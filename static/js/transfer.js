// Gmail Transfer Tool - Transfer specific JavaScript

class TransferManager {
    constructor(app) {
        this.app = app;
        this.init();
    }
    
    init() {
        this.bindTransferEvents();
        this.setupFormValidation();
    }
    
    bindTransferEvents() {
        // Автоматическая валидация email при вводе
        const emailInputs = ['sourceEmail', 'targetEmail'];
        emailInputs.forEach(inputId => {
            const input = document.getElementById(inputId);
            if (input) {
                input.addEventListener('input', () => this.validateEmail(inputId));
                input.addEventListener('paste', () => {
                    setTimeout(() => this.validateEmail(inputId), 100);
                });
            }
        });
        
        // Предварительный просмотр при изменении фильтра
        const queryFilter = document.getElementById('queryFilter');
        if (queryFilter) {
            let timeout;
            queryFilter.addEventListener('input', () => {
                clearTimeout(timeout);
                timeout = setTimeout(() => {
                    this.updatePreviewCount();
                }, 1000);
            });
        }
        
        // Умная проверка при изменении максимального количества
        const maxMessages = document.getElementById('maxMessages');
        if (maxMessages) {
            maxMessages.addEventListener('input', () => {
                this.validateMaxMessages();
            });
        }
    }
    
    setupFormValidation() {
        const form = document.getElementById('transferForm');
        if (form) {
            form.addEventListener('submit', (e) => {
                e.preventDefault();
                if (this.validateForm()) {
                    this.app.startTransfer();
                }
            });
        }
    }
    
    validateEmail(inputId) {
        const input = document.getElementById(inputId);
        const value = input.value.trim();
        
        // Очищаем предыдущие состояния
        input.classList.remove('is-valid', 'is-invalid');
        
        if (!value) {
            return false;
        }
        
        // Базовая валидация email
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        const isValid = emailRegex.test(value);
        
        if (isValid) {
            input.classList.add('is-valid');
            
            // Автоматический тест подключения через 2 секунды после ввода
            clearTimeout(input.testTimeout);
            input.testTimeout = setTimeout(() => {
                this.autoTestConnection(inputId);
            }, 2000);
            
        } else {
            input.classList.add('is-invalid');
        }
        
        // Проверяем, что источник и цель отличаются
        this.validateEmailsDifference();
        
        return isValid;
    }
    
    validateEmailsDifference() {
        const sourceEmail = document.getElementById('sourceEmail').value.trim();
        const targetEmail = document.getElementById('targetEmail').value.trim();
        
        if (sourceEmail && targetEmail && sourceEmail === targetEmail) {
            document.getElementById('targetEmail').classList.add('is-invalid');
            this.showValidationError('targetEmail', 'Email адреса должны отличаться');
            return false;
        }
        
        return true;
    }
    
    validateMaxMessages() {
        const input = document.getElementById('maxMessages');
        const value = parseInt(input.value);
        
        input.classList.remove('is-valid', 'is-invalid');
        
        if (input.value && (isNaN(value) || value <= 0)) {
            input.classList.add('is-invalid');
            this.showValidationError('maxMessages', 'Введите положительное число');
            return false;
        } else if (input.value) {
            input.classList.add('is-valid');
        }
        
        return true;
    }
    
    validateForm() {
        const sourceEmail = document.getElementById('sourceEmail').value.trim();
        const targetEmail = document.getElementById('targetEmail').value.trim();
        
        if (!sourceEmail || !targetEmail) {
            this.app.showAlert('warning', 'Заполните все обязательные поля');
            return false;
        }
        
        if (!this.validateEmail('sourceEmail') || !this.validateEmail('targetEmail')) {
            this.app.showAlert('warning', 'Проверьте корректность email адресов');
            return false;
        }
        
        if (!this.validateEmailsDifference()) {
            this.app.showAlert('warning', 'Email адреса должны отличаться');
            return false;
        }
        
        if (!this.validateMaxMessages()) {
            return false;
        }
        
        return true;
    }
    
