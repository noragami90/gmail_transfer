// Gmail Transfer Tool - Bulk Transfer JavaScript

class BulkTransferApp {
    constructor() {
        this.socket = null;
        this.currentBulkId = null;
        this.init();
    }
    
    init() {
        this.setupSocketIO();
        this.bindEvents();
    }
    
    setupSocketIO() {
        // Инициализация Socket.IO
        this.socket = io();
        
        this.socket.on('connect', () => {
            console.log('Connected to server');
        });
        
        this.socket.on('bulk_transfer_progress', (data) => {
            this.updateBulkProgress(data);
        });
    }
    
    bindEvents() {
        // Форма массового переноса
        document.getElementById('bulkTransferForm').addEventListener('submit', (e) => {
            e.preventDefault();
            this.startBulkTransfer();
        });
        
        // Проверка списка переносов
        document.getElementById('validateTransfersBtn').addEventListener('click', () => {
            this.validateTransfers();
        });
        
        // Отмена массового переноса
        document.getElementById('cancelBulkBtn').addEventListener('click', () => {
            this.cancelBulkTransfer();
        });
    }
    
    validateTransfers() {
        const transfersList = document.getElementById('transfersList').value.trim();
        
        if (!transfersList) {
            this.showAlert('warning', 'Введите список переносов для проверки');
            return;
        }
        
        const transfers = this.parseTransfersList(transfersList);
        const resultsDiv = document.getElementById('validationResults');
        const contentDiv = document.getElementById('validationContent');
        
        if (transfers.length === 0) {
            contentDiv.innerHTML = `
                <p class="text-danger mb-0">
                    <i class="bi bi-x-circle"></i> 
                    Не удалось распарсить ни одного переноса. Проверьте формат.
                </p>
            `;
        } else {
            contentDiv.innerHTML = `
                <p class="text-success mb-2">
                    <i class="bi bi-check-circle"></i> 
                    Найдено <strong>${transfers.length}</strong> валидных переносов:
                </p>
                <div class="list-group list-group-flush">
                    ${transfers.map((transfer, index) => `
                        <div class="list-group-item p-2">
                            <strong>${index + 1}.</strong> ${transfer.source_email} → ${transfer.target_email}
                            ${transfer.query ? `<br><small class="text-muted">Фильтр: ${transfer.query}</small>` : ''}
                            ${transfer.max_messages ? `<br><small class="text-muted">Лимит: ${transfer.max_messages} сообщений</small>` : ''}
                        </div>
                    `).join('')}
                </div>
            `;
        }
        
        resultsDiv.style.display = 'block';
        resultsDiv.scrollIntoView({ behavior: 'smooth' });
    }
    
    parseTransfersList(text) {
        const transfers = [];
        const lines = text.split('\n');
        
        for (let i = 0; i < lines.length; i++) {
            const line = lines[i].trim();
            
            // Пропускаем пустые строки и комментарии
            if (!line || line.startsWith('#')) continue;
            
            // Ищем формат: source -> target
            if (line.includes('->')) {
                const parts = line.split('->');
                if (parts.length >= 2) {
                    const source = parts[0].trim();
                    const targetPart = parts[1].trim();
                    
                    // Парсим целевую часть (может содержать фильтры)
                    const targetParts = targetPart.split(' ');
                    const target = targetParts[0];
                    
                    let query = '';
                    let maxMessages = null;
                    
                    // Обрабатываем дополнительные параметры
                    for (let j = 1; j < targetParts.length; j++) {
                        const part = targetParts[j];
                        if (part.startsWith('max:')) {
                            const maxStr = part.substring(4);
                            const maxNum = parseInt(maxStr);
                            if (!isNaN(maxNum)) {
                                maxMessages = maxNum;
                            }
                        } else {
                            query += (query ? ' ' : '') + part;
                        }
                    }
                    
                    // Валидация email
                    if (this.isValidEmail(source) && this.isValidEmail(target)) {
                        transfers.push({
                            source_email: source,
                            target_email: target,
                            query: query,
                            max_messages: maxMessages
                        });
                    }
                }
            }
        }
        
        return transfers;
    }
    
