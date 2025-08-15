// Gmail Transfer Tool - Main JavaScript

class GmailTransferApp {
    constructor() {
        this.socket = null;
        this.currentTaskId = null;
        this.lastUpdate = Date.now();
        
        this.init();
    }
    
    init() {
        console.log('=== ИНИЦИАЛИЗАЦИЯ ПРИЛОЖЕНИЯ ===');
        this.setupSocketIO();
        this.bindEvents();
        this.checkHealth();
        this.loadRecentTransfers();
        
        // Добавляем небольшую задержку для полной загрузки DOM
        setTimeout(() => {
            console.log('=== ЗАПУСК ВОССТАНОВЛЕНИЯ ПРОГРЕССА ===');
            this.restoreProgressIfNeeded();
        }, 100);
    }
    
    setupSocketIO() {
        // Инициализация Socket.IO
        this.socket = io();
        
        this.socket.on('connect', () => {
            console.log('Connected to server');
            this.updateConnectionStatus('connected');
        });
        
        this.socket.on('disconnect', () => {
            console.log('Disconnected from server');
            this.updateConnectionStatus('disconnected');
        });
        
        this.socket.on('transfer_progress', (data) => {
            this.updateProgress(data.progress);
        });
        
        this.socket.on('transfer_status', (data) => {
            this.updateStatus(data.status, data.message);
        });
        
        this.socket.on('transfer_error', (data) => {
            this.showError('Ошибка переноса', data.error);
            this.hideProgress();
        });
    }
    
    bindEvents() {
        // Форма переноса
        document.getElementById('transferForm').addEventListener('submit', (e) => {
            e.preventDefault();
            this.startTransfer();
        });
        
        // Кнопки тестирования подключения
        document.getElementById('testSourceBtn').addEventListener('click', () => {
            this.testConnection('source');
        });
        
        document.getElementById('testTargetBtn').addEventListener('click', () => {
            this.testTargetEmail();
        });
        
        // Предварительный просмотр
        document.getElementById('previewBtn').addEventListener('click', () => {
            this.showPreview();
        });
        
        // Отмена переноса
        document.getElementById('cancelBtn').addEventListener('click', () => {
            this.cancelTransfer();
        });

        // Кнопка восстановления прогресса
        document.getElementById('restoreProgressBtn').addEventListener('click', () => {
            console.log('🔄 Принудительное восстановление прогресса...');
            this.restoreProgressIfNeeded();
        });
        
        // Обновление статистики
        document.getElementById('refreshStatsBtn').addEventListener('click', () => {
            this.refreshStats();
        });
        
        // Кнопка сброса кэша (если есть)
        const clearCacheBtn = document.getElementById('clearCacheBtn');
        if (clearCacheBtn) {
            clearCacheBtn.addEventListener('click', () => {
                this.clearCache();
            });
        }
        
        // Автоматическое обновление статистики при вводе email
        document.getElementById('sourceEmail').addEventListener('blur', () => {
            this.loadUserStats('source');
        });
        
        document.getElementById('targetEmail').addEventListener('blur', () => {
            this.loadUserStats('target');
        });
    }
    
    async checkHealth() {
        try {
            const response = await fetch('/api/health');
            const data = await response.json();
            
            if (response.ok && data.status === 'healthy') {
                this.updateConnectionStatus('healthy');
            } else {
                this.updateConnectionStatus('unhealthy');
            }
        } catch (error) {
            console.error('Health check failed:', error);
            this.updateConnectionStatus('error');
        }
    }
    
    updateConnectionStatus(status) {
        const indicator = document.getElementById('statusIndicator');
        const icon = indicator.querySelector('i');
        
        icon.className = 'bi bi-circle-fill me-1';
        
        switch (status) {
            case 'healthy':
            case 'connected':
                icon.classList.add('text-success');
                indicator.innerHTML = '<i class="bi bi-circle-fill text-success me-1"></i>Подключено';
                break;
            case 'unhealthy':
            case 'disconnected':
                icon.classList.add('text-warning');
                indicator.innerHTML = '<i class="bi bi-circle-fill text-warning me-1"></i>Отключено';
                break;
            case 'error':
                icon.classList.add('text-danger');
                indicator.innerHTML = '<i class="bi bi-circle-fill text-danger me-1"></i>Ошибка';
                break;
        }
    }
    
