"""
Скрипт установки и настройки Gmail Transfer Tool
"""
import os
import sys
import subprocess
import shutil
from pathlib import Path

def check_python_version():
    """Проверяет версию Python"""
    if sys.version_info < (3, 7):
        print("❌ Требуется Python 3.7 или выше")
        print(f"   Текущая версия: {sys.version}")
        return False
    
    print(f"✅ Python версия: {sys.version_info.major}.{sys.version_info.minor}")
    return True

def check_dependencies():
    """Проверяет наличие файла requirements.txt"""
    if not os.path.exists('requirements.txt'):
        print("❌ Файл requirements.txt не найден")
        return False
    
    print("✅ Файл requirements.txt найден")
    return True

def create_virtual_environment():
    """Создает виртуальное окружение"""
    venv_path = Path('venv')
    
    if venv_path.exists():
        print("⚠️  Виртуальное окружение уже существует")
        response = input("   Пересоздать? (y/n): ").lower().strip()
        if response in ['y', 'yes', 'да', 'д']:
            shutil.rmtree(venv_path)
        else:
            print("✅ Используем существующее виртуальное окружение")
            return True
    
    try:
        print("🔄 Создание виртуального окружения...")
        subprocess.run([sys.executable, '-m', 'venv', 'venv'], check=True)
        print("✅ Виртуальное окружение создано")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка создания виртуального окружения: {e}")
        return False

def install_dependencies():
    """Устанавливает зависимости"""
    try:
        # Определяем путь к pip в виртуальном окружении
        if os.name == 'nt':  # Windows
            pip_path = 'venv\\Scripts\\pip'
        else:  # Unix/Linux/MacOS
            pip_path = 'venv/bin/pip'
        
        print("🔄 Установка зависимостей...")
        subprocess.run([pip_path, 'install', '-r', 'requirements.txt'], check=True)
        print("✅ Зависимости установлены")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка установки зависимостей: {e}")
        return False

def create_env_file():
    """Создает .env файл из примера"""
    env_file = Path('.env')
    env_example = Path('env_example.txt')
    
    if env_file.exists():
        print("⚠️  Файл .env уже существует")
        return True
    
    if not env_example.exists():
        print("❌ Файл env_example.txt не найден")
        return False
    
    try:
        shutil.copy(env_example, env_file)
        print("✅ Создан файл .env")
        print("⚠️  Не забудьте отредактировать .env с вашими настройками!")
        return True
    except Exception as e:
        print(f"❌ Ошибка создания .env файла: {e}")
        return False

def create_logs_directory():
    """Создает директорию для логов"""
    logs_dir = Path('logs')
    if not logs_dir.exists():
        logs_dir.mkdir()
        print("✅ Создана директория logs/")
    else:
        print("✅ Директория logs/ уже существует")
    return True

def display_next_steps():
    """Показывает следующие шаги"""
    print("\n" + "="*60)
    print("🎉 УСТАНОВКА ЗАВЕРШЕНА!")
    print("="*60)
    print("\n📋 Следующие шаги:")
    print("\n1. Активируйте виртуальное окружение:")
    if os.name == 'nt':  # Windows
        print("   venv\\Scripts\\activate")
    else:  # Unix/Linux/MacOS
        print("   source venv/bin/activate")
    
    print("\n2. Настройте Google Cloud:")
    print("   - Создайте проект в Google Cloud Console")
    print("   - Включите Gmail API")
    print("   - Создайте сервисный аккаунт")
    print("   - Скачайте JSON ключ")
    
    print("\n3. Настройте Google Workspace:")
    print("   - Откройте Google Admin Console")
    print("   - Добавьте делегирование для сервисного аккаунта")
    
    print("\n4. Отредактируйте .env файл:")
    print("   - Укажите путь к JSON ключу")
    print("   - Укажите ваш домен Google Workspace")
    
    print("\n5. Проверьте установку:")
    print("   python main.py --help")
    
    print("\n📖 Подробные инструкции в файле README.md")
    print("\n" + "="*60)

def main():
    """Главная функция установки"""
    print("🚀 Установка Gmail Transfer Tool")
    print("="*40)
    
    steps = [
        ("Проверка версии Python", check_python_version),
        ("Проверка зависимостей", check_dependencies),
        ("Создание виртуального окружения", create_virtual_environment),
        ("Установка зависимостей", install_dependencies),
        ("Создание .env файла", create_env_file),
        ("Создание директории логов", create_logs_directory),
    ]
    
    for step_name, step_func in steps:
        print(f"\n🔄 {step_name}...")
        if not step_func():
            print(f"\n❌ Установка прервана на этапе: {step_name}")
            return 1
    
    display_next_steps()
    return 0

if __name__ == '__main__':
    sys.exit(main())
