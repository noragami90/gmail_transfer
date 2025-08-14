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

# Валидация обязательных параметров
if not SERVICE_ACCOUNT_FILE:
    raise ValueError("Не задан SERVICE_ACCOUNT_FILE в .env файле")

if not WORKSPACE_DOMAIN:
    raise ValueError("Не задан WORKSPACE_DOMAIN в .env файле")

if not os.path.exists(SERVICE_ACCOUNT_FILE):
    raise FileNotFoundError(f"Файл сервисного аккаунта не найден: {SERVICE_ACCOUNT_FILE}")
