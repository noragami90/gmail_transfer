"""
Gmail API клиент для работы с почтой через сервисный аккаунт
"""
import time
from typing import List, Dict, Any, Optional
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import base64
import email
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import SERVICE_ACCOUNT_FILE, SCOPES, API_DELAY, BATCH_SIZE
from logger import setup_logger

logger = setup_logger(__name__)

class GmailClient:
    """Клиент для работы с Gmail API через сервисный аккаунт"""
    
    def __init__(self):
        """Инициализация Gmail клиента"""
        self.service = None
        self._authenticate()
    
    def _authenticate(self):
        """Аутентификация через сервисный аккаунт"""
        try:
            logger.info("Инициализация аутентификации Gmail API...")
            
            # Создаем credentials из сервисного аккаунта
            credentials = service_account.Credentials.from_service_account_file(
                SERVICE_ACCOUNT_FILE,
                scopes=SCOPES
            )
            
            # Создаем сервис Gmail API
            self.service = build('gmail', 'v1', credentials=credentials)
            logger.info("Аутентификация Gmail API успешно завершена")
            
        except Exception as e:
            logger.error(f"Ошибка аутентификации Gmail API: {e}")
            raise
    
    def _impersonate_user(self, email_address: str):
        """
        Имперсонация пользователя для доступа к его почтовому ящику
        
        Args:
            email_address: Email адрес пользователя для имперсонации
            
        Returns:
            Gmail service для конкретного пользователя
        """
        try:
            credentials = service_account.Credentials.from_service_account_file(
                SERVICE_ACCOUNT_FILE,
                scopes=SCOPES
            )
            
            # Создаем делегированные credentials для конкретного пользователя
            delegated_credentials = credentials.with_subject(email_address)
            
            # Создаем сервис для этого пользователя
            user_service = build('gmail', 'v1', credentials=delegated_credentials)
            
            logger.info(f"Успешная имперсонация пользователя: {email_address}")
            return user_service
            
        except Exception as e:
            logger.error(f"Ошибка имперсонации пользователя {email_address}: {e}")
            raise
    
    def get_messages_list(self, user_email: str, query: str = "", 
                         max_results: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Получает список сообщений из почтового ящика пользователя
        
        Args:
            user_email: Email пользователя
            query: Поисковый запрос Gmail (например, "is:unread")
            max_results: Максимальное количество результатов
            
        Returns:
            Список сообщений
        """
        try:
            user_service = self._impersonate_user(user_email)
            messages = []
            next_page_token = None
            
            logger.info(f"Получение списка сообщений для {user_email}")
            
            while True:
                # Запрос к API
                results = user_service.users().messages().list(
                    userId='me',
                    q=query,
                    pageToken=next_page_token,
                    maxResults=min(BATCH_SIZE, max_results) if max_results else BATCH_SIZE
                ).execute()
                
                batch_messages = results.get('messages', [])
                messages.extend(batch_messages)
                
                logger.info(f"Получено {len(batch_messages)} сообщений, всего: {len(messages)}")
                
                # Проверяем лимит
                if max_results and len(messages) >= max_results:
                    messages = messages[:max_results]
                    break
                
                # Проверяем наличие следующей страницы
                next_page_token = results.get('nextPageToken')
                if not next_page_token:
                    break
                
                # Задержка между запросами
                time.sleep(API_DELAY)
            
            logger.info(f"Всего получено {len(messages)} сообщений для {user_email}")
            return messages
            
        except HttpError as e:
            logger.error(f"HTTP ошибка при получении сообщений: {e}")
            raise
        except Exception as e:
            logger.error(f"Ошибка при получении сообщений: {e}")
            raise
    
    def get_message_details(self, user_email: str, message_id: str) -> Dict[str, Any]:
        """
        Получает детали конкретного сообщения
        
        Args:
            user_email: Email пользователя
            message_id: ID сообщения
            
        Returns:
            Детали сообщения
        """
        try:
            user_service = self._impersonate_user(user_email)
            
            message = user_service.users().messages().get(
                userId='me',
                id=message_id,
                format='full'
            ).execute()
            
            return message
            
        except HttpError as e:
            logger.error(f"HTTP ошибка при получении сообщения {message_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Ошибка при получении сообщения {message_id}: {e}")
            raise
    
    def import_message(self, target_user_email: str, raw_message: str, 
                      label_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Импортирует сообщение в почтовый ящик целевого пользователя
        
        Args:
            target_user_email: Email целевого пользователя
            raw_message: Raw сообщение в формате RFC 2822
            label_ids: Список ID меток для применения
            
        Returns:
            Результат импорта
        """
        try:
            target_service = self._impersonate_user(target_user_email)
            
            # Подготавливаем тело запроса
            body = {
                'raw': base64.urlsafe_b64encode(raw_message.encode()).decode()
            }
            
            if label_ids:
                body['labelIds'] = label_ids
            
            # Импортируем сообщение
            result = target_service.users().messages().import_(
                userId='me',
                body=body
            ).execute()
            
            logger.debug(f"Сообщение импортировано: {result.get('id')}")
            return result
            
        except HttpError as e:
            logger.error(f"HTTP ошибка при импорте сообщения: {e}")
            raise
        except Exception as e:
            logger.error(f"Ошибка при импорте сообщения: {e}")
            raise
    
    def get_labels(self, user_email: str) -> List[Dict[str, Any]]:
        """
        Получает список меток пользователя
        
        Args:
            user_email: Email пользователя
            
        Returns:
            Список меток
        """
        try:
            user_service = self._impersonate_user(user_email)
            
            results = user_service.users().labels().list(userId='me').execute()
            labels = results.get('labels', [])
            
            logger.info(f"Получено {len(labels)} меток для {user_email}")
            return labels
            
        except HttpError as e:
            logger.error(f"HTTP ошибка при получении меток: {e}")
            raise
        except Exception as e:
            logger.error(f"Ошибка при получении меток: {e}")
            raise
    
    def create_label(self, user_email: str, label_name: str) -> Dict[str, Any]:
        """
        Создает новую метку
        
        Args:
            user_email: Email пользователя
            label_name: Название метки
            
        Returns:
            Созданная метка
        """
        try:
            user_service = self._impersonate_user(user_email)
            
            label_object = {
                'name': label_name,
                'labelListVisibility': 'labelShow',
                'messageListVisibility': 'show'
            }
            
            result = user_service.users().labels().create(
                userId='me',
                body=label_object
            ).execute()
            
            logger.info(f"Создана метка '{label_name}' для {user_email}")
            return result
            
        except HttpError as e:
            logger.error(f"HTTP ошибка при создании метки: {e}")
            raise
        except Exception as e:
            logger.error(f"Ошибка при создании метки: {e}")
            raise
