#!/usr/bin/env python3
"""
Веб-приложение Gmail Transfer Tool
"""
import os
import json
import uuid
from datetime import datetime
from typing import Dict, Any
from flask import Flask, render_template, request, jsonify, session
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import threading
import time

from email_transfer import EmailTransfer
from gmail_client import GmailClient
from logger import setup_logger
from database import db
from bulk_transfer import bulk_manager

# Настройка приложения
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', str(uuid.uuid4()))
app.config['CORS_HEADERS'] = 'Content-Type'

# Инициализация расширений
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", logger=True, engineio_logger=True)

# Логгер
logger = setup_logger(__name__)

# Глобальные переменные для отслеживания задач
active_tasks = {}
task_results = {}

# Кэш для статистики пользователей (email -> stats)
user_stats_cache = {}
cache_timeout = 300  # 5 минут

class WebSocketHandler:
    """Обработчик WebSocket событий для отправки прогресса"""
    
    @staticmethod
    def emit_progress(task_id: str, progress: Dict[str, Any]):
        """Отправляет прогресс выполнения задачи"""
        socketio.emit('transfer_progress', {
            'task_id': task_id,
            'progress': progress
        }, room=task_id)
    
    @staticmethod
    def emit_status(task_id: str, status: str, message: str = ""):
        """Отправляет статус задачи"""
        socketio.emit('transfer_status', {
            'task_id': task_id,
            'status': status,
            'message': message,
            'timestamp': datetime.now().isoformat()
        }, room=task_id)
    
    @staticmethod
    def emit_error(task_id: str, error: str):
        """Отправляет ошибку"""
        socketio.emit('transfer_error', {
            'task_id': task_id,
            'error': error,
            'timestamp': datetime.now().isoformat()
        }, room=task_id)

class ProgressTracker:
    """Отслеживает прогресс переноса и отправляет обновления через WebSocket"""
    
    def __init__(self, task_id: str):
        self.task_id = task_id
        self.total_messages = 0
        self.processed = 0
        self.transferred = 0
        self.errors = 0
        self.skipped = 0
        self.start_time = datetime.now()

    def set_total(self, total: int):
        """Устанавливает общее количество сообщений"""
        self.total_messages = total
        self._emit_update()

    def update_progress(self, transferred: int, errors: int, skipped: int = 0):
        """Обновляет прогресс"""
        self.processed += 1
        self.transferred = transferred
        self.errors = errors
        self.skipped = skipped
        self._emit_update()
    
    def _emit_update(self):
        """Отправляет обновление прогресса"""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        
        # Рассчитываем скорость переноса (сообщений в минуту)
        messages_per_minute = (self.transferred / (elapsed / 60)) if elapsed > 0 and self.transferred > 0 else 0
        
        # Оценка времени до завершения
        remaining_messages = self.total_messages - self.processed
        eta_seconds = (remaining_messages / (self.processed / elapsed)) if elapsed > 0 and self.processed > 0 else 0
        
        progress = {
            'total': self.total_messages,
            'processed': self.processed,
            'transferred': self.transferred,
            'errors': self.errors,
            'skipped': self.skipped,
            'percentage': (self.processed / self.total_messages * 100) if self.total_messages > 0 else 0,
            'elapsed_time': elapsed,
            'estimated_remaining': eta_seconds,
            'messages_per_minute': round(messages_per_minute, 1)
        }
        
        # Обновляем active_tasks для API
        if self.task_id in active_tasks:
            active_tasks[self.task_id]['progress'] = progress
            
        WebSocketHandler.emit_progress(self.task_id, progress)

