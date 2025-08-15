# Gmail Transfer Tool

Инструмент для переноса почты между сотрудниками в Google Workspace с веб-интерфейсом, историей переносов и возможностью массовых операций.

## 🚀 Возможности

### ✉️ Перенос почты
- **Одиночный перенос** между двумя пользователями
- **Массовый перенос** десятков ящиков одновременно
- **Фильтрация** сообщений по дате, отправителю, теме, вложениям
- **Лимиты** на количество переносимых сообщений
- **Real-time прогресс** с WebSocket обновлениями

### 📊 История и отчетность
- **База данных** всех переносов с детальной статистикой
- **Фильтрация и поиск** по истории переносов
- **Статистика** успешных/неудачных операций
- **Топ источников** переносов

### 🎯 Веб-интерфейс
- **Современный UI** с Bootstrap 5
- **Адаптивный дизайн** для мобильных устройств
- **Живые обновления** прогресса переносов
- **Валидация** входных данных

## 📋 Требования

- Google Workspace админ аккаунт
- Service Account с domain-wide delegation
- Docker и Docker Compose

## ⚡ Быстрый старт

### 1. Настройка Google Cloud

1. Создайте проект в [Google Cloud Console](https://console.cloud.google.com/)
2. Включите Gmail API
3. Создайте Service Account и скачайте JSON ключ
4. Настройте domain-wide delegation в Google Admin Console

**Настройка делегирования:**
- Откройте [Google Admin Console](https://admin.google.com/)
- Перейдите в Security → API controls → Domain-wide delegation
- Добавьте Client ID из JSON файла
- Укажите OAuth scopes:
  ```
  https://www.googleapis.com/auth/gmail.readonly,https://www.googleapis.com/auth/gmail.insert,https://www.googleapis.com/auth/gmail.modify,https://www.googleapis.com/auth/gmail.labels
  ```

### 2. Установка

```bash
# Клонируйте репозиторий
git clone https://github.com/noragami90/gmail_transfer.git
cd gmail_transfer

# Создайте необходимые файлы
cp env_example.txt .env
cp your-service-account.json service-account-key.json

# Отредактируйте .env файл
nano .env
```

### 3. Запуск

**Продакшен (готовый образ):**
```bash
docker-compose up -d
```

**Разработка (локальная сборка):**
```bash
docker-compose -f docker-compose.dev.yml up -d --build
```

### 4. Использование

- **Продакшен**: http://localhost:5000
- **Разработка**: http://localhost:5001

## 📖 Использование

### Одиночный перенос

1. Откройте главную страницу
2. Введите email исходного и целевого сотрудника
3. Настройте фильтры (опционально)
4. Нажмите "Начать перенос"

### Массовый перенос

1. Перейдите на страницу "Массовый перенос"
2. Введите название операции
3. Заполните список переносов в формате:
   ```
   old1@company.com -> new1@company.com
   old2@company.com -> new2@company.com after:2024/01/01
   old3@company.com -> new3@company.com has:attachment max:1000
   # Комментарии поддерживаются
   ```
4. Выберите количество параллельных переносов
5. Запустите массовый перенос

### Фильтры Gmail

Поддерживаются все стандартные фильтры Gmail:
- `after:2024/01/01` - сообщения после даты
- `before:2024/12/31` - сообщения до даты  
- `from:boss@company.com` - от конкретного отправителя
- `to:team@company.com` - к конкретному получателю
- `subject:urgent` - по теме сообщения
- `has:attachment` - только с вложениями
- `is:important` - важные сообщения
- `label:work` - с определенной меткой

## 🔧 Конфигурация

### Environment переменные (.env)

```bash
# Service Account (обязательно)
SERVICE_ACCOUNT_FILE=/app/service-account-key.json

# Redis (опционально)  
REDIS_PASSWORD=your_redis_password

# Дополнительные настройки
MAX_MESSAGES_DEFAULT=10000
CONCURRENT_WORKERS=3
```

### Docker Compose

**Продакшен** (`docker-compose.yml`):
- Использует готовый образ `ghcr.io/noragami90/gmail_transfer:latest`
- Порт 5000
- Persistent данные в volumes

**Разработка** (`docker-compose.dev.yml`):
- Собирает образ локально
- Порт 5001  
- Hot reload кода

## 📊 API

### Основные эндпоинты

```
GET  /                          - Главная страница
GET  /bulk                      - Массовый перенос
GET  /history                   - История переносов

POST /api/start-transfer        - Запуск переноса
POST /api/bulk-transfer/create  - Создание массового переноса
POST /api/bulk-transfer/start   - Запуск массового переноса
GET  /api/transfers/history     - История переносов
GET  /api/transfers/stats       - Статистика переносов
```

### WebSocket события

```javascript
// Подключение к прогрессу переноса
socket.emit('join_task', { task_id: 'your-task-id' });

// Подключение к массовому переносу  
socket.emit('join_bulk_task', { bulk_id: 'your-bulk-id' });

// События прогресса
socket.on('transfer_progress', (data) => { ... });
socket.on('bulk_transfer_progress', (data) => { ... });
```

## 🔒 Безопасность

- Service Account файлы монтируются read-only
- Redis с паролем
- Валидация всех входных данных
- Логирование всех операций
- Healthcheck для контейнеров

## 🐛 Отладка

### Просмотр логов

```bash
# Все логи
docker-compose logs -f

# Только приложение
docker-compose logs -f gmail-transfer

# Последние 100 строк
docker-compose logs --tail=100 gmail-transfer
```

### Проверка здоровья

```bash
curl http://localhost:5000/api/health
```

### Подключение к Redis

```bash
docker-compose exec redis redis-cli
```

## 🛠️ Разработка

### Структура проекта

```
├── app.py              # Основное Flask приложение
├── email_transfer.py   # Логика переноса почты
├── gmail_client.py     # Gmail API клиент
├── database.py         # SQLite база данных
├── bulk_transfer.py    # Массовые переносы
├── logger.py          # Настройка логирования
├── templates/         # HTML шаблоны
├── static/           # CSS/JS файлы
├── data/             # База данных SQLite
└── logs/             # Файлы логов
```

### Локальная разработка

```bash
# Сборка и запуск dev версии
docker-compose -f docker-compose.dev.yml up -d --build

# Пересборка после изменений
docker-compose -f docker-compose.dev.yml up -d --build --force-recreate
```

## 📈 Мониторинг

- Логи в папке `./logs`
- База данных в `./data/transfers.db`
- Метрики через API `/api/transfers/stats`
- Healthcheck endpoint `/api/health`

## 🤝 Поддержка

При возникновении проблем:

1. Проверьте логи: `docker-compose logs gmail-transfer`
2. Убедитесь в правильности настройки Service Account
3. Проверьте делегирование в Google Admin Console
4. Включен ли Gmail API в проекте

## 📝 Лицензия

MIT License - используйте свободно для личных и коммерческих проектов.