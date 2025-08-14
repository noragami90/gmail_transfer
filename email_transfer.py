"""
Основная логика переноса почты между аккаунтами Gmail
"""
import base64
import time
from typing import List, Dict, Any, Optional, Tuple
from tqdm import tqdm
import email
from email.utils import parsedate_to_datetime

from gmail_client import GmailClient
from logger import setup_logger
from config import API_DELAY

logger = setup_logger(__name__)

class EmailTransfer:
    """Класс для переноса почты между аккаунтами Gmail"""
    
    def __init__(self):
        """Инициализация класса переноса"""
        self.gmail_client = GmailClient()
        self.transferred_count = 0
        self.error_count = 0
        self.skipped_count = 0
    
    def get_message_raw(self, user_email: str, message_id: str) -> str:
        """
        Получает raw содержимое сообщения
        
        Args:
            user_email: Email пользователя
            message_id: ID сообщения
            
        Returns:
            Raw содержимое сообщения
        """
        try:
            # Получаем сообщение в raw формате
            user_service = self.gmail_client._impersonate_user(user_email)
            
            message = user_service.users().messages().get(
                userId='me',
                id=message_id,
                format='raw'
            ).execute()
            
            # Декодируем raw содержимое
            raw_data = message['raw']
            raw_message = base64.urlsafe_b64decode(raw_data).decode('utf-8')
            
            return raw_message
            
        except Exception as e:
            logger.error(f"Ошибка получения raw сообщения {message_id}: {e}")
            raise
    
    def preserve_message_metadata(self, source_message: Dict[str, Any], 
                                 target_user_email: str) -> List[str]:
        """
        Сохраняет метаданные сообщения (метки) в целевом аккаунте
        
        Args:
            source_message: Исходное сообщение
            target_user_email: Email целевого пользователя
            
        Returns:
            Список ID меток для применения
        """
        try:
            source_label_ids = source_message.get('labelIds', [])
            target_label_ids = []
            
            # Получаем существующие метки целевого пользователя
            target_labels = self.gmail_client.get_labels(target_user_email)
            target_labels_map = {label['name']: label['id'] for label in target_labels}
            
            # Получаем метки исходного пользователя для сопоставления
            source_user_email = self._extract_email_from_message(source_message)
            if source_user_email:
                source_labels = self.gmail_client.get_labels(source_user_email)
                source_labels_map = {label['id']: label['name'] for label in source_labels}
            else:
                source_labels_map = {}
            
            # Сопоставляем метки
            for label_id in source_label_ids:
                # Пропускаем системные метки, которые нельзя создавать
                if label_id in ['INBOX', 'SENT', 'DRAFT', 'SPAM', 'TRASH', 'IMPORTANT', 'STARRED']:
                    if label_id in target_labels_map.values():
                        target_label_ids.append(label_id)
                    continue
                
                # Получаем название метки
                label_name = source_labels_map.get(label_id)
                if not label_name:
                    continue
                
                # Проверяем, существует ли метка в целевом аккаунте
                if label_name in target_labels_map:
                    target_label_ids.append(target_labels_map[label_name])
                else:
                    # Создаем новую метку
                    try:
                        new_label = self.gmail_client.create_label(target_user_email, label_name)
                        target_label_ids.append(new_label['id'])
                        target_labels_map[label_name] = new_label['id']
                    except Exception as e:
                        logger.warning(f"Не удалось создать метку '{label_name}': {e}")
            
            return target_label_ids
            
        except Exception as e:
            logger.error(f"Ошибка обработки меток: {e}")
            return []
    
    def _extract_email_from_message(self, message: Dict[str, Any]) -> Optional[str]:
        """
        Извлекает email отправителя из сообщения
        
        Args:
            message: Сообщение
            
        Returns:
            Email отправителя или None
        """
        try:
            headers = message.get('payload', {}).get('headers', [])
            for header in headers:
                if header['name'].lower() == 'delivered-to':
                    return header['value']
            return None
        except Exception:
            return None
    
    def transfer_single_message(self, source_user_email: str, target_user_email: str, 
                               message_id: str) -> bool:
        """
        Переносит одно сообщение
        
        Args:
            source_user_email: Email исходного пользователя
            target_user_email: Email целевого пользователя
            message_id: ID сообщения
            
        Returns:
            True если перенос успешен, False иначе
        """
        try:
            # Получаем детали сообщения
            message_details = self.gmail_client.get_message_details(source_user_email, message_id)
            
            # Получаем raw содержимое
            raw_message = self.get_message_raw(source_user_email, message_id)
            
            # Подготавливаем метки
            label_ids = self.preserve_message_metadata(message_details, target_user_email)
            
            # Импортируем сообщение
            result = self.gmail_client.import_message(
                target_user_email, 
                raw_message, 
                label_ids
            )
            
            logger.debug(f"Сообщение {message_id} успешно перенесено как {result.get('id')}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка переноса сообщения {message_id}: {e}")
            return False
    
    def transfer_all_messages(self, source_user_email: str, target_user_email: str,
                             query: str = "", max_messages: Optional[int] = None,
                             create_transfer_label: bool = True) -> Dict[str, int]:
        """
        Переносит все сообщения от одного пользователя к другому
        
        Args:
            source_user_email: Email исходного пользователя
            target_user_email: Email целевого пользователя
            query: Поисковый запрос для фильтрации сообщений
            max_messages: Максимальное количество сообщений для переноса
            create_transfer_label: Создать метку "Transferred from [email]"
            
        Returns:
            Статистика переноса
        """
        logger.info(f"Начинаем перенос почты от {source_user_email} к {target_user_email}")
        
        # Сбрасываем счетчики
        self.transferred_count = 0
        self.error_count = 0
        self.skipped_count = 0
        
        try:
            # Создаем метку для отслеживания перенесенных сообщений
            transfer_label_id = None
            if create_transfer_label:
                try:
                    transfer_label_name = f"Transferred from {source_user_email}"
                    transfer_label = self.gmail_client.create_label(target_user_email, transfer_label_name)
                    transfer_label_id = transfer_label['id']
                    logger.info(f"Создана метка переноса: {transfer_label_name}")
                except Exception as e:
                    logger.warning(f"Не удалось создать метку переноса: {e}")
            
            # Получаем список сообщений
            logger.info("Получение списка сообщений...")
            messages = self.gmail_client.get_messages_list(
                source_user_email, 
                query=query, 
                max_results=max_messages
            )
            
            if not messages:
                logger.info("Сообщения для переноса не найдены")
                return {
                    'total': 0,
                    'transferred': 0,
                    'errors': 0,
                    'skipped': 0
                }
            
            # Переносим сообщения с прогрессом
            logger.info(f"Начинаем перенос {len(messages)} сообщений...")
            
            with tqdm(total=len(messages), desc="Перенос сообщений") as pbar:
                for message in messages:
                    message_id = message['id']
                    
                    try:
                        # Переносим сообщение
                        success = self.transfer_single_message(
                            source_user_email, 
                            target_user_email, 
                            message_id
                        )
                        
                        if success:
                            self.transferred_count += 1
                            
                            # Добавляем метку переноса если нужно
                            if transfer_label_id:
                                try:
                                    target_service = self.gmail_client._impersonate_user(target_user_email)
                                    target_service.users().messages().modify(
                                        userId='me',
                                        id=message_id,
                                        body={'addLabelIds': [transfer_label_id]}
                                    ).execute()
                                except Exception:
                                    pass  # Не критично если не удалось добавить метку
                        else:
                            self.error_count += 1
                        
                    except Exception as e:
                        logger.error(f"Критическая ошибка при переносе сообщения {message_id}: {e}")
                        self.error_count += 1
                    
                    # Обновляем прогресс
                    pbar.set_postfix({
                        'Перенесено': self.transferred_count,
                        'Ошибок': self.error_count
                    })
                    pbar.update(1)
                    
                    # Задержка между запросами
                    time.sleep(API_DELAY)
            
            # Итоговая статистика
            total_messages = len(messages)
            logger.info(f"Перенос завершен!")
            logger.info(f"Всего сообщений: {total_messages}")
            logger.info(f"Успешно перенесено: {self.transferred_count}")
            logger.info(f"Ошибок: {self.error_count}")
            logger.info(f"Пропущено: {self.skipped_count}")
            
            return {
                'total': total_messages,
                'transferred': self.transferred_count,
                'errors': self.error_count,
                'skipped': self.skipped_count
            }
            
        except Exception as e:
            logger.error(f"Критическая ошибка при переносе почты: {e}")
            raise
    
    def get_user_stats(self, user_email: str, query: str = "") -> Dict[str, Any]:
        """
        Получает статистику по почтовому ящику пользователя
        
        Args:
            user_email: Email пользователя
            query: Поисковый запрос
            
        Returns:
            Статистика почтового ящика
        """
        try:
            logger.info(f"Получение статистики для {user_email}")
            
            # Получаем общее количество сообщений
            messages = self.gmail_client.get_messages_list(user_email, query=query, max_results=1)
            total_count = len(self.gmail_client.get_messages_list(user_email, query=query))
            
            # Получаем метки
            labels = self.gmail_client.get_labels(user_email)
            
            stats = {
                'email': user_email,
                'total_messages': total_count,
                'labels_count': len(labels),
                'query': query or "все сообщения"
            }
            
            logger.info(f"Статистика для {user_email}: {total_count} сообщений, {len(labels)} меток")
            return stats
            
        except Exception as e:
            logger.error(f"Ошибка получения статистики для {user_email}: {e}")
            raise
