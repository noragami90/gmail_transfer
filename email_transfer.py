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
    
    def parse_exclude_emails(self, exclude_emails: str) -> List[str]:
        """
        Парсит строку исключаемых email адресов
        
        Args:
            exclude_emails: Строка с адресами через запятую или построчно
            
        Returns:
            Список email адресов для исключения
        """
        if not exclude_emails:
            return []
        
        # Разделяем по запятым и новым строкам
        emails = []
        for part in exclude_emails.replace(',', '\n').split('\n'):
            email = part.strip().lower()
            if email and '@' in email:
                emails.append(email)
        
        logger.info(f"Исключаемые адреса: {emails}")
        return emails
    
    def should_exclude_message(self, message_data: Dict[str, Any], exclude_emails: List[str]) -> bool:
        """
        Проверяет, нужно ли исключить сообщение из переноса
        
        Args:
            message_data: Данные сообщения от Gmail API
            exclude_emails: Список исключаемых email адресов
            
        Returns:
            True если сообщение нужно исключить
        """
        if not exclude_emails:
            return False
        
        # Получаем заголовки
        headers = message_data.get('payload', {}).get('headers', [])
        
        # Ищем отправителя (From)
        sender = None
        for header in headers:
            if header['name'].lower() == 'from':
                sender = header['value'].lower()
                break
        
        if not sender:
            return False
        
        # Извлекаем email из строки "Name <email@domain.com>" или просто "email@domain.com"
        import re
        email_match = re.search(r'<([^>]+)>|([^\s<>]+@[^\s<>]+)', sender)
        if email_match:
            sender_email = (email_match.group(1) or email_match.group(2)).lower()
            
            # Проверяем полное совпадение или совпадение домена
            for exclude_email in exclude_emails:
                if exclude_email == sender_email:
                    logger.debug(f"Исключаем письмо от {sender_email} (точное совпадение)")
                    return True
                elif exclude_email.startswith('@') and sender_email.endswith(exclude_email):
                    logger.debug(f"Исключаем письмо от {sender_email} (совпадение домена {exclude_email})")
                    return True
        
        return False
    
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
            
            # ВСЕГДА добавляем INBOX для перенесенных сообщений
            target_label_ids.append('INBOX')
            
            # Сопоставляем метки
            for label_id in source_label_ids:
                # Пропускаем системные метки, которые нельзя создавать
                if label_id in ['INBOX', 'SENT', 'DRAFT', 'SPAM', 'TRASH', 'IMPORTANT', 'STARRED']:
                    # INBOX уже добавлен выше, остальные проверяем
                    if label_id != 'INBOX' and label_id in target_labels_map.values():
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
    
    def modify_headers_for_import(self, raw_message: str, target_user_email: str, source_user_email: str = None) -> str:
        """
        Модифицирует заголовки сообщения для корректного импорта
        
        Args:
            raw_message: Исходное raw сообщение
            target_user_email: Email целевого пользователя
            
        Returns:
            Модифицированное raw сообщение
        """
        try:
            import uuid
            import time
            from datetime import datetime
            
            lines = raw_message.split('\n')
            modified_lines = []
            message_id_replaced = False
            
            for line in lines:
                # Заменяем проблемные заголовки
                if line.startswith('Delivered-To:'):
                    # Заменяем на целевой email
                    modified_lines.append(f'Delivered-To: {target_user_email}')
                elif line.startswith('Message-ID:') or line.startswith('Message-Id:'):
                    # Генерируем новый уникальный Message-ID
                    if not message_id_replaced:
                        new_msg_id = f"<{uuid.uuid4()}@gmail-transfer.local>"
                        modified_lines.append(f'Message-ID: {new_msg_id}')
                        message_id_replaced = True
                elif line.startswith('X-Google-Smtp-Source:'):
                    # Удаляем Google SMTP заголовки
                    continue
                elif line.startswith('X-Received:'):
                    # Удаляем Google X-Received заголовки
                    continue
                elif line.startswith('ARC-Seal:') or line.startswith('ARC-Message-Signature:') or line.startswith('ARC-Authentication-Results:'):
                    # Удаляем ARC заголовки
                    continue
                elif line.startswith('Received: from 895081623425'):
                    # Удаляем Google API Received заголовки
                    continue
                elif line.startswith('Received: by 2002:') and ('gmailapi.google.com' in line or 'gmail.googleapis.com' in line):
                    # Удаляем Gmail API Received заголовки
                    continue
                else:
                    modified_lines.append(line)
            
            # Добавляем заголовок переноса
            transfer_header = f'X-Gmail-Transfer: Moved from {source_user_email} at {datetime.now().isoformat()}'
            
            # Находим конец заголовков и вставляем наш заголовок
            header_end_index = -1
            for i, line in enumerate(modified_lines):
                if line.strip() == '':  # Пустая строка означает конец заголовков
                    header_end_index = i
                    break
            
            if header_end_index > 0:
                modified_lines.insert(header_end_index, transfer_header)
            else:
                # Если не нашли конец заголовков, добавляем в начало
                modified_lines.insert(1, transfer_header)
            
            return '\n'.join(modified_lines)
            
        except Exception as e:
            logger.warning(f"Ошибка модификации заголовков: {e}")
            return raw_message  # Возвращаем оригинал при ошибке
    
    def _map_message_labels(self, message_details: Dict[str, Any], 
                           source_labels_map: Dict[str, str], 
                           target_labels_map: Dict[str, str]) -> List[str]:
        """
        Эффективно сопоставляет метки сообщения без лишних API вызовов
        
        Args:
            message_details: Детали сообщения
            source_labels_map: Карта меток источника (id -> name)
            target_labels_map: Карта меток цели (name -> id)
            
        Returns:
            Список ID меток для применения
        """
        # ВСЕГДА добавляем INBOX для перенесенных сообщений
        label_ids = ['INBOX']
        
        if not source_labels_map or not target_labels_map:
            return label_ids
            
        source_label_ids = message_details.get('labelIds', [])
        
        # Сопоставляем метки
        for label_id in source_label_ids:
            # Пропускаем системные метки, которые нельзя создавать
            if label_id in ['INBOX', 'SENT', 'DRAFT', 'SPAM', 'TRASH', 'IMPORTANT', 'STARRED']:
                # INBOX уже добавлен выше, остальные проверяем
                if label_id != 'INBOX':
                    label_ids.append(label_id)
                continue
            
            # Получаем название метки
            label_name = source_labels_map.get(label_id)
            if not label_name:
                continue
            
            # Проверяем, существует ли метка в целевом аккаунте
            if label_name in target_labels_map:
                label_ids.append(target_labels_map[label_name])
        
        return label_ids
    
    def transfer_single_message(self, source_user_email: str, target_user_email: str, 
                               message_id: str, transfer_label_id: str = None, 
                               source_labels_map: Dict[str, str] = None,
                               target_labels_map: Dict[str, str] = None,
                               exclude_emails: List[str] = None) -> bool:
        """
        Переносит одно сообщение
        
        Args:
            source_user_email: Email исходного пользователя
            target_user_email: Email целевого пользователя
            message_id: ID сообщения
            transfer_label_id: ID метки переноса (если уже создана)
            source_labels_map: Карта меток источника (id -> name)
            target_labels_map: Карта меток цели (name -> id)
            
        Returns:
            True если перенос успешен, False иначе
        """
        try:
            # Получаем детали сообщения
            message_details = self.gmail_client.get_message_details(source_user_email, message_id)
            
            # Проверяем, нужно ли исключить это сообщение
            if exclude_emails and self.should_exclude_message(message_details, exclude_emails):
                logger.info(f"Сообщение {message_id} исключено из переноса")
                return True  # Считаем успешным, но пропускаем
            
            # Получаем raw содержимое
            raw_message = self.get_message_raw(source_user_email, message_id)
            
            # КРИТИЧНО: Модифицируем заголовки для корректного импорта
            raw_message = self.modify_headers_for_import(raw_message, target_user_email, source_user_email)
            
            # Если карты меток не переданы, получаем их (для standalone вызовов)
            if source_labels_map is None or target_labels_map is None:
                logger.info("Получение карт меток для standalone переноса...")
                source_labels = self.gmail_client.get_labels(source_user_email)
                target_labels = self.gmail_client.get_labels(target_user_email)
                
                source_labels_map = {label['id']: label['name'] for label in source_labels}
                target_labels_map = {label['name']: label['id'] for label in target_labels}
            
            # Создаем метку переноса, если не передана
            if transfer_label_id is None:
                transfer_label_name = f"Transferred from {source_user_email}"
                
                # Проверяем, существует ли метка
                if transfer_label_name in target_labels_map:
                    transfer_label_id = target_labels_map[transfer_label_name]
                    logger.info(f"Используем существующую метку переноса: {transfer_label_name}")
                else:
                    # Создаем новую метку
                    try:
                        transfer_label = self.gmail_client.create_label(target_user_email, transfer_label_name)
                        transfer_label_id = transfer_label['id']
                        target_labels_map[transfer_label_name] = transfer_label_id
                        logger.info(f"Создана метка переноса: {transfer_label_name}")
                    except Exception as e:
                        logger.warning(f"Не удалось создать метку переноса: {e}")
                        transfer_label_id = None
            
            # Подготавливаем метки эффективно
            label_ids = self._map_message_labels(message_details, source_labels_map, target_labels_map)
            
            # Добавляем метку переноса
            if transfer_label_id:
                label_ids.append(transfer_label_id)
            
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
            # ОДИН РАЗ получаем карты меток для эффективности
            logger.info("Подготовка карт меток...")
            source_labels = self.gmail_client.get_labels(source_user_email)
            target_labels = self.gmail_client.get_labels(target_user_email)
            
            source_labels_map = {label['id']: label['name'] for label in source_labels}
            target_labels_map = {label['name']: label['id'] for label in target_labels}
            
            # Создаем метку для отслеживания перенесенных сообщений
            transfer_label_id = None
            if create_transfer_label:
                try:
                    transfer_label_name = f"Transferred from {source_user_email}"
                    
                    # Проверяем, может метка уже существует
                    if transfer_label_name in target_labels_map:
                        transfer_label_id = target_labels_map[transfer_label_name]
                        logger.info(f"Используем существующую метку переноса: {transfer_label_name}")
                    else:
                        transfer_label = self.gmail_client.create_label(target_user_email, transfer_label_name)
                        transfer_label_id = transfer_label['id']
                        target_labels_map[transfer_label_name] = transfer_label_id  # Обновляем карту
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
                        # Переносим сообщение ЭФФЕКТИВНО (без повторных API вызовов)
                        success = self.transfer_single_message(
                            source_user_email, 
                            target_user_email, 
                            message_id,
                            transfer_label_id,
                            source_labels_map,
                            target_labels_map
                        )
                        
                        if success:
                            self.transferred_count += 1
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