    async testConnection(type) {
        const emailInput = document.getElementById(type === 'source' ? 'sourceEmail' : 'targetEmail');
        const button = document.getElementById(type === 'source' ? 'testSourceBtn' : 'testTargetBtn');
        const email = emailInput.value.trim();
        
        if (!email) {
            this.showAlert('warning', 'Введите email адрес для проверки');
            return;
        }
        
        // Показываем загрузку
        button.innerHTML = '<i class="bi bi-arrow-clockwise spin"></i>';
        button.disabled = true;
        
        try {
            const response = await fetch('/api/test-connection', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email })
            });
            
            const data = await response.json();
            
            if (response.ok && data.accessible) {
                button.innerHTML = '<i class="bi bi-check-circle text-success"></i>';
                this.showAlert('success', `Подключение к ${email} успешно`);
                
                // Загружаем статистику только для исходного email
                if (type === 'source') {
                    this.loadUserStats(type);
                }
            } else {
                button.innerHTML = '<i class="bi bi-x-circle text-danger"></i>';
                this.showAlert('danger', `Ошибка подключения к ${email}: ${data.error}`);
            }
        } catch (error) {
            button.innerHTML = '<i class="bi bi-x-circle text-danger"></i>';
            this.showAlert('danger', `Ошибка: ${error.message}`);
        } finally {
            button.disabled = false;
        }
    }
    
    async loadUserStats(type) {
        const email = document.getElementById(type === 'source' ? 'sourceEmail' : 'targetEmail').value.trim();
        const query = document.getElementById('queryFilter').value.trim();
        
        if (!email) return;
        
        try {
            const response = await fetch('/api/user-stats', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, query })
            });
            
            const data = await response.json();
            
            if (response.ok) {
                this.updateUserStats(type, data);
            }
        } catch (error) {
            console.error('Failed to load user stats:', error);
        }
    }
    
    updateUserStats(type, stats) {
        const container = document.getElementById(`${type}Stats`);
        const totalElement = document.getElementById(`${type}Total`);
        const labelsElement = document.getElementById(`${type}Labels`);
        const statusElement = document.getElementById(`${type}Status`);
        
        totalElement.textContent = stats.total_messages.toLocaleString();
        labelsElement.textContent = stats.labels_count;
        statusElement.className = 'badge bg-success';
        statusElement.textContent = '✓ Доступен';
        
        container.style.display = 'block';
        container.classList.add('slide-in-up');
    }
    
    async testTargetEmail() {
        const emailInput = document.getElementById('targetEmail');
        const button = document.getElementById('testTargetBtn');
        const email = emailInput.value.trim();
        
        if (!email) {
            this.showAlert('warning', 'Введите email адрес для проверки');
            return;
        }
        
        // Показываем загрузку
        button.innerHTML = '<i class="bi bi-arrow-clockwise spin"></i>';
        button.disabled = true;
        
        try {
            const response = await fetch('/api/test-connection', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email })
            });
            
            const data = await response.json();
            
            if (response.ok && data.accessible) {
                button.innerHTML = '<i class="bi bi-check-circle text-success"></i>';
                this.showAlert('success', `Подключение к ${email} успешно`);
            } else {
                button.innerHTML = '<i class="bi bi-x-circle text-danger"></i>';
                this.showAlert('danger', `Ошибка подключения к ${email}: ${data.error}`);
            }
        } catch (error) {
            button.innerHTML = '<i class="bi bi-x-circle text-danger"></i>';
            this.showAlert('danger', 'Ошибка проверки подключения');
            console.error('Connection test failed:', error);
        } finally {
            setTimeout(() => {
                button.innerHTML = '<i class="bi bi-check-circle"></i>';
                button.disabled = false;
            }, 2000);
        }
    }
    

    
    async showPreview() {
        const sourceEmail = document.getElementById('sourceEmail').value.trim();
        const query = document.getElementById('queryFilter').value.trim();
        const maxMessages = document.getElementById('maxMessages').value;
        
        if (!sourceEmail) {
            this.showAlert('warning', 'Введите email исходного пользователя');
            return;
        }
        
        this.showLoading('Анализ сообщений...', 'Подсчитываем количество сообщений для переноса');
        
        try {
            const response = await fetch('/api/user-stats', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    email: sourceEmail, 
                    query: query || '' 
                })
            });
            
            const data = await response.json();
            
            if (response.ok) {
                const total = maxMessages ? Math.min(data.total_messages, parseInt(maxMessages)) : data.total_messages;
                
                this.hideLoading();
                
                const message = `
                    <strong>Предварительный просмотр переноса:</strong><br>
                    • Исходный пользователь: ${sourceEmail}<br>
                    • Фильтр: ${query || 'все сообщения'}<br>
                    • Сообщений к переносу: ${total.toLocaleString()}<br>
                    • Общее количество меток: ${data.labels_count}
                `;
                
                this.showAlert('info', message);
            } else {
                this.hideLoading();
                this.showAlert('danger', `Ошибка анализа: ${data.error}`);
            }
        } catch (error) {
            this.hideLoading();
            this.showAlert('danger', `Ошибка: ${error.message}`);
        }
    }
    
    async startTransfer() {
        const sourceEmail = document.getElementById('sourceEmail').value.trim();
        const targetEmail = document.getElementById('targetEmail').value.trim();
        const query = document.getElementById('queryFilter').value.trim();
        const maxMessages = document.getElementById('maxMessages').value;
        const createLabel = document.getElementById('createLabel').checked;
        
        if (!sourceEmail || !targetEmail) {
            this.showAlert('warning', 'Введите email адреса исходного и целевого пользователей');
            return;
        }
        
        if (sourceEmail === targetEmail) {
            this.showAlert('warning', 'Email адреса исходного и целевого пользователей должны отличаться');
            return;
        }
        
        // Подтверждение
        const confirmMessage = `Вы уверены, что хотите перенести почту от ${sourceEmail} к ${targetEmail}?`;
        if (!confirm(confirmMessage)) {
            return;
        }
        
        this.showLoading('Запуск переноса...', 'Инициализация процесса переноса');
        
        try {
            const response = await fetch('/api/start-transfer', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    source_email: sourceEmail,
                    target_email: targetEmail,
                    query: query,
                    max_messages: maxMessages ? parseInt(maxMessages) : null,
                    create_transfer_label: createLabel
                })
            });
            
            const data = await response.json();
            
            if (response.ok) {
                this.currentTaskId = data.task_id;
                this.hideLoading();
                this.showProgress();
                
                // Присоединяемся к комнате задачи для получения обновлений
                this.socket.emit('join_task', { task_id: this.currentTaskId });
                
                // Добавляем в недавние операции
                this.addRecentTransfer({
                    id: this.currentTaskId,
                    source: sourceEmail,
                    target: targetEmail,
                    status: 'running',
                    start_time: new Date().toISOString()
                });
                
            } else {
                this.hideLoading();
                this.showAlert('danger', `Ошибка запуска переноса: ${data.error}`);
            }
        } catch (error) {
            this.hideLoading();
            this.showAlert('danger', `Ошибка: ${error.message}`);
        }
    }
    
    async cancelTransfer() {
        if (!this.currentTaskId) return;
        
        if (!confirm('Вы уверены, что хотите отменить перенос?')) {
            return;
        }
        
        try {
            const response = await fetch('/api/cancel-transfer', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ task_id: this.currentTaskId })
            });
            
            if (response.ok) {
                this.showAlert('warning', 'Перенос отменен');
                this.hideProgress();
            }
        } catch (error) {
            this.showAlert('danger', `Ошибка отмены: ${error.message}`);
        }
    }
    
    showProgress() {
        console.log('🎭 Показываем окно прогресса...');
        const progressCard = document.getElementById('progressCard');
        
        if (progressCard) {
            console.log('✅ Карточка прогресса найдена, показываем...');
            progressCard.style.display = 'block';
            progressCard.classList.add('slide-in-up');
            
            // Принудительно делаем видимой
            progressCard.style.visibility = 'visible';
            progressCard.style.opacity = '1';
            
            // Прокручиваем к прогрессу
            progressCard.scrollIntoView({ behavior: 'smooth' });
            
            console.log('✅ Карточка прогресса отображена');
        } else {
            console.error('❌ Карточка прогресса не найдена!');
        }
        
        // Запускаем полинг статуса как резерв для WebSocket
        if (this.currentTaskId) {
            console.log('🔄 Запускаем полинг для задачи:', this.currentTaskId);
            this.startStatusPolling(this.currentTaskId);
        }
    }
    
    startStatusPolling(taskId) {
        let noProgressCount = 0;
        this.statusPollingInterval = setInterval(async () => {
            try {
                const response = await fetch(`/api/task-status/${taskId}`);
                const data = await response.json();
                
                if (data.status === 'completed') {
                    clearInterval(this.statusPollingInterval);
                    this.hideProgress();
                    // Уведомление показывается в updateStatus, не дублируем
                } else if (data.status === 'not_found') {
                    clearInterval(this.statusPollingInterval);
                    this.hideProgress();
                    this.showAlert('warning', 'Задача не найдена');
                } else if (data.status === 'running') {
                    // Скрываем модальное окно, если оно еще показано
                    const loadingModal = document.getElementById('loadingModal');
                    if (loadingModal && loadingModal.classList.contains('show')) {
                        this.hideLoading();
                        this.showProgress();
                    }
                    
                    // ВСЕГДА обновляем прогресс из API данных
                    if (data.progress) {
                        const total = data.progress.total || 0;
                        const transferred = data.progress.transferred || 0;
                        const errors = data.progress.errors || 0;
                        
                        console.log('API Progress Update:', data.progress);
                        console.log('Extracted values:', { total, transferred, errors });
                        
                        // Используем полную структуру данных для обновления
                        this.updateProgress(data.progress);
                    }
                }
            } catch (error) {
                console.error('Ошибка полинга статуса:', error);
            }
        }, 2000); // Проверяем каждые 2 секунды
    }
    
    hideProgress() {
        const progressCard = document.getElementById('progressCard');
        progressCard.style.display = 'none';
        this.currentTaskId = null;
        
        // Останавливаем полинг
        if (this.statusPollingInterval) {
            clearInterval(this.statusPollingInterval);
            this.statusPollingInterval = null;
        }
    }
    
    updateProgress(progress) {
        console.log('updateProgress called with:', progress);
        
        const total = progress.total || 0;
        const transferred = progress.transferred || 0;
        const errors = progress.errors || 0;
        
        // Обновляем основные числа
        document.getElementById('totalMessages').textContent = total.toLocaleString();
        document.getElementById('transferredMessages').textContent = transferred.toLocaleString();
        document.getElementById('errorMessages').textContent = errors.toLocaleString();
        
        // Рассчитываем процент
        const percentage = total > 0 ? Math.round((transferred / total) * 100) : 0;
        const progressBar = document.getElementById('progressBar');
        const progressPercentage = document.getElementById('progressPercentage');
        const progressText = document.getElementById('progressText');
        
        if (progressBar) {
            progressBar.style.width = `${percentage}%`;
        }
        if (progressPercentage) {
            progressPercentage.textContent = `${percentage}%`;
        }
        if (progressText) {
            progressText.textContent = `${transferred} из ${total} сообщений`;
        }
        
        // Время выполнения
        const elapsed = Math.round(progress.elapsed_time || 0);
        const elapsedMinutes = Math.floor(elapsed / 60);
        const elapsedSeconds = elapsed % 60;
        const elapsedElement = document.getElementById('elapsedTime');
        if (elapsedElement) {
            elapsedElement.textContent = `${elapsedMinutes}:${elapsedSeconds.toString().padStart(2, '0')}`;
        }
        
        // Оставшееся время
        const remaining = Math.round(progress.estimated_remaining || 0);
        const remainingMinutes = Math.floor(remaining / 60);
        const remainingSeconds = remaining % 60;
        const remainingElement = document.getElementById('timeRemaining');
        if (remainingElement) {
            remainingElement.textContent = remaining > 0 ? `${remainingMinutes}:${remainingSeconds.toString().padStart(2, '0')}` : '--:--';
        }
        
        // Скорость переноса
        const speed = progress.messages_per_minute || 0;
        const speedElement = document.getElementById('transferSpeed');
        if (speedElement) {
            speedElement.textContent = speed > 0 ? `${speed} сообщ/мин` : '-- сообщ/мин';
        }
        
        // Обновляем заголовок прогресса
        const progressTitle = document.getElementById('progressTitle');
        if (progressTitle) {
            if (total > 0 && transferred > 0) {
                progressTitle.textContent = 'Перенос в процессе...';
            } else if (total > 0) {
                progressTitle.textContent = 'Начинаем перенос...';
            } else {
                progressTitle.textContent = 'Анализ сообщений...';
            }
        }
        
        // Сохраняем состояние в localStorage для восстановления после перезагрузки
        if (this.currentTaskId) {
            localStorage.setItem('currentTransfer', JSON.stringify({
                taskId: this.currentTaskId,
                progress: progress,
                timestamp: Date.now()
            }));
        }
    }
    
    restoreProgressIfNeeded() {
        // Восстанавливаем прогресс после перезагрузки страницы
        console.log('🔄 Начинаем восстановление прогресса...');
        
        try {
            // Сначала проверяем localStorage
            const savedTransfer = localStorage.getItem('currentTransfer');
            console.log('💾 Данные в localStorage:', savedTransfer);
            
            // Затем проверяем активные задачи на сервере
            console.log('🌐 Проверяем активные задачи на сервере...');
            fetch('/api/active-tasks')
                .then(response => {
                    console.log('📡 Ответ сервера:', response.status);
                    return response.json();
                })
                .then(data => {
                    console.log('📊 Активные задачи:', data);
                    
                    if (data.active_tasks && data.active_tasks.length > 0) {
                        // Есть активные задачи, восстанавливаем первую
                        const activeTask = data.active_tasks[0];
                        console.log('✅ Найдена активная задача:', activeTask);
                        
                        this.currentTaskId = activeTask.task_id;
                        console.log('🎯 Восстанавливаем задачу:', this.currentTaskId);
                        
                        this.showProgress();
                        
                        // Присоединяемся к комнате задачи
                        this.socket.emit('join_task', { task_id: this.currentTaskId });
                        
                        // Запускаем полинг
                        this.startStatusPolling(this.currentTaskId);
                        
                        // Показываем прогресс если есть
                        if (activeTask.progress && Object.keys(activeTask.progress).length > 0) {
                            console.log('📈 Восстанавливаем прогресс:', activeTask.progress);
                            this.updateProgress(activeTask.progress);
                        }
                        
                        this.showAlert('info', 'Восстановлен прогресс активного переноса');
                        return;
                    }
                    
                    console.log('❌ Нет активных задач на сервере');
                    // Нет активных задач, проверяем localStorage
                    this.checkLocalStorageRestore();
                })
                .catch(error => {
                    console.error('❌ Ошибка проверки активных задач:', error);
                    // Fallback к localStorage
                    this.checkLocalStorageRestore();
                });
        } catch (error) {
            console.error('❌ Критическая ошибка восстановления прогресса:', error);
            localStorage.removeItem('currentTransfer');
        }
    }
    
    checkLocalStorageRestore() {
        console.log('💾 Проверяем localStorage для восстановления...');
        
        try {
            const savedTransfer = localStorage.getItem('currentTransfer');
            if (savedTransfer) {
                console.log('📦 Найдены сохраненные данные:', savedTransfer);
                const transferData = JSON.parse(savedTransfer);
                const timeSinceUpdate = Date.now() - transferData.timestamp;
                
                console.log(`⏰ Время с последнего обновления: ${Math.round(timeSinceUpdate / 1000)} секунд`);
                
                // Если прошло менее 5 минут, восстанавливаем прогресс
                if (timeSinceUpdate < 300000) {
                    console.log('✅ Данные актуальны, восстанавливаем...');
                    this.currentTaskId = transferData.taskId;
                    
                    // Проверяем статус задачи
                    fetch(`/api/task-status/${this.currentTaskId}`)
                        .then(response => response.json())
                        .then(data => {
                            console.log('Статус задачи при восстановлении:', data);
                            
                            if (data.status === 'running') {
                                console.log('Восстанавливаем прогресс активного переноса:', this.currentTaskId);
                                this.showProgress();
                                
                                // Присоединяемся к комнате задачи
                                this.socket.emit('join_task', { task_id: this.currentTaskId });
                                
                                // Запускаем полинг
                                this.startStatusPolling(this.currentTaskId);
                                
                                // Показываем последний известный прогресс
                                if (transferData.progress) {
                                    this.updateProgress(transferData.progress);
                                }
                                
                                this.showAlert('info', 'Восстановлен прогресс активного переноса');
                            } else if (data.status === 'completed') {
                                // Показываем завершенный перенос на короткое время
                                console.log('Показываем завершенный перенос:', this.currentTaskId);
                                this.showProgress();
                                
                                // Показываем финальный прогресс
                                if (data.result) {
                                    const finalProgress = {
                                        total: data.result.total || 0,
                                        transferred: data.result.transferred || 0,
                                        errors: data.result.errors || 0,
                                        percentage: 100,
                                        elapsed_time: transferData.progress?.elapsed_time || 0,
                                        estimated_remaining: 0,
                                        messages_per_minute: transferData.progress?.messages_per_minute || 0
                                    };
                                    this.updateProgress(finalProgress);
                                }
                                
                                // Обновляем заголовок
                                const progressTitle = document.getElementById('progressTitle');
                                if (progressTitle) {
                                    progressTitle.textContent = 'Перенос завершен успешно!';
                                }
                                
                                this.showAlert('success', 'Перенос был завершен во время отсутствия');
                                
                                // Скрываем через 5 секунд
                                setTimeout(() => {
                                    this.hideProgress();
                                    localStorage.removeItem('currentTransfer');
                                }, 5000);
                            } else {
                                // Задача не найдена или ошибка, очищаем данные
                                console.log('Задача не найдена или завершена с ошибкой');
                                localStorage.removeItem('currentTransfer');
                            }
                        })
                        .catch(error => {
                            console.error('Ошибка восстановления прогресса:', error);
                            localStorage.removeItem('currentTransfer');
                        });
                } else {
                    // Данные устарели, удаляем
                    localStorage.removeItem('currentTransfer');
                }
            }
        } catch (error) {
            console.error('Ошибка восстановления прогресса:', error);
            localStorage.removeItem('currentTransfer');
        }
    }
    
    updateStatus(status, message) {
        const title = document.getElementById('progressTitle');
        title.textContent = message;
        
        if (status === 'completed') {
            // Очищаем сохраненное состояние
            localStorage.removeItem('currentTransfer');
            
            setTimeout(() => {
                this.hideProgress();
                this.showAlert('success', 'Перенос успешно завершен!');
                this.loadRecentTransfers();
            }, 3000);
        } else if (status === 'error' || status === 'cancelled') {
            // Очищаем сохраненное состояние при ошибке
            localStorage.removeItem('currentTransfer');
        }
    }
    
    async refreshStats() {
        // Очищаем кэш перед обновлением
        await this.clearCache();
        
        this.loadUserStats('source');
        this.loadUserStats('target');
        this.showAlert('info', 'Статистика обновлена');
    }
    
    async clearCache() {
        try {
            const response = await fetch('/api/clear-cache', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({})
            });
            
            if (response.ok) {
                console.log('Кэш статистики очищен');
            }
        } catch (error) {
            console.error('Ошибка очистки кэша:', error);
        }
    }
    
    showAlert(type, message) {
        const alertContainer = document.getElementById('alertContainer');
        
        // Ограничиваем количество уведомлений (максимум 3)
        const existingAlerts = alertContainer.querySelectorAll('.alert');
        if (existingAlerts.length >= 3) {
            // Удаляем самое старое уведомление
            existingAlerts[0].remove();
        }
        
        const alertId = 'alert-' + Date.now();
        
        const alertHtml = `
            <div class="alert alert-${type} alert-dismissible fade show slide-in-up" role="alert" id="${alertId}">
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;
        
        alertContainer.insertAdjacentHTML('beforeend', alertHtml);
        
        // Автоматическое скрытие через 5 секунд
        setTimeout(() => {
            const alert = document.getElementById(alertId);
            if (alert) {
                const bsAlert = new bootstrap.Alert(alert);
                bsAlert.close();
            }
        }, 5000);
    }
    
    showError(title, message) {
        this.showAlert('danger', `<strong>${title}:</strong> ${message}`);
    }
    
    showLoading(title, text) {
        document.getElementById('loadingModalTitle').textContent = title;
        document.getElementById('loadingModalText').textContent = text;
        
        const modal = new bootstrap.Modal(document.getElementById('loadingModal'));
        modal.show();
    }
    
    hideLoading() {
        const modalElement = document.getElementById('loadingModal');
        const modal = bootstrap.Modal.getInstance(modalElement);
        if (modal) {
            modal.hide();
        } else {
            // Принудительное скрытие, если Bootstrap не инициализирован
            modalElement.style.display = 'none';
            modalElement.classList.remove('show');
            document.body.classList.remove('modal-open');
            
            // Убираем backdrop
            const backdrop = document.querySelector('.modal-backdrop');
            if (backdrop) {
                backdrop.remove();
            }
        }
    }
    
    addRecentTransfer(transfer) {
        const container = document.getElementById('recentTransfers');
        
        // Очищаем пустое сообщение при первом добавлении
        if (container.children.length === 1 && container.children[0].querySelector('.bi-inbox')) {
            container.innerHTML = '';
        }
        
        const transferHtml = `
            <div class="transfer-item ${transfer.status} slide-in-up">
                <div class="d-flex justify-content-between align-items-start">
                    <div>
                        <div class="fw-semibold">${transfer.source} → ${transfer.target}</div>
                        <small class="text-muted">${new Date(transfer.start_time).toLocaleString()}</small>
                    </div>
                    <span class="badge bg-${this.getStatusColor(transfer.status)}">${this.getStatusText(transfer.status)}</span>
                </div>
            </div>
        `;
        
        container.insertAdjacentHTML('afterbegin', transferHtml);
        
        // Ограничиваем количество записей
        const items = container.children;
        if (items.length > 5) {
            container.removeChild(items[items.length - 1]);
        }
    }
    
    getStatusColor(status) {
        switch (status) {
            case 'completed': return 'success';
            case 'error': return 'danger';
            case 'running': return 'primary';
            case 'cancelled': return 'warning';
            default: return 'secondary';
        }
    }
    
    getStatusText(status) {
        switch (status) {
            case 'completed': return 'Завершено';
            case 'error': return 'Ошибка';
            case 'running': return 'Выполняется';
            case 'cancelled': return 'Отменено';
            default: return 'Неизвестно';
        }
    }
    
    loadRecentTransfers() {
        // Загружаем из localStorage
        const transfers = JSON.parse(localStorage.getItem('recentTransfers') || '[]');
        const container = document.getElementById('recentTransfers');
        
        if (transfers.length === 0) {
            container.innerHTML = `
                <div class="text-center text-muted py-3">
                    <i class="bi bi-inbox display-6"></i>
                    <p class="mt-2 mb-0">Операции переноса будут отображаться здесь</p>
                </div>
            `;
        } else {
            container.innerHTML = '';
            transfers.slice(0, 5).forEach(transfer => {
                this.addRecentTransfer(transfer);
            });
        }
    }
}

// Утилиты
function formatBytes(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function formatDuration(seconds) {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    
    if (hours > 0) {
        return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    } else {
        return `${minutes}:${secs.toString().padStart(2, '0')}`;
    }
}

// Инициализация приложения
document.addEventListener('DOMContentLoaded', () => {
    window.gmailTransferApp = new GmailTransferApp();
});

// Добавляем CSS анимацию для спиннера
const style = document.createElement('style');
style.textContent = `
    .spin {
        animation: spin 1s linear infinite;
    }
    
    @keyframes spin {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
    }
`;
document.head.appendChild(style);
