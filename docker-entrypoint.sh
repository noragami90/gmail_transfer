#!/bin/bash
set -e

# Создаем service account файл из переменной окружения если он передан
if [ -n "$SERVICE_ACCOUNT_JSON" ]; then
    echo "Creating service account file from environment variable..."
    echo "$SERVICE_ACCOUNT_JSON" > /app/service-account-key.json
    export SERVICE_ACCOUNT_FILE="/app/service-account-key.json"
fi

# Проверяем Docker Secrets
if [ -f "/run/secrets/service_account" ]; then
    echo "Using service account from Docker Secrets..."
    export SERVICE_ACCOUNT_FILE="/run/secrets/service_account"
fi

# Проверяем наличие service account файла
if [ ! -f "$SERVICE_ACCOUNT_FILE" ]; then
    echo "Warning: Service account file not found at $SERVICE_ACCOUNT_FILE"
    echo "Please:"
    echo "1. Mount the file as volume: -v ./service-account-key.json:/app/service-account-key.json"
    echo "2. Use Docker Secrets (recommended for production)"
    echo "3. Set SERVICE_ACCOUNT_JSON environment variable"
fi

# Запускаем приложение
exec "$@"
