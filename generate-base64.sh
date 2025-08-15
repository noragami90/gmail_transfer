#!/bin/bash

# Скрипт для генерации base64 из service account файла

if [ ! -f "gmailtogmail-7aa3b4223cbe.json" ]; then
    echo "❌ Файл gmailtogmail-7aa3b4223cbe.json не найден!"
    echo "Поместите ваш service account файл в текущую директорию"
    exit 1
fi

echo "🔐 Генерация base64 из gmailtogmail-7aa3b4223cbe.json..."
echo ""

BASE64_CONTENT=$(base64 -i gmailtogmail-7aa3b4223cbe.json)

echo "✅ Base64 сгенерирован! Добавьте в .env файл:"
echo ""
echo "SERVICE_ACCOUNT_BASE64=$BASE64_CONTENT"
echo ""
echo "📋 Или скопируйте только значение:"
echo "$BASE64_CONTENT"