def transfer_emails_async(task_id: str, source_email: str, target_email: str, 
                         query: str = "", max_messages: int = None, 
                         create_transfer_label: bool = True, exclude_emails: str = ""):
    """Асинхронный перенос писем с отслеживанием прогресса"""
    try:
        # Создаем запись в базе данных
        transfer_record = {
            'id': task_id,
            'source_email': source_email,
            'target_email': target_email,
            'query_filter': query,
            'max_messages': max_messages,
            'create_label': create_transfer_label
        }
        db.create_transfer(transfer_record)
        
        active_tasks[task_id] = {
            'status': 'running',
            'source_email': source_email,
            'target_email': target_email,
            'start_time': datetime.now().isoformat()
        }
        
        WebSocketHandler.emit_status(task_id, 'starting', 'Инициализация переноса...')
        
        # Создаем трекер прогресса
        tracker = ProgressTracker(task_id)
        
        # Инициализируем Gmail клиент и трансфер
        transfer = EmailTransfer()
        
        # Парсим исключаемые адреса
        exclude_emails_list = transfer.parse_exclude_emails(exclude_emails)
        
        WebSocketHandler.emit_status(task_id, 'analyzing', 'Анализ почтового ящика...')
        
        # Получаем список сообщений
        messages = transfer.gmail_client.get_messages_list(
            source_email, 
            query=query, 
            max_results=max_messages
        )
        
        if not messages:
            WebSocketHandler.emit_status(task_id, 'completed', 'Сообщения для переноса не найдены')
            task_results[task_id] = {
                'status': 'completed',
                'total': 0,
                'transferred': 0,
                'errors': 0,
                'message': 'Сообщения не найдены'
            }
            active_tasks.pop(task_id, None)
            return
        
        total_messages = len(messages)
        tracker.set_total(total_messages)

        # КРИТИЧНО: Обновляем БД с количеством найденных сообщений
        db.update_transfer(task_id, {
            'status': 'running',
            'total_messages': total_messages,
            'start_time': datetime.now()
        })

        # ЭФФЕКТИВНОСТЬ: один раз получаем карты меток и создаём метку переноса,
        # чтобы не дёргать API меток на каждое письмо
        WebSocketHandler.emit_status(task_id, 'preparing', 'Подготовка меток...')
        source_labels = transfer.gmail_client.get_labels(source_email)
        target_labels = transfer.gmail_client.get_labels(target_email)
        source_labels_map = {label['id']: label['name'] for label in source_labels}
        target_labels_map = {label['name']: label['id'] for label in target_labels}

        transfer_label_id = None
        if create_transfer_label:
            transfer_label_name = f"Transferred from {source_email}"
            if transfer_label_name in target_labels_map:
                transfer_label_id = target_labels_map[transfer_label_name]
            else:
                try:
                    new_label = transfer.gmail_client.create_label(target_email, transfer_label_name)
                    transfer_label_id = new_label['id']
                    target_labels_map[transfer_label_name] = transfer_label_id
                except Exception as e:
                    logger.warning(f"Не удалось создать метку переноса: {e}")

        WebSocketHandler.emit_status(task_id, 'transferring', f'Начинаем перенос {total_messages} сообщений...')

        # Принудительно отправляем начальный прогресс
        WebSocketHandler.emit_progress(task_id, {
            'total': total_messages,
            'processed': 0,
            'transferred': 0,
            'errors': 0,
            'skipped': 0,
            'percentage': 0,
            'elapsed_time': 0,
            'estimated_remaining': 0
        })

        # Переносим сообщения
        transferred_count = 0
        error_count = 0
        skipped_count = 0

        for i, message in enumerate(messages):
            if task_id not in active_tasks:  # Проверяем, не отменена ли задача
                break

            try:
                status = transfer.transfer_single_message(
                    source_email,
                    target_email,
                    message['id'],
                    transfer_label_id=transfer_label_id,
                    source_labels_map=source_labels_map,
                    target_labels_map=target_labels_map,
                    exclude_emails=exclude_emails_list
                )

                if status == 'transferred':
                    transferred_count += 1
                elif status == 'skipped':
                    skipped_count += 1
                else:
                    error_count += 1

            except Exception as e:
                logger.error(f"Ошибка переноса сообщения {message['id']}: {e}")
                error_count += 1

            tracker.update_progress(transferred_count, error_count, skipped_count)

            # Обновляем БД каждые 10 сообщений
            if i % 10 == 0:
                db.update_transfer(task_id, {
                    'transferred_messages': transferred_count,
                    'error_messages': error_count,
                    'skipped_messages': skipped_count
                })

            time.sleep(0.1)  # Небольшая задержка

        # Завершение
        result = {
            'status': 'completed',
            'total': len(messages),
            'transferred': transferred_count,
            'errors': error_count,
            'skipped': skipped_count,
            'end_time': datetime.now().isoformat()
        }

        # Обновляем запись в БД
        db.update_transfer(task_id, {
            'status': 'completed',
            'total_messages': len(messages),
            'transferred_messages': transferred_count,
            'error_messages': error_count,
            'skipped_messages': skipped_count,
            'end_time': datetime.now()
        })
        
        task_results[task_id] = result
        active_tasks.pop(task_id, None)
        
        WebSocketHandler.emit_status(
            task_id,
            'completed',
            f'Перенос завершен! Перенесено: {transferred_count}, '
            f'Пропущено: {skipped_count}, Ошибок: {error_count}'
        )
        
        logger.info(f"Задача {task_id} завершена: {result}")
        
    except Exception as e:
        error_msg = f"Критическая ошибка при переносе: {str(e)}"
        logger.error(f"Задача {task_id}: {error_msg}")
        
        # Обновляем запись в БД
        db.update_transfer(task_id, {
            'status': 'error',
            'error_message': error_msg,
            'end_time': datetime.now()
        })
        
        task_results[task_id] = {
            'status': 'error',
            'error': error_msg,
            'end_time': datetime.now().isoformat()
        }
        active_tasks.pop(task_id, None)
        
        WebSocketHandler.emit_error(task_id, error_msg)