    async autoTestConnection(inputId) {
        const input = document.getElementById(inputId);
        const email = input.value.trim();
        
        if (!email || !this.validateEmail(inputId)) {
            return;
        }
        
        const type = inputId === 'sourceEmail' ? 'source' : 'target';
        const button = document.getElementById(type === 'source' ? 'testSourceBtn' : 'testTargetBtn');
        
        // Показываем индикатор проверки
        const originalIcon = button.innerHTML;
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
                input.classList.remove('is-invalid');
                input.classList.add('is-valid');
                
                // Загружаем статистику
                this.app.loadUserStats(type);
                
                // Показываем тихое уведомление
                this.showQuietNotification(`✅ ${email} доступен`, 'success');
                
            } else {
                button.innerHTML = '<i class="bi bi-x-circle text-danger"></i>';
                input.classList.remove('is-valid');
                input.classList.add('is-invalid');
                
                this.showValidationError(inputId, data.error || 'Пользователь недоступен');
                this.showQuietNotification(`❌ ${email} недоступен`, 'danger');
            }
        } catch (error) {
            button.innerHTML = '<i class="bi bi-exclamation-triangle text-warning"></i>';
            console.error('Auto test connection failed:', error);
        } finally {
            button.disabled = false;
        }
    }
    
    async updatePreviewCount() {
        const sourceEmail = document.getElementById('sourceEmail').value.trim();
        const query = document.getElementById('queryFilter').value.trim();
        
        if (!sourceEmail) return;
        
        const previewBtn = document.getElementById('previewBtn');
        const originalText = previewBtn.innerHTML;
        
        try {
            previewBtn.innerHTML = '<i class="bi bi-arrow-clockwise spin me-2"></i>Анализ...';
            previewBtn.disabled = true;
            
            const response = await fetch('/api/user-stats', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email: sourceEmail, query })
            });
            
            const data = await response.json();
            
            if (response.ok) {
                const count = data.total_messages;
                const countText = count.toLocaleString();
                
                if (count === 0) {
                    previewBtn.innerHTML = '<i class="bi bi-eye me-2"></i>Нет сообщений';
                } else {
                    previewBtn.innerHTML = `<i class="bi bi-eye me-2"></i>Просмотр (${countText})`;
                }
                
                // Обновляем статистику
                this.app.updateUserStats('source', data);
            }
        } catch (error) {
            console.error('Failed to update preview count:', error);
        } finally {
            if (previewBtn.innerHTML.includes('Анализ')) {
                previewBtn.innerHTML = originalText;
            }
            previewBtn.disabled = false;
        }
    }
    
    showValidationError(inputId, message) {
        const input = document.getElementById(inputId);
        
        // Удаляем предыдущие ошибки
        const existingError = input.parentNode.querySelector('.invalid-feedback');
        if (existingError) {
            existingError.remove();
        }
        
        // Добавляем новую ошибку
        const errorDiv = document.createElement('div');
        errorDiv.className = 'invalid-feedback';
        errorDiv.textContent = message;
        
        input.parentNode.appendChild(errorDiv);
    }
    
    showQuietNotification(message, type) {
        // Создаем тихое уведомление в углу
        const notification = document.createElement('div');
        notification.className = `alert alert-${type} position-fixed top-0 end-0 m-3 shadow-sm`;
        notification.style.zIndex = '9999';
        notification.style.minWidth = '300px';
        notification.innerHTML = `
            ${message}
            <button type="button" class="btn-close" onclick="this.parentElement.remove()"></button>
        `;
        
        document.body.appendChild(notification);
        
        // Автоматическое удаление через 3 секунды
        setTimeout(() => {
            if (notification.parentElement) {
                notification.remove();
            }
        }, 3000);
        
        // Анимация появления
        notification.style.transform = 'translateX(100%)';
        notification.style.transition = 'transform 0.3s ease';
        setTimeout(() => {
            notification.style.transform = 'translateX(0)';
        }, 100);
    }
    
    generateSampleQueries() {
        return [
            { label: 'Все непрочитанные', query: 'is:unread' },
            { label: 'Важные письма', query: 'is:important' },
            { label: 'С вложениями', query: 'has:attachment' },
            { label: 'За последний месяц', query: 'newer_than:1m' },
            { label: 'От конкретного отправителя', query: 'from:example@domain.com' },
            { label: 'В определенной папке', query: 'in:inbox' },
            { label: 'Помеченные звездочкой', query: 'is:starred' },
            { label: 'Большие письма (>5MB)', query: 'larger:5M' }
        ];
    }
    
    setupQuerySuggestions() {
        const queryInput = document.getElementById('queryFilter');
        const suggestions = this.generateSampleQueries();
        
        // Создаем выпадающий список с предложениями
        const datalist = document.createElement('datalist');
        datalist.id = 'querySuggestions';
        
        suggestions.forEach(suggestion => {
            const option = document.createElement('option');
            option.value = suggestion.query;
            option.textContent = suggestion.label;
            datalist.appendChild(option);
        });
        
        queryInput.setAttribute('list', 'querySuggestions');
        queryInput.parentNode.appendChild(datalist);
    }
    
    formatTransferEstimate(totalMessages, transferredPerMinute = 60) {
        const totalMinutes = Math.ceil(totalMessages / transferredPerMinute);
        const hours = Math.floor(totalMinutes / 60);
        const minutes = totalMinutes % 60;
        
        if (hours > 0) {
            return `~${hours}ч ${minutes}мин`;
        } else {
            return `~${minutes}мин`;
        }
    }
}

