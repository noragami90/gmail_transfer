# Gmail Transfer Tool - Production Dockerfile
FROM python:3.11-slim-bullseye

# Метаданные
LABEL maintainer="Gmail Transfer Tool"
LABEL version="1.0.0"
LABEL description="Professional Gmail transfer tool for Google Workspace"

# Переменные окружения
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    PORT=5000 \
    FLASK_ENV=production

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Создаем пользователя для безопасности
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Создаем рабочую директорию
WORKDIR /app

# Копируем файлы зависимостей
COPY requirements.txt web_requirements.txt ./

# Объединяем зависимости и устанавливаем
RUN cat requirements.txt web_requirements.txt > combined_requirements.txt && \
    pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r combined_requirements.txt && \
    rm combined_requirements.txt

# Копируем исходный код
COPY . .

# Копируем и настраиваем entrypoint
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Создаем необходимые директории
RUN mkdir -p logs static/css static/js templates && \
    chown -R appuser:appuser /app

# Переключаемся на непривилегированного пользователя
USER appuser

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:$PORT/api/health || exit 1

# Открываем порт
EXPOSE $PORT

# Entrypoint для настройки service account
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

# Команда запуска
CMD ["python", "app.py"]
