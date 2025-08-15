# Gmail Transfer Tool - Makefile

.PHONY: help build run dev test clean lint format install docker-build docker-run docker-dev setup

# Цвета для вывода
BLUE=\033[0;34m
GREEN=\033[0;32m
YELLOW=\033[1;33m
RED=\033[0;31m
NC=\033[0m # No Color

# Переменные
IMAGE_NAME=gmail-transfer
DEV_IMAGE_NAME=gmail-transfer-dev
CONTAINER_NAME=gmail-transfer-app
VERSION=$(shell git describe --tags --always --dirty)

help: ## 📖 Показать справку
	@echo "$(BLUE)Gmail Transfer Tool - Команды разработки$(NC)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "$(GREEN)%-20s$(NC) %s\n", $$1, $$2}'

# Установка и настройка
install: ## 📦 Установить зависимости
	@echo "$(BLUE)Установка зависимостей...$(NC)"
	python -m pip install --upgrade pip
	pip install -r requirements.txt -r web_requirements.txt
	@echo "$(GREEN)✅ Зависимости установлены$(NC)"

setup: ## ⚙️ Первоначальная настройка проекта
	@echo "$(BLUE)Настройка проекта...$(NC)"
	python setup.py
	@echo "$(GREEN)✅ Проект настроен$(NC)"

venv: ## 🐍 Создать виртуальное окружение
	@echo "$(BLUE)Создание виртуального окружения...$(NC)"
	python -m venv venv
	@echo "$(YELLOW)Активируйте: source venv/bin/activate$(NC)"

# Разработка
dev: ## 🚀 Запустить в режиме разработки
	@echo "$(BLUE)Запуск в режиме разработки...$(NC)"
	export FLASK_ENV=development FLASK_DEBUG=1 && python app.py

cli: ## 💻 Запустить CLI версию
	@echo "$(BLUE)Запуск CLI версии...$(NC)"
	python main.py --help

test-connection: ## 🔍 Тестировать подключение к Gmail API
	@echo "$(BLUE)Тестирование подключения...$(NC)"
	python test_connection.py

# Тестирование
test: ## 🧪 Запустить тесты
	@echo "$(BLUE)Запуск тестов...$(NC)"
	pytest -v --cov=. --cov-report=html
	@echo "$(GREEN)✅ Тесты завершены$(NC)"

test-quick: ## ⚡ Быстрые тесты
	@echo "$(BLUE)Быстрые тесты...$(NC)"
	pytest -x -v
	@echo "$(GREEN)✅ Быстрые тесты завершены$(NC)"

# Качество кода
lint: ## 🧹 Проверить код линтером
	@echo "$(BLUE)Проверка кода...$(NC)"
	flake8 . --count --statistics
	@echo "$(GREEN)✅ Линтинг завершен$(NC)"

format: ## 🎨 Форматировать код
	@echo "$(BLUE)Форматирование кода...$(NC)"
	black .
	isort .
	@echo "$(GREEN)✅ Код отформатирован$(NC)"

format-check: ## 🔍 Проверить форматирование
	@echo "$(BLUE)Проверка форматирования...$(NC)"
	black --check .
	isort --check-only .
	@echo "$(GREEN)✅ Форматирование корректно$(NC)"

security: ## 🔒 Проверить безопасность
	@echo "$(BLUE)Проверка безопасности...$(NC)"
	bandit -r . -f json -o bandit-report.json
	safety check
	@echo "$(GREEN)✅ Проверка безопасности завершена$(NC)"

# Docker команды
docker-build: ## 🐳 Собрать Docker образ (production)
	@echo "$(BLUE)Сборка production образа...$(NC)"
	docker build -t $(IMAGE_NAME):$(VERSION) -t $(IMAGE_NAME):latest .
	@echo "$(GREEN)✅ Production образ собран$(NC)"

docker-build-dev: ## 🐳 Собрать Docker образ (development)
	@echo "$(BLUE)Сборка development образа...$(NC)"
	docker build -t $(DEV_IMAGE_NAME):$(VERSION) -t $(DEV_IMAGE_NAME):latest .
	@echo "$(GREEN)✅ Development образ собран$(NC)"

docker-run: ## 🚀 Запустить Docker контейнер (production)
	@echo "$(BLUE)Запуск production контейнера...$(NC)"
	docker run -d \
		--name $(CONTAINER_NAME) \
		-p 5000:5000 \
		-v $(PWD)/.env:/app/.env \
		-v $(PWD)/logs:/app/logs \
		$(IMAGE_NAME):latest
	@echo "$(GREEN)✅ Контейнер запущен на http://localhost:5000$(NC)"

docker-dev: ## 🔧 Запустить Docker контейнер (development)
	@echo "$(BLUE)Запуск development контейнера...$(NC)"
	docker run -it --rm \
		--name $(CONTAINER_NAME)-dev \
		-p 5000:5000 \
		-v $(PWD):/app \
		-v $(PWD)/.env:/app/.env \
		$(DEV_IMAGE_NAME):latest
	@echo "$(GREEN)✅ Development контейнер запущен$(NC)"

docker-stop: ## ⏹️ Остановить Docker контейнер
	@echo "$(BLUE)Остановка контейнера...$(NC)"
	docker stop $(CONTAINER_NAME) || true
	docker rm $(CONTAINER_NAME) || true
	@echo "$(GREEN)✅ Контейнер остановлен$(NC)"

docker-logs: ## 📋 Показать логи Docker контейнера
	@echo "$(BLUE)Логи контейнера:$(NC)"
	docker logs -f $(CONTAINER_NAME)

# Docker Compose команды
compose-up: ## 🚀 Запустить с docker-compose (production, готовые образы)
	@echo "$(BLUE)Запуск production с готовыми образами...$(NC)"
	docker-compose up -d
	@echo "$(GREEN)✅ Production сервисы запущены$(NC)"

compose-dev: ## 🔧 Запустить с docker-compose (development)
	@echo "$(BLUE)Запуск development окружения...$(NC)"
	docker-compose -f docker-compose.dev.yml up -d
	@echo "$(GREEN)✅ Development окружение запущено$(NC)"

compose-build: ## 🔨 Запустить development со сборкой
	@echo "$(BLUE)Запуск development со сборкой...$(NC)"
	docker-compose -f docker-compose.dev.yml up -d --build
	@echo "$(GREEN)✅ Development сервисы собраны и запущены$(NC)"

compose-down: ## ⏹️ Остановить docker-compose
	@echo "$(BLUE)Остановка сервисов...$(NC)"
	docker-compose down
	docker-compose -f docker-compose.dev.yml down
	@echo "$(GREEN)✅ Сервисы остановлены$(NC)"

compose-logs: ## 📋 Показать логи docker-compose
	@echo "$(BLUE)Логи сервисов:$(NC)"
	docker-compose logs -f

compose-pull: ## 📥 Обновить Docker образы
	@echo "$(BLUE)Обновление образов...$(NC)"
	docker-compose pull
	@echo "$(GREEN)✅ Образы обновлены$(NC)"



# Очистка
clean: ## 🧽 Очистить временные файлы
	@echo "$(BLUE)Очистка...$(NC)"
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type f -name "*.log" -delete
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -rf dist/
	rm -rf build/
	rm -rf *.egg-info/
	rm -f bandit-report.json
	rm -f safety-report.json
	@echo "$(GREEN)✅ Очистка завершена$(NC)"

clean-docker: ## 🐳 Очистить Docker образы и контейнеры
	@echo "$(BLUE)Очистка Docker...$(NC)"
	docker stop $(CONTAINER_NAME) $(CONTAINER_NAME)-dev 2>/dev/null || true
	docker rm $(CONTAINER_NAME) $(CONTAINER_NAME)-dev 2>/dev/null || true
	docker rmi $(IMAGE_NAME) $(DEV_IMAGE_NAME) 2>/dev/null || true
	docker system prune -f
	@echo "$(GREEN)✅ Docker очищен$(NC)"

# Проверки
health: ## 🏥 Проверить здоровье приложения
	@echo "$(BLUE)Проверка здоровья...$(NC)"
	curl -f http://localhost:5000/api/health || echo "$(RED)❌ Приложение недоступно$(NC)"

status: ## 📊 Показать статус сервисов
	@echo "$(BLUE)Статус сервисов:$(NC)"
	@echo "Docker контейнеры:"
	@docker ps -a --filter name=$(CONTAINER_NAME) --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" || echo "Нет контейнеров"
	@echo ""
	@echo "Docker Compose сервисы:"
	@docker-compose ps 2>/dev/null || echo "Docker Compose не запущен"

# Информация
info: ## ℹ️ Показать информацию о проекте
	@echo "$(BLUE)Информация о проекте:$(NC)"
	@echo "Версия: $(VERSION)"
	@echo "Git branch: $(shell git branch --show-current 2>/dev/null || echo 'unknown')"
	@echo "Git commit: $(shell git rev-parse --short HEAD 2>/dev/null || echo 'unknown')"
	@echo "Python version: $(shell python --version)"
	@echo "Docker version: $(shell docker --version 2>/dev/null || echo 'не установлен')"
	@echo "Docker Compose version: $(shell docker-compose --version 2>/dev/null || echo 'не установлен')"

# Быстрые команды для разработки
quick-setup: venv install setup ## ⚡ Быстрая настройка (venv + install + setup)

quick-test: format-check lint test ## ⚡ Быстрая проверка (format + lint + test)

quick-docker: docker-build docker-run ## ⚡ Быстрый Docker (build + run)

# Помощь по командам
commands: help ## 📋 Показать все команды (алиас для help)