    isValidEmail(email) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(email);
    }
    
    async startBulkTransfer() {
        const name = document.getElementById('bulkName').value.trim();
        const transfersList = document.getElementById('transfersList').value.trim();
        const maxWorkers = parseInt(document.getElementById('maxWorkers').value);
        
        if (!name || !transfersList) {
            this.showAlert('warning', 'Заполните все обязательные поля');
            return;
        }
        
        const transfers = this.parseTransfersList(transfersList);
        if (transfers.length === 0) {
            this.showAlert('danger', 'Не удалось распарсить список переносов. Проверьте формат.');
            return;
        }
        
        // Подтверждение
        const confirmMessage = `Вы уверены, что хотите запустить массовый перенос "${name}" для ${transfers.length} переносов?`;
        if (!confirm(confirmMessage)) {
            return;
        }
        
        try {
            // Создаем массовый перенос
            const createResponse = await fetch('/api/bulk-transfer/create', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name: name,
                    transfers_text: transfersList
                })
            });
            
            const createData = await createResponse.json();
            
            if (!createResponse.ok) {
                throw new Error(createData.error || 'Ошибка создания массового переноса');
            }
            
            this.currentBulkId = createData.bulk_id;
            
            // Запускаем массовый перенос
            const startResponse = await fetch('/api/bulk-transfer/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    bulk_id: this.currentBulkId,
                    max_workers: maxWorkers
                })
            });
            
            const startData = await startResponse.json();
            
            if (startResponse.ok) {
                this.showBulkProgress();
                this.socket.emit('join_bulk_task', { bulk_id: this.currentBulkId });
                this.showAlert('success', 'Массовый перенос запущен успешно!');
            } else {
                throw new Error(startData.error || 'Ошибка запуска массового переноса');
            }
            
        } catch (error) {
            this.showAlert('danger', `Ошибка: ${error.message}`);
        }
    }
    
    showBulkProgress() {
        document.getElementById('bulkIdleCard').style.display = 'none';
        document.getElementById('bulkProgressCard').style.display = 'block';
        
        // Сбрасываем значения
        document.getElementById('bulkProgressBar').style.width = '0%';
        document.getElementById('bulkProgressText').textContent = '0%';
        document.getElementById('bulkTotal').textContent = '0';
        document.getElementById('bulkCompleted').textContent = '0';
        document.getElementById('bulkFailed').textContent = '0';
        document.getElementById('currentTransfer').textContent = 'Инициализация...';
    }
    
    hideBulkProgress() {
        document.getElementById('bulkProgressCard').style.display = 'none';
        document.getElementById('bulkIdleCard').style.display = 'block';
        this.currentBulkId = null;
    }
    
    updateBulkProgress(data) {
        if (data.bulk_id !== this.currentBulkId) return;
        
        console.log('Bulk progress update:', data);
        
        if (data.total) {
            const completed = data.completed || 0;
            const failed = data.failed || 0;
            const total = data.total;
            const percentage = Math.round((completed + failed) / total * 100);
            
            document.getElementById('bulkTotal').textContent = total;
            document.getElementById('bulkCompleted').textContent = completed;
            document.getElementById('bulkFailed').textContent = failed;
            
            document.getElementById('bulkProgressBar').style.width = `${percentage}%`;
            document.getElementById('bulkProgressText').textContent = `${percentage}%`;
            
            // Цвет прогресс-бара в зависимости от ошибок
            const progressBar = document.getElementById('bulkProgressBar');
            if (failed > 0) {
                progressBar.className = 'progress-bar bg-warning';
            } else {
                progressBar.className = 'progress-bar bg-success';
            }
        }
        
        if (data.current_transfer) {
            const currentText = `${data.current_transfer.source_email} → ${data.current_transfer.target_email}`;
            document.getElementById('currentTransfer').textContent = currentText;
        }
        
        if (data.status === 'completed' || data.status === 'error' || data.status === 'partial') {
            setTimeout(() => {
                this.hideBulkProgress();
                this.showAlert('info', data.message || 'Массовый перенос завершен');
            }, 3000);
        }
    }
    
    async cancelBulkTransfer() {
        if (!this.currentBulkId) return;
        
        if (!confirm('Вы уверены, что хотите отменить массовый перенос?')) {
            return;
        }
        
        try {
            const response = await fetch('/api/bulk-transfer/cancel', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ bulk_id: this.currentBulkId })
            });
            
            if (response.ok) {
                this.showAlert('warning', 'Массовый перенос отменен');
                this.hideBulkProgress();
            }
        } catch (error) {
            this.showAlert('danger', `Ошибка отмены: ${error.message}`);
        }
    }
    
    showAlert(type, message) {
        const alertContainer = document.getElementById('alertContainer');
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
}

// Инициализация приложения
document.addEventListener('DOMContentLoaded', () => {
    window.bulkTransferApp = new BulkTransferApp();
});
