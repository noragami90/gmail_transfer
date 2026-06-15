#!/usr/bin/env python3
"""
Модуль для массового переноса почты
"""
import uuid
import threading
import time
from typing import List, Dict, Any, Callable, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from email_transfer import EmailTransfer
from database import db
from logger import setup_logger

logger = setup_logger(__name__)

class BulkTransferManager:
    """Менеджер массовых переносов"""
    
    def __init__(self):
        self.active_bulk_transfers = {}
        self.progress_callbacks = {}
    
    def create_bulk_transfer(self, name: str, transfers: List[Dict[str, Any]],
                             exclude_emails: str = "") -> str:
        """Создание массового переноса"""
        bulk_id = str(uuid.uuid4())

        # Общий список исключаемых адресов применяется ко всем переносам
        if exclude_emails:
            for transfer_data in transfers:
                transfer_data.setdefault('exclude_emails', exclude_emails)

        # Создаем записи в БД
        bulk_data = {
            'id': bulk_id,
            'name': name,
            'transfers': transfers
        }
        
        db.create_bulk_transfer(bulk_data)
        
        # Создаем отдельные записи для каждого переноса
        for i, transfer_data in enumerate(transfers):
            transfer_id = f"{bulk_id}_{i}"
            transfer_record = {
                'id': transfer_id,
                'source_email': transfer_data['source_email'],
                'target_email': transfer_data['target_email'],
                'query_filter': transfer_data.get('query', ''),
                'max_messages': transfer_data.get('max_messages'),
                'create_label': transfer_data.get('create_label', True),
                'metadata': {
                    'bulk_id': bulk_id,
                    'bulk_index': i,
                    'bulk_name': name
                }
            }
            db.create_transfer(transfer_record)
        
        logger.info(f"Создан массовый перенос {bulk_id}: {name}, {len(transfers)} переносов")
        return bulk_id
    
    def start_bulk_transfer(self, bulk_id: str, progress_callback: Optional[Callable] = None,
                          max_workers: int = 3) -> bool:
        """Запуск массового переноса"""
        bulk_transfer = db.get_bulk_transfer(bulk_id)
        if not bulk_transfer:
            logger.error(f"Массовый перенос {bulk_id} не найден")
            return False
        
        if bulk_id in self.active_bulk_transfers:
            logger.warning(f"Массовый перенос {bulk_id} уже выполняется")
            return False
        
        # Регистрируем callback
        if progress_callback:
            self.progress_callbacks[bulk_id] = progress_callback
        
        # Запускаем в отдельном потоке
        thread = threading.Thread(
            target=self._execute_bulk_transfer,
            args=(bulk_id, max_workers),
            daemon=True
        )
        thread.start()
        
        return True
    
    def _execute_bulk_transfer(self, bulk_id: str, max_workers: int = 3):
        """Выполнение массового переноса"""
        try:
            bulk_transfer = db.get_bulk_transfer(bulk_id)
            transfers_data = bulk_transfer['transfers_data']
            
            self.active_bulk_transfers[bulk_id] = {
                'status': 'running',
                'start_time': datetime.now(),
                'total': len(transfers_data),
                'completed': 0,
                'failed': 0,
                'current_transfer': None
            }
            
            # Обновляем статус в БД
            db.update_bulk_transfer(bulk_id, {
                'status': 'running',
                'start_time': datetime.now()
            })
            
            self._emit_bulk_progress(bulk_id, 'started', 'Начинаем массовый перенос...')
            
            # Используем ThreadPoolExecutor для параллельного выполнения
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Создаем задачи
                future_to_transfer = {}
                
                for i, transfer_data in enumerate(transfers_data):
                    transfer_id = f"{bulk_id}_{i}"
                    future = executor.submit(
                        self._execute_single_transfer,
                        transfer_id,
                        transfer_data,
                        bulk_id
                    )
                    future_to_transfer[future] = (transfer_id, transfer_data)
                
                # Обрабатываем результаты по мере завершения
                for future in as_completed(future_to_transfer):
                    transfer_id, transfer_data = future_to_transfer[future]
                    
                    try:
                        success = future.result()
                        if success:
                            self.active_bulk_transfers[bulk_id]['completed'] += 1
                        else:
                            self.active_bulk_transfers[bulk_id]['failed'] += 1
                    except Exception as e:
                        logger.error(f"Ошибка в переносе {transfer_id}: {e}")
                        self.active_bulk_transfers[bulk_id]['failed'] += 1
                        
                        # Обновляем запись переноса
                        db.update_transfer(transfer_id, {
                            'status': 'error',
                            'error_message': str(e),
                            'end_time': datetime.now()
                        })
                    
                    # Отправляем прогресс
                    self._emit_bulk_progress(bulk_id, 'progress')
            
            # Завершение
            bulk_state = self.active_bulk_transfers[bulk_id]
            completed = bulk_state['completed']
            failed = bulk_state['failed']
            
            final_status = 'completed' if failed == 0 else 'partial' if completed > 0 else 'error'
            
            db.update_bulk_transfer(bulk_id, {
                'status': final_status,
                'completed_transfers': completed,
                'failed_transfers': failed,
                'end_time': datetime.now()
            })
            
            self._emit_bulk_progress(
                bulk_id, 
                final_status, 
                f'Массовый перенос завершен: {completed} успешно, {failed} с ошибками'
            )
            
            logger.info(f"Массовый перенос {bulk_id} завершен: {completed}/{completed+failed}")
            
        except Exception as e:
            logger.error(f"Критическая ошибка в массовом переносе {bulk_id}: {e}")
            
            db.update_bulk_transfer(bulk_id, {
                'status': 'error',
                'end_time': datetime.now()
            })
            
            self._emit_bulk_progress(bulk_id, 'error', f'Критическая ошибка: {str(e)}')
        
        finally:
            # Очищаем активный перенос
            self.active_bulk_transfers.pop(bulk_id, None)
            self.progress_callbacks.pop(bulk_id, None)
    
    def _execute_single_transfer(self, transfer_id: str, transfer_data: Dict[str, Any], 
                               bulk_id: str) -> bool:
        """Выполнение одного переноса в рамках массового"""
        try:
            # Уважаем отмену массового переноса
            bulk_state = self.active_bulk_transfers.get(bulk_id)
            if bulk_state and bulk_state.get('status') == 'cancelled':
                db.update_transfer(transfer_id, {
                    'status': 'cancelled',
                    'end_time': datetime.now()
                })
                return False

            # Обновляем статус текущего переноса
            if bulk_state:
                bulk_state['current_transfer'] = transfer_data

            # Обновляем запись в БД
            db.update_transfer(transfer_id, {
                'status': 'running',
                'start_time': datetime.now()
            })

            logger.info(f"Начинаем перенос {transfer_id}: {transfer_data['source_email']} -> {transfer_data['target_email']}")

            # Создаем EmailTransfer
            email_transfer = EmailTransfer()

            # Парсим исключаемые адреса (если заданы для этого переноса)
            exclude_list = email_transfer.parse_exclude_emails(transfer_data.get('exclude_emails', ''))

            # Выполняем перенос
            result = email_transfer.transfer_all_messages(
                source_user_email=transfer_data['source_email'],
                target_user_email=transfer_data['target_email'],
                query=transfer_data.get('query', ''),
                max_messages=transfer_data.get('max_messages'),
                create_transfer_label=transfer_data.get('create_label', True),
                exclude_emails=exclude_list
            )

            # Обновляем результат в БД
            db.update_transfer(transfer_id, {
                'status': 'completed',
                'total_messages': result.get('total', 0),
                'transferred_messages': result.get('transferred', 0),
                'error_messages': result.get('errors', 0),
                'skipped_messages': result.get('skipped', 0),
                'end_time': datetime.now(),
                'metadata': {
                    **db.get_transfer(transfer_id)['metadata'],
                    'transfer_result': result
                }
            })
            
            logger.info(f"Перенос {transfer_id} завершен успешно: {result}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка в переносе {transfer_id}: {e}")
            
            db.update_transfer(transfer_id, {
                'status': 'error',
                'error_message': str(e),
                'end_time': datetime.now()
            })
            
            return False
    
    def _emit_bulk_progress(self, bulk_id: str, status: str, message: str = ''):
        """Отправка прогресса массового переноса"""
        if bulk_id not in self.progress_callbacks:
            return
        
        callback = self.progress_callbacks[bulk_id]
        
        if bulk_id in self.active_bulk_transfers:
            state = self.active_bulk_transfers[bulk_id]
            progress_data = {
                'bulk_id': bulk_id,
                'status': status,
                'message': message,
                'total': state['total'],
                'completed': state['completed'],
                'failed': state['failed'],
                'current_transfer': state.get('current_transfer'),
                'timestamp': datetime.now().isoformat()
            }
        else:
            progress_data = {
                'bulk_id': bulk_id,
                'status': status,
                'message': message,
                'timestamp': datetime.now().isoformat()
            }
        
        try:
            callback(progress_data)
        except Exception as e:
            logger.error(f"Ошибка в callback массового переноса {bulk_id}: {e}")
    
    def cancel_bulk_transfer(self, bulk_id: str) -> bool:
        """Отмена массового переноса"""
        if bulk_id not in self.active_bulk_transfers:
            return False
        
        # Помечаем как отмененный
        self.active_bulk_transfers[bulk_id]['status'] = 'cancelled'
        
        # Обновляем в БД
        db.update_bulk_transfer(bulk_id, {
            'status': 'cancelled',
            'end_time': datetime.now()
        })
        
        self._emit_bulk_progress(bulk_id, 'cancelled', 'Массовый перенос отменен')
        
        logger.info(f"Массовый перенос {bulk_id} отменен")
        return True
    
    def get_bulk_status(self, bulk_id: str) -> Optional[Dict[str, Any]]:
        """Получение статуса массового переноса"""
        # Сначала проверяем активные переносы
        if bulk_id in self.active_bulk_transfers:
            return self.active_bulk_transfers[bulk_id]
        
        # Затем проверяем в БД
        return db.get_bulk_transfer(bulk_id)
    
    def parse_bulk_input(self, text: str) -> List[Dict[str, Any]]:
        """Парсинг текстового ввода для массового переноса"""
        transfers = []
        lines = text.strip().split('\n')
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            try:
                # Формат: source_email -> target_email [query] [max:N]
                if '->' in line:
                    parts = line.split('->')
                    if len(parts) != 2:
                        continue
                    
                    source = parts[0].strip()
                    target_part = parts[1].strip()
                    
                    # Парсим дополнительные параметры
                    target_parts = target_part.split()
                    target = target_parts[0]
                    
                    query = ''
                    max_messages = None
                    
                    for part in target_parts[1:]:
                        if part.startswith('max:'):
                            try:
                                max_messages = int(part[4:])
                            except ValueError:
                                pass
                        else:
                            query += ' ' + part
                    
                    query = query.strip()
                    
                    transfers.append({
                        'source_email': source,
                        'target_email': target,
                        'query': query,
                        'max_messages': max_messages,
                        'create_label': True
                    })
                
            except Exception as e:
                logger.warning(f"Ошибка парсинга строки {i+1}: {line} - {e}")
                continue
        
        return transfers

# Глобальный экземпляр менеджера
bulk_manager = BulkTransferManager()
