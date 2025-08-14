# 🚀 Быстрый старт Gmail Transfer Tool

## Пошаговая инструкция для начала работы

### 1. Установка и настройка окружения

```bash
# Установите Python 3.7+ если не установлен
# Клонируйте/скачайте проект
cd gmail_transfer

# Запустите автоматическую установку
python setup.py

# Активируйте виртуальное окружение
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate     # Windows
```

### 2. Настройка Google Cloud (5 минут)

#### A. Создание проекта и сервисного аккаунта

1. Откройте [Google Cloud Console](https://console.cloud.google.com/)
2. Создайте новый проект
3. Перейдите в **"APIs & Services" → "Library"**
4. Найдите и включите **"Gmail API"**
5. Перейдите в **"IAM & Admin" → "Service Accounts"**
6. Нажмите **"Create Service Account"**:
   - Name: `gmail-transfer-service`
   - Description: `Service account for Gmail transfer tool`
7. Нажмите **"Create and Continue"**
8. Пропустите роли (нажмите **"Continue"**)
9. Нажмите **"Done"**
10. Кликните на созданный аккаунт
11. Перейдите на вкладку **"Keys"**
12. Нажмите **"Add Key" → "Create new key" → "JSON"**
13. Скачайте файл (например, `service-account-key.json`)

#### B. Получение Client ID

1. В созданном сервисном аккаунте скопируйте **"Unique ID"** (это ваш Client ID)

### 3. Настройка Google Workspace (3 минуты)

#### Добавление делегирования прав

1. Откройте [Google Admin Console](https://admin.google.com/)
2. Перейдите в **"Security" → "API controls" → "Domain-wide delegation"**
3. Нажмите **"Add new"**
4. Заполните:
   - **Client ID**: вставьте Unique ID из предыдущего шага
   - **OAuth scopes**: скопируйте это точно:
     ```
     https://www.googleapis.com/auth/gmail.readonly,https://www.googleapis.com/auth/gmail.insert,https://www.googleapis.com/auth/gmail.modify,https://www.googleapis.com/auth/gmail.labels
     ```
5. Нажмите **"Authorize"**

### 4. Настройка приложения (2 минуты)

```bash
# Отредактируйте .env файл
nano .env  # или любой другой редактор
```

Заполните `.env`:
```env
SERVICE_ACCOUNT_FILE=/full/path/to/your/service-account-key.json
WORKSPACE_DOMAIN=yourcompany.com
LOG_LEVEL=INFO
BATCH_SIZE=100
API_DELAY=0.1
```

### 5. Проверка настроек

```bash
# Тест подключения
python test_connection.py

# Тест доступа к конкретному пользователю
python test_connection.py user@yourcompany.com
```

### 6. Первый перенос

```bash
# Сначала пробный запуск
python main.py old.employee@company.com new.employee@company.com --dry-run

# Если все ОК, реальный перенос
python main.py old.employee@company.com new.employee@company.com
```

## ⚡ Частые команды

### Статистика пользователя
```bash
python main.py --stats user@company.com
```

### Перенос только непрочитанных
```bash
python main.py old@company.com new@company.com --query "is:unread"
```

### Перенос с ограничением
```bash
python main.py old@company.com new@company.com --max-messages 1000
```

### Перенос писем от конкретного отправителя
```bash
python main.py old@company.com new@company.com --query "from:boss@company.com"
```

## 🔧 Решение проблем

### Ошибка 403 Forbidden
- Проверьте делегирование в Google Admin Console
- Убедитесь, что скопировали правильный Client ID
- Проверьте OAuth scopes

### Ошибка 404 Not Found
- Проверьте правильность email адресов
- Убедитесь, что пользователи существуют в вашем домене

### Ошибки импорта Python модулей
```bash
# Убедитесь, что виртуальное окружение активировано
source venv/bin/activate
pip install -r requirements.txt
```

### Тестирование по шагам
```bash
# 1. Проверка аутентификации
python -c "from gmail_client import GmailClient; print('OK')"

# 2. Проверка доступа
python test_connection.py test.user@yourcompany.com

# 3. Статистика пользователя
python main.py --stats real.user@yourcompany.com
```

## 📞 Поддержка

- Проверьте файл `logs/gmail_transfer_YYYYMMDD.log` для деталей ошибок
- Используйте `--dry-run` для безопасного тестирования
- Начинайте с небольших переносов (`--max-messages 10`)

**🎉 Готово! Теперь вы можете переносить почту между сотрудниками!**
