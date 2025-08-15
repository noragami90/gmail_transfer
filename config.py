"""
Конфигурация проекта для переноса Gmail почты
"""
import os
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Gmail API настройки
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.insert',
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.labels'
]

# Конфигурация из переменных окружения
SERVICE_ACCOUNT_FILE = os.getenv('SERVICE_ACCOUNT_FILE')
WORKSPACE_DOMAIN = os.getenv('WORKSPACE_DOMAIN')
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
BATCH_SIZE = int(os.getenv('BATCH_SIZE', 100))
API_DELAY = float(os.getenv('API_DELAY', 0.1))

# Значения по умолчанию
if not SERVICE_ACCOUNT_FILE:
    SERVICE_ACCOUNT_FILE = './service-account-key.json'

if not WORKSPACE_DOMAIN:
    WORKSPACE_DOMAIN = 'auto'  # Автоопределение
