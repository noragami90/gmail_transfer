#!/usr/bin/env python3
"""
Основной скрипт для переноса почты Gmail между сотрудниками
"""
import argparse
import sys
from typing import Optional

from email_transfer import EmailTransfer
from logger import setup_logger

logger = setup_logger(__name__)

def main():
    """Главная функция программы"""
    parser = argparse.ArgumentParser(
        description='Перенос почты Gmail между сотрудниками в Google Workspace',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:

1. Перенести всю почту:
   python main.py old.employee@company.com new.employee@company.com

2. Перенести только непрочитанные письма:
   python main.py old.employee@company.com new.employee@company.com --query "is:unread"

3. Перенести максимум 100 писем:
   python main.py old.employee@company.com new.employee@company.com --max-messages 100

4. Посмотреть статистику почтового ящика:
   python main.py --stats user@company.com

5. Перенести письма с определенным поиском:
   python main.py old@company.com new@company.com --query "from:important@client.com"
        """
    )
    
    # Основные аргументы
    parser.add_argument('source_email', nargs='?', 
                       help='Email исходного пользователя (откуда переносим)')
    parser.add_argument('target_email', nargs='?',
                       help='Email целевого пользователя (куда переносим)')
    
    # Опциональные аргументы
    parser.add_argument('--query', '-q', default='',
                       help='Поисковый запрос Gmail для фильтрации сообщений (например: "is:unread")')
    parser.add_argument('--max-messages', '-m', type=int,
                       help='Максимальное количество сообщений для переноса')
    parser.add_argument('--no-transfer-label', action='store_true',
                       help='Не создавать метку "Transferred from [email]"')
    parser.add_argument('--stats', '-s', metavar='EMAIL',
                       help='Показать статистику почтового ящика пользователя')
    parser.add_argument('--dry-run', action='store_true',
                       help='Пробный запуск (только подсчет сообщений, без переноса)')
    
    args = parser.parse_args()
    
    try:
        # Инициализируем класс переноса
        transfer = EmailTransfer()
        
        # Если запрошена статистика
        if args.stats:
            logger.info("=== РЕЖИМ СТАТИСТИКИ ===")
            stats = transfer.get_user_stats(args.stats, query=args.query)
            
            print(f"\n📊 Статистика почтового ящика:")
            print(f"   Email: {stats['email']}")
            print(f"   Всего сообщений: {stats['total_messages']:,}")
            print(f"   Количество меток: {stats['labels_count']}")
            print(f"   Запрос: {stats['query']}")
            
            return 0
        
        # Проверяем обязательные аргументы для переноса
        if not args.source_email or not args.target_email:
            parser.print_help()
            print("\n❌ Ошибка: Необходимо указать email исходного и целевого пользователя")
            return 1
        
        # Пробный запуск
        if args.dry_run:
            logger.info("=== ПРОБНЫЙ ЗАПУСК ===")
            print(f"\n🔍 Анализ сообщений для переноса:")
            print(f"   От: {args.source_email}")
            print(f"   К: {args.target_email}")
            print(f"   Запрос: {args.query or 'все сообщения'}")
            
            # Получаем только статистику
            messages = transfer.gmail_client.get_messages_list(
                args.source_email, 
                query=args.query,
                max_results=args.max_messages
            )
            
            print(f"   Найдено сообщений: {len(messages):,}")
            if args.max_messages:
                print(f"   Лимит: {args.max_messages:,}")
            
            print(f"\n✅ Пробный запуск завершен. Используйте команду без --dry-run для фактического переноса.")
            return 0
        
        # Выполняем перенос
        logger.info("=== НАЧАЛО ПЕРЕНОСА ПОЧТЫ ===")
        print(f"\n📧 Перенос почты:")
        print(f"   От: {args.source_email}")
        print(f"   К: {args.target_email}")
        print(f"   Запрос: {args.query or 'все сообщения'}")
        if args.max_messages:
            print(f"   Лимит: {args.max_messages:,}")
        
        # Подтверждение от пользователя
        confirm = input(f"\n⚠️  Вы уверены, что хотите перенести почту? (да/нет): ").lower().strip()
        if confirm not in ['да', 'yes', 'y', 'д']:
            print("❌ Операция отменена пользователем")
            return 0
        
        # Выполняем перенос
        result = transfer.transfer_all_messages(
            source_user_email=args.source_email,
            target_user_email=args.target_email,
            query=args.query,
            max_messages=args.max_messages,
            create_transfer_label=not args.no_transfer_label
        )
        
        # Выводим результаты
        print(f"\n✅ Перенос завершен!")
        print(f"   Всего сообщений: {result['total']:,}")
        print(f"   Успешно перенесено: {result['transferred']:,}")
        print(f"   Ошибок: {result['errors']:,}")
        print(f"   Пропущено: {result['skipped']:,}")
        
        if result['errors'] > 0:
            print(f"\n⚠️  Внимание: {result['errors']} сообщений не удалось перенести.")
            print(f"   Проверьте логи для подробностей.")
            return 1
        
        logger.info("=== ПЕРЕНОС ЗАВЕРШЕН УСПЕШНО ===")
        return 0
        
    except KeyboardInterrupt:
        print(f"\n❌ Операция прервана пользователем")
        logger.info("Операция прервана пользователем")
        return 1
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        logger.error(f"Критическая ошибка: {e}")
        return 1

if __name__ == '__main__':
    sys.exit(main())