# Маршруты Flask
@app.route('/')
def index():
    """Главная страница"""
    return render_template('index.html')

@app.route('/history')
def history():
    """Страница истории переносов"""
    return render_template('history.html')

@app.route('/single')
def single():
    """Страница одиночного переноса"""
    return render_template('single.html')

@app.route('/bulk')
def bulk():
    """Страница массового переноса"""
    return render_template('bulk.html')



@app.route('/api/task-status/<task_id>')
def get_task_status(task_id):
    """Получить статус задачи"""
    try:
        if task_id in active_tasks:
            response = {
                'status': 'running',
                'task': active_tasks[task_id]
            }
            
            # Используем данные из active_tasks (от ProgressTracker) если есть
            if 'progress' in active_tasks[task_id]:
                response['progress'] = active_tasks[task_id]['progress']
            else:
                # Fallback к данным из БД
                db_record = db.get_transfer(task_id)
                if db_record:
                    response['progress'] = {
                        'total': db_record.get('total_messages', 0),
                        'transferred': db_record.get('transferred_messages', 0),
                        'errors': db_record.get('error_messages', 0),
                        'processed': db_record.get('transferred_messages', 0),
                        'percentage': 0,
                        'elapsed_time': 0,
                        'estimated_remaining': 0,
                        'messages_per_minute': 0
                    }
            return jsonify(response)
        elif task_id in task_results:
            return jsonify({
                'status': 'completed',
                'result': task_results[task_id]
            })
        else:
            return jsonify({
                'status': 'not_found',
                'message': 'Задача не найдена'
            }), 404
    except Exception as e:
        logger.error(f"Ошибка получения статуса задачи {task_id}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/clear-stuck-tasks', methods=['POST'])
def clear_stuck_tasks():
    """Очистить зависшие задачи"""
    try:
        cleared_count = 0
        current_time = datetime.now()
        
        # Очищаем задачи, которые висят больше 30 минут
        stuck_tasks = []
        for task_id, task_info in list(active_tasks.items()):
            try:
                start_time = datetime.fromisoformat(task_info['start_time'])
                elapsed = (current_time - start_time).total_seconds()
                
                if elapsed > 1800:  # 30 минут
                    stuck_tasks.append(task_id)
            except Exception as e:
                logger.warning(f"Ошибка проверки задачи {task_id}: {e}")
                stuck_tasks.append(task_id)
        
        # Удаляем зависшие задачи
        for task_id in stuck_tasks:
            active_tasks.pop(task_id, None)
            task_results.pop(task_id, None)
            
            # Обновляем статус в БД
            db.update_transfer(task_id, {
                'status': 'cancelled',
                'end_time': current_time,
                'error_message': 'Задача была очищена как зависшая'
            })
            cleared_count += 1
            
        logger.info(f"Очищено {cleared_count} зависших задач")
        
        return jsonify({
            'success': True,
            'cleared_count': cleared_count,
            'active_tasks': len(active_tasks)
        })
        
    except Exception as e:
        logger.error(f"Ошибка очистки зависших задач: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/clear-database', methods=['POST'])
def clear_database():
    """Очистить базу данных от старых записей"""
    try:
        # Очищаем все записи переносов
        cleared_transfers = db.clear_all_transfers()
        
        # Очищаем активные задачи и результаты
        active_count = len(active_tasks)
        results_count = len(task_results)
        
        active_tasks.clear()
        task_results.clear()
        
        logger.info(f"База данных очищена: {cleared_transfers} переносов, {active_count} активных задач, {results_count} результатов")
        
        return jsonify({
            'success': True,
            'cleared_transfers': cleared_transfers,
            'cleared_active_tasks': active_count,
            'cleared_results': results_count
        })
        
    except Exception as e:
        logger.error(f"Ошибка очистки базы данных: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/active-tasks')
def get_active_tasks():
    """Получить список активных задач"""
    try:
        active_list = []
        for task_id, task_info in active_tasks.items():
            active_list.append({
                'task_id': task_id,
                'status': 'running',
                'source_email': task_info.get('source_email'),
                'target_email': task_info.get('target_email'),
                'start_time': task_info.get('start_time'),
                'progress': task_info.get('progress', {})
            })
        
        return jsonify({
            'active_tasks': active_list,
            'count': len(active_list)
        })
        
    except Exception as e:
        logger.error(f"Ошибка получения активных задач: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/health')
def health_check():
    """Проверка здоровья приложения"""
    try:
        # Проверяем подключение к Gmail API
        client = GmailClient()
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'gmail_api': 'connected'
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'timestamp': datetime.now().isoformat(),
            'error': str(e)
        }), 500

@app.route('/api/test-connection', methods=['POST'])
def test_connection():
    """Тестирует подключение к пользователю"""
    try:
        data = request.get_json()
        email = data.get('email')
        
        if not email:
            return jsonify({'error': 'Email обязателен'}), 400
        
        client = GmailClient()
        
        # Проверяем доступ к пользователю
        labels = client.get_labels(email)
        messages = client.get_messages_list(email, max_results=1)
        
        return jsonify({
            'status': 'success',
            'email': email,
            'labels_count': len(labels),
            'accessible': True
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'accessible': False
        }), 400

@app.route('/api/user-stats', methods=['POST'])
def get_user_stats():
    """Получает статистику пользователя с кэшированием"""
    try:
        data = request.get_json()
        email = data.get('email')
        query = data.get('query', '')
        
        if not email:
            return jsonify({'error': 'Email обязателен'}), 400
        
        # Создаем ключ для кэша
        cache_key = f"{email}:{query}"
        current_time = time.time()
        
        # Проверяем кэш
        if cache_key in user_stats_cache:
            cached_data = user_stats_cache[cache_key]
            if current_time - cached_data['timestamp'] < cache_timeout:
                logger.info(f"Возвращаем кэшированную статистику для {email}")
                return jsonify(cached_data['stats'])
        
        # Получаем новую статистику
        logger.info(f"Получаем новую статистику для {email}")
        transfer = EmailTransfer()
        stats = transfer.get_user_stats(email, query)
        
        # Сохраняем в кэш
        user_stats_cache[cache_key] = {
            'stats': stats,
            'timestamp': current_time
        }
        
        return jsonify(stats)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/clear-cache', methods=['POST'])
def clear_stats_cache():
    """Очищает кэш статистики"""
    try:
        data = request.get_json()
        email = data.get('email')
        
        if email:
            # Очищаем кэш для конкретного пользователя
            keys_to_remove = [key for key in user_stats_cache.keys() if key.startswith(f"{email}:")]
            for key in keys_to_remove:
                user_stats_cache.pop(key, None)
            logger.info(f"Очищен кэш для {email}")
        else:
            # Очищаем весь кэш
            user_stats_cache.clear()
            logger.info("Очищен весь кэш статистики")
        
        return jsonify({'status': 'cache_cleared'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/start-transfer', methods=['POST'])
def start_transfer():
    """Запускает перенос писем"""
    try:
        data = request.get_json()
        
        # Валидация данных
        source_email = data.get('source_email')
        target_email = data.get('target_email')
        query = data.get('query', '')
        max_messages = data.get('max_messages')
        create_label = data.get('create_transfer_label', True)
        exclude_emails = data.get('exclude_emails', '')
        
        if not source_email or not target_email:
            return jsonify({'error': 'Source и target email обязательны'}), 400
        
        # Создаем уникальный ID задачи
        task_id = str(uuid.uuid4())
        
        # Запускаем перенос в отдельном потоке
        thread = threading.Thread(
            target=transfer_emails_async,
            args=(task_id, source_email, target_email, query, max_messages, create_label, exclude_emails)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'task_id': task_id,
            'status': 'started',
            'message': 'Перенос запущен'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/cancel-transfer', methods=['POST'])
def cancel_transfer():
    """Отменяет перенос писем"""
    try:
        data = request.get_json()
        task_id = data.get('task_id')
        
        if not task_id:
            return jsonify({'error': 'Task ID обязателен'}), 400
        
        if task_id in active_tasks:
            active_tasks.pop(task_id)
            db.update_transfer(task_id, {
                'status': 'cancelled',
                'end_time': datetime.now(),
                'error_message': 'Перенос отменён пользователем'
            })
            WebSocketHandler.emit_status(task_id, 'cancelled', 'Перенос отменен пользователем')
            return jsonify({'status': 'cancelled'})
        else:
            return jsonify({'error': 'Задача не найдена или уже завершена'}), 404
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/transfers/history')
def get_transfers_history():
    """Получение истории переносов"""
    try:
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 20))
        status = request.args.get('status')
        source_email = request.args.get('source_email')
        
        offset = (page - 1) * limit

        transfers = db.get_transfers(
            limit=limit,
            offset=offset,
            status=status,
            source_email=source_email
        )

        total = db.get_transfers_count(status=status, source_email=source_email)
        stats = db.get_transfer_stats()

        return jsonify({
            'transfers': transfers,
            'stats': stats,
            'total': total,
            'page': page,
            'limit': limit
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/transfers/<transfer_id>')
def get_transfer_details(transfer_id):
    """Детали одного переноса"""
    try:
        transfer = db.get_transfer(transfer_id)
        if transfer:
            return jsonify(transfer)
        return jsonify({'error': 'Перенос не найден'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/bulk-transfers')
def get_bulk_transfers_list():
    """Список массовых переносов с пагинацией (для истории)"""
    try:
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 20))
        status = request.args.get('status')
        name = request.args.get('name')

        offset = (page - 1) * limit

        bulk_transfers = db.get_bulk_transfers(
            limit=limit, offset=offset, status=status, name=name
        )
        total = db.get_bulk_transfers_count(status=status, name=name)

        return jsonify({
            'bulk_transfers': bulk_transfers,
            'total': total,
            'page': page,
            'limit': limit
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/transfers/stats')
def get_transfer_stats():
    """Получение статистики переносов"""
    try:
        stats = db.get_transfer_stats()
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/bulk-transfer/create', methods=['POST'])
def create_bulk_transfer():
    """Создание массового переноса"""
    try:
        data = request.get_json()
        name = data.get('name')
        transfers_text = data.get('transfers_text')
        exclude_emails = data.get('exclude_emails', '')

        if not name or not transfers_text:
            return jsonify({'error': 'Имя и список переносов обязательны'}), 400

        # Парсим список переносов
        transfers = bulk_manager.parse_bulk_input(transfers_text)

        if not transfers:
            return jsonify({'error': 'Не удалось распарсить список переносов'}), 400

        # Создаем массовый перенос
        bulk_id = bulk_manager.create_bulk_transfer(name, transfers, exclude_emails=exclude_emails)
        
        return jsonify({
            'bulk_id': bulk_id,
            'name': name,
            'transfers_count': len(transfers),
            'status': 'created'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/bulk-transfer/start', methods=['POST'])
def start_bulk_transfer():
    """Запуск массового переноса"""
    try:
        data = request.get_json()
        bulk_id = data.get('bulk_id')
        max_workers = data.get('max_workers', 3)
        
        if not bulk_id:
            return jsonify({'error': 'Bulk ID обязателен'}), 400
        
        # Создаем callback для WebSocket
        def progress_callback(progress_data):
            socketio.emit('bulk_transfer_progress', progress_data, room=bulk_id)
        
        success = bulk_manager.start_bulk_transfer(
            bulk_id,
            progress_callback=progress_callback,
            max_workers=max_workers
        )
        
        if success:
            return jsonify({
                'bulk_id': bulk_id,
                'status': 'started',
                'message': 'Массовый перенос запущен'
            })
        else:
            return jsonify({'error': 'Не удалось запустить массовый перенос'}), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/bulk-transfer/cancel', methods=['POST'])
def cancel_bulk_transfer():
    """Отмена массового переноса"""
    try:
        data = request.get_json()
        bulk_id = data.get('bulk_id')
        
        if not bulk_id:
            return jsonify({'error': 'Bulk ID обязателен'}), 400
        
        success = bulk_manager.cancel_bulk_transfer(bulk_id)
        
        if success:
            return jsonify({'status': 'cancelled'})
        else:
            return jsonify({'error': 'Массовый перенос не найден или уже завершен'}), 404
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/bulk-transfer/status/<bulk_id>')
def get_bulk_transfer_status(bulk_id):
    """Получение статуса массового переноса"""
    try:
        status = bulk_manager.get_bulk_status(bulk_id)
        if status:
            return jsonify(status)
        else:
            return jsonify({'error': 'Массовый перенос не найден'}), 404
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500



# WebSocket события
@socketio.on('connect')
def handle_connect():
    """Обработка подключения WebSocket"""
    logger.info(f"Client connected: {request.sid}")
    emit('connected', {'status': 'Connected to Gmail Transfer Tool'})

@socketio.on('disconnect')
def handle_disconnect():
    """Обработка отключения WebSocket"""
    logger.info(f"Client disconnected: {request.sid}")

@socketio.on('join_task')
def handle_join_task(data):
    """Присоединение к комнате задачи для получения обновлений"""
    task_id = data.get('task_id')
    if task_id:
        session['task_id'] = task_id
        logger.info(f"Client {request.sid} joined task {task_id}")
        emit('joined_task', {'task_id': task_id})

@socketio.on('join_bulk_task')
def handle_join_bulk_task(data):
    """Присоединение к комнате массового переноса"""
    bulk_id = data.get('bulk_id')
    if bulk_id:
        session['bulk_id'] = bulk_id
        logger.info(f"Client {request.sid} joined bulk task {bulk_id}")
        emit('joined_bulk_task', {'bulk_id': bulk_id})

if __name__ == '__main__':
    # Создаем папки если не существуют
    os.makedirs('logs', exist_ok=True)
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static/css', exist_ok=True)
    os.makedirs('static/js', exist_ok=True)
    
    # Запускаем приложение
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    logger.info(f"Запуск Gmail Transfer Web App на порту {port}")
    socketio.run(app, host='0.0.0.0', port=port, debug=debug)
