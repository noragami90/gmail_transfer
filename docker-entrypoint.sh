#!/bin/bash
set -e

# Создаем папку logs если её нет
mkdir -p /app/logs

# Создаем service account файл из base64 переменной окружения
if [ -n "$SERVICE_ACCOUNT_BASE64" ]; then
    echo "Creating service account file from base64 environment variable..."
    echo "$SERVICE_ACCOUNT_BASE64" | base64 -d > /app/service-account-key.json
    export SERVICE_ACCOUNT_FILE="/app/service-account-key.json"
    echo "Service account file created successfully"
fi

# Создаем service account файл из JSON переменной окружения (для совместимости)
if [ -n "$SERVICE_ACCOUNT_JSON" ]; then
    echo "Creating service account file from JSON environment variable..."
    echo "$SERVICE_ACCOUNT_JSON" > /app/service-account-key.json
    export SERVICE_ACCOUNT_FILE="/app/service-account-key.json"
    echo "Service account file created successfully"
fi

# Проверяем наличие service account файла
if [ ! -f "$SERVICE_ACCOUNT_FILE" ]; then
    echo "Warning: Service account file not found at $SERVICE_ACCOUNT_FILE"
    echo "Please set one of:"
    echo "1. SERVICE_ACCOUNT_BASE64 - base64 encoded service account JSON (recommended for production)"
    echo "2. SERVICE_ACCOUNT_JSON - raw JSON content"
    echo "3. Mount file as volume: -v ./service-account-key.json:/app/service-account-key.json"
fi

# Запускаем приложение
exec "$@"
