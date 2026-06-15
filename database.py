#!/usr/bin/env python3
"""
База данных для Gmail Transfer Tool
"""
import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path
import threading
from contextlib import contextmanager

from logger import setup_logger

logger = setup_logger(__name__)

class TransferDatabase:
    """Класс для работы с базой данных переносов"""
    
    def __init__(self, db_path: str = "data/transfers.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)
        self._local = threading.local()
        self.init_database()
    
    @contextmanager
    def get_connection(self):
        """Получение подключения к базе данных"""
        if not hasattr(self._local, 'connection'):
            self._local.connection = sqlite3.connect(
                self.db_path, 
                check_same_thread=False,
                timeout=30.0
            )
            self._local.connection.row_factory = sqlite3.Row
        
        try:
            yield self._local.connection
        except Exception:
            self._local.connection.rollback()
            raise
        else:
            self._local.connection.commit()
    
    def init_database(self):
        """Инициализация базы данных"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Таблица переносов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS transfers (
                    id TEXT PRIMARY KEY,
                    source_email TEXT NOT NULL,
                    target_email TEXT NOT NULL,
                    query_filter TEXT,
                    max_messages INTEGER,
                    create_label BOOLEAN DEFAULT TRUE,
                    status TEXT NOT NULL DEFAULT 'pending',
                    total_messages INTEGER DEFAULT 0,
                    transferred_messages INTEGER DEFAULT 0,
                    error_messages INTEGER DEFAULT 0,
                    skipped_messages INTEGER DEFAULT 0,
                    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    end_time TIMESTAMP,
                    error_message TEXT,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица массовых переносов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS bulk_transfers (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    transfers_data TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    total_transfers INTEGER DEFAULT 0,
                    completed_transfers INTEGER DEFAULT 0,
                    failed_transfers INTEGER DEFAULT 0,
                    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    end_time TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Индексы для быстрого поиска
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_transfers_status ON transfers(status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_transfers_source ON transfers(source_email)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_transfers_target ON transfers(target_email)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_transfers_created ON transfers(created_at)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_bulk_status ON bulk_transfers(status)')

            # Миграция: добавляем недостающие колонки в существующие БД
            existing_columns = {row['name'] for row in cursor.execute('PRAGMA table_info(transfers)')}
            if 'skipped_messages' not in existing_columns:
                cursor.execute('ALTER TABLE transfers ADD COLUMN skipped_messages INTEGER DEFAULT 0')
                logger.info("Миграция: добавлена колонка skipped_messages")

        logger.info(f"База данных инициализирована: {self.db_path}")
    
    def create_transfer(self, transfer_data: Dict[str, Any]) -> str:
        """Создание записи о переносе"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO transfers (
                    id, source_email, target_email, query_filter, 
                    max_messages, create_label, status, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                transfer_data['id'],
                transfer_data['source_email'],
                transfer_data['target_email'],
                transfer_data.get('query_filter'),
                transfer_data.get('max_messages'),
                transfer_data.get('create_label', True),
                'pending',
                json.dumps(transfer_data.get('metadata', {}))
            ))
            
        logger.info(f"Создана запись переноса: {transfer_data['id']}")
        return transfer_data['id']
    
    def update_transfer(self, transfer_id: str, updates: Dict[str, Any]):
        """Обновление записи переноса"""
        if not updates:
            return
            
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Строим динамический запрос
            set_clauses = []
            values = []
            
            for field, value in updates.items():
                if field == 'metadata':
                    value = json.dumps(value)
                set_clauses.append(f"{field} = ?")
                values.append(value)
            
            values.append(transfer_id)
            
            query = f"UPDATE transfers SET {', '.join(set_clauses)} WHERE id = ?"
            cursor.execute(query, values)
            
        logger.debug(f"Обновлен перенос {transfer_id}: {list(updates.keys())}")
    
    def get_transfer(self, transfer_id: str) -> Optional[Dict[str, Any]]:
        """Получение записи переноса"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM transfers WHERE id = ?', (transfer_id,))
            row = cursor.fetchone()
            
            if row:
                transfer = dict(row)
                if transfer['metadata']:
                    transfer['metadata'] = json.loads(transfer['metadata'])
                return transfer
            return None
    
    def get_transfers(self, limit: int = 50, offset: int = 0, 
                     status: Optional[str] = None,
                     source_email: Optional[str] = None) -> List[Dict[str, Any]]:
        """Получение списка переносов"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            where_clauses = []
            params = []
            
            if status:
                where_clauses.append("status = ?")
                params.append(status)
            
            if source_email:
                where_clauses.append("source_email LIKE ?")
                params.append(f"%{source_email}%")

            where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

            query = f'''
                SELECT * FROM transfers
                {where_sql}
                ORDER BY created_at DESC 
                LIMIT ? OFFSET ?
            '''
            params.extend([limit, offset])
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            transfers = []
            for row in rows:
                transfer = dict(row)
                if transfer['metadata']:
                    transfer['metadata'] = json.loads(transfer['metadata'])
                transfers.append(transfer)
            
            return transfers
    
    def get_transfers_count(self, status: Optional[str] = None,
                            source_email: Optional[str] = None) -> int:
        """Подсчёт количества переносов с учётом фильтров (для пагинации)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            where_clauses = []
            params = []

            if status:
                where_clauses.append("status = ?")
                params.append(status)

            if source_email:
                where_clauses.append("source_email LIKE ?")
                params.append(f"%{source_email}%")

            where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

            cursor.execute(f"SELECT COUNT(*) FROM transfers {where_sql}", params)
            return cursor.fetchone()[0]

    def get_bulk_transfers_count(self, status: Optional[str] = None,
                                 name: Optional[str] = None) -> int:
        """Подсчёт количества массовых переносов с учётом фильтров"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            where_clauses = []
            params = []

            if status:
                where_clauses.append("status = ?")
                params.append(status)

            if name:
                where_clauses.append("name LIKE ?")
                params.append(f"%{name}%")

            where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

            cursor.execute(f"SELECT COUNT(*) FROM bulk_transfers {where_sql}", params)
            return cursor.fetchone()[0]

    def get_transfer_stats(self) -> Dict[str, Any]:
        """Получение статистики переносов"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Общая статистика
            cursor.execute('''
                SELECT 
                    COUNT(*) as total_transfers,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                    SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as failed,
                    SUM(CASE WHEN status = 'running' THEN 1 ELSE 0 END) as running,
                    SUM(transferred_messages) as total_messages_transferred
                FROM transfers
            ''')
            stats = dict(cursor.fetchone())
            
            # Статистика за последние 30 дней
            cursor.execute('''
                SELECT COUNT(*) as recent_transfers
                FROM transfers 
                WHERE created_at >= datetime('now', '-30 days')
            ''')
            stats['recent_transfers'] = cursor.fetchone()[0]
            
            # Топ источников
            cursor.execute('''
                SELECT source_email, COUNT(*) as count
                FROM transfers 
                GROUP BY source_email 
                ORDER BY count DESC 
                LIMIT 5
            ''')
            stats['top_sources'] = [dict(row) for row in cursor.fetchall()]
            
            return stats
    
    def create_bulk_transfer(self, bulk_data: Dict[str, Any]) -> str:
        """Создание массового переноса"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO bulk_transfers (
                    id, name, transfers_data, total_transfers, status
                ) VALUES (?, ?, ?, ?, ?)
            ''', (
                bulk_data['id'],
                bulk_data['name'],
                json.dumps(bulk_data['transfers']),
                len(bulk_data['transfers']),
                'pending'
            ))
            
        logger.info(f"Создан массовый перенос: {bulk_data['id']}")
        return bulk_data['id']
    
    def update_bulk_transfer(self, bulk_id: str, updates: Dict[str, Any]):
        """Обновление массового переноса"""
        if not updates:
            return
            
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            set_clauses = []
            values = []
            
            for field, value in updates.items():
                set_clauses.append(f"{field} = ?")
                values.append(value)
            
            values.append(bulk_id)
            
            query = f"UPDATE bulk_transfers SET {', '.join(set_clauses)} WHERE id = ?"
            cursor.execute(query, values)
    
    def get_bulk_transfer(self, bulk_id: str) -> Optional[Dict[str, Any]]:
        """Получение массового переноса"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM bulk_transfers WHERE id = ?', (bulk_id,))
            row = cursor.fetchone()
            
            if row:
                bulk = dict(row)
                bulk['transfers_data'] = json.loads(bulk['transfers_data'])
                return bulk
            return None
    
    def get_bulk_transfers(self, limit: int = 20, offset: int = 0,
                           status: Optional[str] = None,
                           name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Получение списка массовых переносов"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            where_clauses = []
            params = []

            if status:
                where_clauses.append("status = ?")
                params.append(status)

            if name:
                where_clauses.append("name LIKE ?")
                params.append(f"%{name}%")

            where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
            params.extend([limit, offset])

            cursor.execute(f'''
                SELECT * FROM bulk_transfers
                {where_sql}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            ''', params)
            rows = cursor.fetchall()
            
            bulks = []
            for row in rows:
                bulk = dict(row)
                bulk['transfers_data'] = json.loads(bulk['transfers_data'])
                bulks.append(bulk)
            
            return bulks
    
    def cleanup_old_records(self, days: int = 90):
        """Очистка старых записей"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Удаляем старые завершенные переносы
            cursor.execute('''
                DELETE FROM transfers 
                WHERE status IN ('completed', 'error', 'cancelled') 
                AND created_at < datetime('now', '-{} days')
            '''.format(days))
            deleted_transfers = cursor.rowcount
            
            # Удаляем старые массовые переносы
            cursor.execute('''
                DELETE FROM bulk_transfers 
                WHERE status IN ('completed', 'error', 'cancelled') 
                AND created_at < datetime('now', '-{} days')
            '''.format(days))
            deleted_bulk = cursor.rowcount
            
        logger.info(f"Очищено старых записей: {deleted_transfers} переносов, {deleted_bulk} массовых")
        return deleted_transfers + deleted_bulk
    
    def clear_all_transfers(self) -> int:
        """Полная очистка всех записей переносов"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Подсчитываем количество записей перед удалением
            cursor.execute('SELECT COUNT(*) FROM transfers')
            transfers_count = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM bulk_transfers')
            bulk_count = cursor.fetchone()[0]
            
            # Удаляем все записи
            cursor.execute('DELETE FROM transfers')
            cursor.execute('DELETE FROM bulk_transfers')
            
            # Сбрасываем автоинкремент (если таблица существует)
            try:
                cursor.execute('DELETE FROM sqlite_sequence WHERE name IN ("transfers", "bulk_transfers")')
            except sqlite3.OperationalError:
                # Таблица sqlite_sequence может не существовать, если нет AUTOINCREMENT полей
                pass
            
            conn.commit()
            
            total_cleared = transfers_count + bulk_count
            logger.info(f"Полная очистка базы данных: удалено {transfers_count} переносов и {bulk_count} массовых переносов")
            
            return total_cleared

# Глобальный экземпляр базы данных
db = TransferDatabase()
