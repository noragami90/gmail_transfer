#!/usr/bin/env python3
"""
Скрипт для тестирования подключения к Gmail API
"""
import sys
from gmail_client import GmailClient
from logger import setup_logger

logger = setup_logger(__name__)

def test_authentication():
    """Тестирует аутентификацию"""
    try:
        print("🔄 Проверка аутентификации Gmail API...")
        client = GmailClient()
        print("✅ Аутентификация успешна")
        return True
    except Exception as e:
        print(f"❌ Ошибка аутентификации: {e}")
        return False

def test_user_access(email: str):
    """Тестирует доступ к конкретному пользователю"""
    try:
        print(f"🔄 Проверка доступа к пользователю {email}...")
        client = GmailClient()
        
        # Пытаемся получить список меток
        labels = client.get_labels(email)
        print(f"✅ Доступ к {email} получен. Найдено {len(labels)} меток")
        
        # Пытаемся получить несколько сообщений
        messages = client.get_messages_list(email, max_results=5)
        print(f"✅ Получено {len(messages)} сообщений для теста")
        
        return True
    except Exception as e:
        print(f"❌ Ошибка доступа к {email}: {e}")
        return False

def test_domain_delegation():
    """Тестирует делегирование на уровне домена"""
    from config import WORKSPACE_DOMAIN
    
    test_email = f"test@{WORKSPACE_DOMAIN}"
    print(f"🔄 Тестирование делегирования для домена {WORKSPACE_DOMAIN}...")
    print(f"   Попытка доступа к {test_email}")
    
    try:
        client = GmailClient()
        user_service = client._impersonate_user(test_email)
        print("✅ Делегирование настроено корректно")
        return True
    except Exception as e:
        print(f"❌ Ошибка делегирования: {e}")
        print("\n💡 Возможные причины:")
        print("   1. Сервисный аккаунт не добавлен в Google Admin Console")
        print("   2. Неверно указаны OAuth scopes")
        print("   3. Аккаунт test@domain.com не существует")
        return False

def main():
    """Главная функция тестирования"""
    print("🧪 Тестирование подключения Gmail Transfer Tool")
    print("="*50)
    
    # Базовая аутентификация
    if not test_authentication():
        print("\n❌ Критическая ошибка: невозможно аутентифицироваться")
        print("💡 Проверьте:")
        print("   - Путь к JSON файлу сервисного аккаунта")
        print("   - Корректность содержимого JSON файла")
        print("   - Включен ли Gmail API в Google Cloud Console")
        return 1
    
    # Тестирование делегирования
    if not test_domain_delegation():
        print("\n❌ Ошибка делегирования прав")
        print("💡 Проверьте настройки в Google Admin Console")
        return 1
    
    # Тестирование доступа к конкретному пользователю
    if len(sys.argv) > 1:
        user_email = sys.argv[1]
        if not test_user_access(user_email):
            print(f"\n❌ Ошибка доступа к {user_email}")
            print("💡 Проверьте:")
            print("   - Существует ли этот пользователь")
            print("   - Правильно ли указан домен")
            return 1
    else:
        print("\n💡 Для проверки доступа к конкретному пользователю:")
        print("   python test_connection.py user@yourdomain.com")
    
    print("\n✅ Все тесты пройдены успешно!")
    print("🚀 Система готова к работе")
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