// Дополнительные утилиты для работы с формой
class FormUtils {
    static saveFormState() {
        const formData = {
            sourceEmail: document.getElementById('sourceEmail').value,
            targetEmail: document.getElementById('targetEmail').value,
            queryFilter: document.getElementById('queryFilter').value,
            maxMessages: document.getElementById('maxMessages').value,
            createLabel: document.getElementById('createLabel').checked
        };
        
        localStorage.setItem('gmailTransferFormState', JSON.stringify(formData));
    }
    
    static restoreFormState() {
        const savedState = localStorage.getItem('gmailTransferFormState');
        if (!savedState) return;
        
        try {
            const formData = JSON.parse(savedState);
            
            Object.keys(formData).forEach(key => {
                const element = document.getElementById(key);
                if (element) {
                    if (element.type === 'checkbox') {
                        element.checked = formData[key];
                    } else {
                        element.value = formData[key];
                    }
                }
            });
        } catch (error) {
            console.error('Failed to restore form state:', error);
        }
    }
    
    static clearFormState() {
        localStorage.removeItem('gmailTransferFormState');
    }
}

// Автоматическое сохранение состояния формы
document.addEventListener('DOMContentLoaded', () => {
    // Восстанавливаем состояние формы
    FormUtils.restoreFormState();
    
    // Создаем менеджер переносов
    if (window.gmailTransferApp) {
        window.transferManager = new TransferManager(window.gmailTransferApp);
        window.transferManager.setupQuerySuggestions();
    }
    
    // Автосохранение состояния формы
    const formInputs = ['sourceEmail', 'targetEmail', 'queryFilter', 'maxMessages', 'createLabel'];
    formInputs.forEach(inputId => {
        const element = document.getElementById(inputId);
        if (element) {
            element.addEventListener('change', FormUtils.saveFormState);
            element.addEventListener('input', FormUtils.saveFormState);
        }
    });
    
    // Очищаем состояние при успешном переносе
    window.addEventListener('transferCompleted', () => {
        FormUtils.clearFormState();
    });
});
