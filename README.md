# Gmail Transfer Tool - Инструмент переноса почты Gmail

🚀 **Профессиональный инструмент для переноса почты между сотрудниками в Google Workspace**

## 📋 Описание

Этот инструмент позволяет полностью перенести почту одного сотрудника другому в среде Google Workspace. Поддерживает перенос сообщений с сохранением меток, структуры и метаданных.

## ✨ Возможности

- ✅ **Полный перенос почты** между аккаунтами Google Workspace
- ✅ **Сохранение меток** и структуры папок  
- ✅ **Фильтрация сообщений** с помощью Gmail Query Language
- ✅ **Пакетная обработка** с контролем скорости
- ✅ **Подробное логирование** процесса переноса
- ✅ **Прогресс-бар** для отслеживания процесса
- ✅ **Статистика** почтовых ящиков
- ✅ **Пробный режим** для оценки объема работ
- ✅ **Обработка ошибок** и продолжение работы

## 🛠 Требования

- Python 3.7+
- Google Workspace с правами администратора
- Сервисный аккаунт Google Cloud с делегированием прав

## 📦 Установка

1. **Клонируйте репозиторий:**
   ```bash
   git clone <repository-url>
   cd gmail_transfer
   ```

2. **Создайте виртуальное окружение:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # На Windows: venv\\Scripts\\activate
   ```

3. **Установите зависимости:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Настройте конфигурацию:**
   ```bash
   cp env_example.txt .env
   ```

## ⚙️ Настройка Google Cloud и Workspace

### 1. Создание сервисного аккаунта

1. Перейдите в [Google Cloud Console](https://console.cloud.google.com/)
2. Создайте новый проект или выберите существующий
3. Включите Gmail API:
   - Перейдите в "APIs & Services" → "Library"
   - Найдите "Gmail API" и включите его
4. Создайте сервисный аккаунт:
   - Перейдите в "IAM & Admin" → "Service Accounts"
   - Нажмите "Create Service Account"
   - Заполните название и описание
   - Скачайте JSON ключ

### 2. Настройка делегирования в Google Workspace

1. Перейдите в [Google Admin Console](https://admin.google.com/)
2. Откройте "Security" → "API controls" → "Domain-wide delegation"
3. Нажмите "Add new" и добавьте:
   - **Client ID**: из JSON файла сервисного аккаунта
   - **OAuth scopes**:
     ```
     https://www.googleapis.com/auth/gmail.readonly,https://www.googleapis.com/auth/gmail.insert,https://www.googleapis.com/auth/gmail.modify,https://www.googleapis.com/auth/gmail.labels
     ```

### 3. Конфигурация .env файла

Отредактируйте файл `.env`:

```env
# Путь к JSON файлу сервисного аккаунта
SERVICE_ACCOUNT_FILE=/path/to/your/service-account-key.json

# Ваш домен Google Workspace
WORKSPACE_DOMAIN=yourcompany.com

# Уровень логирования
LOG_LEVEL=INFO

# Настройки API
BATCH_SIZE=100
API_DELAY=0.1
```

## 🚀 Использование

### Основные команды

1. **Полный перенос почты:**
   ```bash
   python main.py old.employee@company.com new.employee@company.com
   ```

2. **Перенос только непрочитанных писем:**
   ```bash
   python main.py old.employee@company.com new.employee@company.com --query "is:unread"
   ```

3. **Ограничение количества писем:**
   ```bash
   python main.py old.employee@company.com new.employee@company.com --max-messages 1000
   ```

4. **Пробный запуск (без фактического переноса):**
   ```bash
   python main.py old.employee@company.com new.employee@company.com --dry-run
   ```

5. **Статистика почтового ящика:**
   ```bash
   python main.py --stats employee@company.com
   ```

### Дополнительные опции

- `--query "search"` - фильтр сообщений (Gmail Query Language)
- `--max-messages N` - максимальное количество сообщений
- `--no-transfer-label` - не создавать метку переноса
- `--dry-run` - пробный запуск без переноса
- `--stats EMAIL` - статистика почтового ящика

### Примеры поисковых запросов

```bash
# Только важные письма
--query "is:important"

# Письма от конкретного отправителя
--query "from:boss@company.com"

# Письма за последний месяц
--query "newer_than:1m"

# Письма с вложениями
--query "has:attachment"

# Комбинированный запрос
--query "is:unread has:attachment -in:spam"
```

## 📊 Логирование

Логи сохраняются в папке `logs/` с именами вида `gmail_transfer_YYYYMMDD.log`.

Уровни логирования:
- **DEBUG**: Детальная информация о каждой операции
- **INFO**: Общий прогресс и важные события  
- **WARNING**: Предупреждения о проблемах
- **ERROR**: Ошибки, которые не останавливают работу

## 🔒 Безопасность

- Храните JSON ключ сервисного аккаунта в безопасном месте
- Не коммитьте `.env` файл в репозиторий
- Регулярно ротируйте ключи сервисного аккаунта
- Используйте минимально необходимые права доступа

## ⚠️ Ограничения

- **Квоты API**: Gmail API имеет лимиты на количество запросов
- **Размер писем**: Очень большие письма могут вызывать проблемы
- **Системные метки**: Некоторые системные метки не переносятся
- **Порядок сообщений**: Порядок может отличаться от оригинального

## 🐛 Устранение неполадок

### Частые ошибки

1. **403 Forbidden**
   - Проверьте настройки делегирования в Google Workspace
   - Убедитесь, что сервисный аккаунт имеет необходимые права

2. **404 Not Found**
   - Проверьте корректность email адресов
   - Убедитесь, что пользователи существуют в вашем домене

3. **429 Too Many Requests**
   - Увеличьте `API_DELAY` в `.env` файле
   - Уменьшите `BATCH_SIZE`

4. **Ошибки импорта**
   - Некоторые сообщения могут иметь нестандартный формат
   - Проверьте логи для деталей

### Проверка настроек

```bash
# Проверьте, что сервисный аккаунт может получить доступ
python -c "from gmail_client import GmailClient; client = GmailClient(); print('✅ Подключение успешно')"

# Проверьте список меток пользователя
python main.py --stats user@yourcompany.com
```

## 📈 Производительность

При переносе больших объемов почты:

1. **Используйте фильтры** для переноса по частям
2. **Мониторьте квоты** API в Google Cloud Console
3. **Настройте задержки** между запросами
4. **Запускайте в tmux/screen** для долгих операций

## 🤝 Поддержка

При возникновении проблем:

1. Проверьте логи в папке `logs/`
2. Убедитесь в корректности настроек
3. Попробуйте пробный запуск с `--dry-run`
4. Проверьте права доступа в Google Workspace

## 📝 Лицензия

Этот проект предназначен для использования в корпоративных средах Google Workspace.
