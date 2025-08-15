// Gmail Transfer Tool - History Page JavaScript

class TransferHistoryApp {
    constructor() {
        this.currentPage = 1;
        this.currentFilters = {};
        this.init();
    }
    
    init() {
        this.bindEvents();
        this.loadStats();
        this.loadHistory();
    }
    
    bindEvents() {
        // Refresh button
        document.getElementById('refreshHistoryBtn').addEventListener('click', () => {
            this.refreshData();
        });
        
        // Apply filters
        document.getElementById('applyFiltersBtn').addEventListener('click', () => {
            this.applyFilters();
        });
        
        // Enter key in filter fields
        document.getElementById('sourceEmailFilter').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.applyFilters();
            }
        });
    }
    
    async loadStats() {
        try {
            const response = await fetch('/api/transfers/stats');
            const stats = await response.json();
            
            if (response.ok) {
                this.updateStats(stats);
            }
        } catch (error) {
            console.error('Failed to load stats:', error);
        }
    }
    
    updateStats(stats) {
        document.getElementById('totalTransfers').textContent = (stats.total_transfers || 0).toLocaleString();
        document.getElementById('completedTransfers').textContent = (stats.completed || 0).toLocaleString();
        document.getElementById('runningTransfers').textContent = (stats.running || 0).toLocaleString();
        document.getElementById('failedTransfers').textContent = (stats.failed || 0).toLocaleString();
        document.getElementById('totalMessages').textContent = (stats.total_messages_transferred || 0).toLocaleString();
        
        // Top sources
        const topSourcesList = document.getElementById('topSourcesList');
        if (stats.top_sources && stats.top_sources.length > 0) {
            topSourcesList.innerHTML = stats.top_sources.map(source => 
                `<div class="d-flex justify-content-between">
                    <small class="text-truncate">${source.source_email}</small>
                    <span class="badge bg-primary">${source.count}</span>
                </div>`
            ).join('');
        } else {
            topSourcesList.innerHTML = '<small class="text-muted">Нет данных</small>';
        }
    }
    
    async loadHistory(page = 1) {
        try {
            const params = new URLSearchParams({
                page: page,
                limit: 20,
                ...this.currentFilters
            });
            
            const response = await fetch(`/api/transfers/history?${params}`);
            const data = await response.json();
            
            if (response.ok) {
                this.updateHistoryTable(data.transfers);
                this.updatePagination(data.page, data.limit, data.transfers.length);
                this.currentPage = page;
            }
        } catch (error) {
            console.error('Failed to load history:', error);
        }
    }
    
    updateHistoryTable(transfers) {
        const tbody = document.getElementById('historyTableBody');
        
        if (transfers.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="6" class="text-center text-muted py-4">
                        <i class="bi bi-inbox display-6"></i>
                        <p class="mt-2 mb-0">История переносов пуста</p>
                    </td>
                </tr>
            `;
            return;
        }
        
        tbody.innerHTML = transfers.map(transfer => {
            const startTime = new Date(transfer.created_at).toLocaleString();
            const statusBadge = this.getStatusBadge(transfer.status);
            const totalMessages = transfer.total_messages || 0;
            const transferredMessages = transfer.transferred_messages || 0;
            const errorMessages = transfer.error_messages || 0;
            
            return `
                <tr>
                    <td>
                        <small>${startTime}</small>
                    </td>
                    <td>
                        <div class="text-truncate" style="max-width: 200px;" title="${transfer.source_email}">
                            ${transfer.source_email}
                        </div>
                    </td>
                    <td>
                        <div class="text-truncate" style="max-width: 200px;" title="${transfer.target_email}">
                            ${transfer.target_email}
                        </div>
                    </td>
                    <td>
                        <span class="badge bg-light text-dark">${totalMessages.toLocaleString()}</span>
                        ${transferredMessages > 0 ? `<br><small class="text-success">✓ ${transferredMessages}</small>` : ''}
                        ${errorMessages > 0 ? `<br><small class="text-danger">✗ ${errorMessages}</small>` : ''}
                    </td>
                    <td>${statusBadge}</td>
                    <td>
                        <button class="btn btn-outline-primary btn-sm" onclick="transferHistory.showDetails('${transfer.id}')">
                            <i class="bi bi-eye"></i>
                        </button>
                    </td>
                </tr>
            `;
        }).join('');
    }
    
    getStatusBadge(status) {
        const badges = {
            completed: '<span class="badge bg-success">Завершено</span>',
            running: '<span class="badge bg-primary">Выполняется</span>',
            error: '<span class="badge bg-danger">Ошибка</span>',
            cancelled: '<span class="badge bg-warning">Отменено</span>',
            pending: '<span class="badge bg-secondary">Ожидание</span>'
        };
        return badges[status] || '<span class="badge bg-secondary">Неизвестно</span>';
    }
    
    updatePagination(currentPage, limit, resultsCount) {
        const pagination = document.getElementById('historyPagination');
        const hasNext = resultsCount === limit;
        const hasPrev = currentPage > 1;
        
        let html = '';
        
        if (hasPrev) {
            html += `
                <li class="page-item">
                    <a class="page-link" href="#" onclick="transferHistory.loadHistory(${currentPage - 1})">
                        <i class="bi bi-chevron-left"></i>
                    </a>
                </li>
            `;
        }
        
        html += `
            <li class="page-item active">
                <span class="page-link">Страница ${currentPage}</span>
            </li>
        `;
        
        if (hasNext) {
            html += `
                <li class="page-item">
                    <a class="page-link" href="#" onclick="transferHistory.loadHistory(${currentPage + 1})">
                        <i class="bi bi-chevron-right"></i>
                    </a>
                </li>
            `;
        }
        
        pagination.innerHTML = html;
    }
    
    applyFilters() {
        this.currentFilters = {};
        
        const statusFilter = document.getElementById('statusFilter').value;
        const sourceEmailFilter = document.getElementById('sourceEmailFilter').value.trim();
        
        if (statusFilter) {
            this.currentFilters.status = statusFilter;
        }
        
        if (sourceEmailFilter) {
            this.currentFilters.source_email = sourceEmailFilter;
        }
        
        this.currentPage = 1;
        this.loadHistory(1);
    }
    
    async showDetails(transferId) {
        try {
            const response = await fetch(`/api/task-status/${transferId}`);
            const data = await response.json();
            
            if (response.ok) {
                this.displayTransferDetails(data);
            } else {
                // Fallback - try to get from history API
                this.showError('Детали недоступны', 'Не удалось загрузить детали переноса');
            }
        } catch (error) {
            this.showError('Ошибка', 'Не удалось загрузить детали переноса');
        }
    }
    
    displayTransferDetails(data) {
        const modalBody = document.getElementById('transferDetailsBody');
        
        modalBody.innerHTML = `
            <div class="row">
                <div class="col-md-6">
                    <h6>Основная информация</h6>
                    <table class="table table-sm">
                        <tr><td>Статус:</td><td>${this.getStatusBadge(data.status)}</td></tr>
                        <tr><td>Откуда:</td><td>${data.task?.source_email || 'N/A'}</td></tr>
                        <tr><td>Куда:</td><td>${data.task?.target_email || 'N/A'}</td></tr>
                        <tr><td>Начало:</td><td>${data.task?.start_time ? new Date(data.task.start_time).toLocaleString() : 'N/A'}</td></tr>
                    </table>
                </div>
                <div class="col-md-6">
                    <h6>Статистика</h6>
                    <table class="table table-sm">
                        <tr><td>Всего сообщений:</td><td>${data.result?.total || 0}</td></tr>
                        <tr><td>Перенесено:</td><td class="text-success">${data.result?.transferred || 0}</td></tr>
                        <tr><td>Ошибок:</td><td class="text-danger">${data.result?.errors || 0}</td></tr>
                    </table>
                </div>
            </div>
        `;
        
        const modal = new bootstrap.Modal(document.getElementById('transferDetailsModal'));
        modal.show();
    }
    
    refreshData() {
        this.loadStats();
        this.loadHistory(this.currentPage);
        this.showAlert('info', 'Данные обновлены');
    }
    
    showAlert(type, message) {
        // Используем алерты из основного приложения
        const alertContainer = document.body;
        const alertId = 'alert-' + Date.now();
        
        const alertHtml = `
            <div class="alert alert-${type} alert-dismissible fade show position-fixed" 
                 style="top: 20px; right: 20px; z-index: 1055;" role="alert" id="${alertId}">
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;
        
        alertContainer.insertAdjacentHTML('beforeend', alertHtml);
        
        setTimeout(() => {
            const alert = document.getElementById(alertId);
            if (alert) {
                const bsAlert = new bootstrap.Alert(alert);
                bsAlert.close();
            }
        }, 3000);
    }
    
    showError(title, message) {
        this.showAlert('danger', `<strong>${title}:</strong> ${message}`);
    }
}

// Инициализация приложения
document.addEventListener('DOMContentLoaded', () => {
    window.transferHistory = new TransferHistoryApp();
});
