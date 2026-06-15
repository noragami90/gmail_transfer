/* Gmail Transfer Tool — dashboard (home) page */
(function () {
    'use strict';
    const { toast, statusBadge, escapeHtml, formatDateTime } = window.App;

    async function loadStats() {
        try {
            const res = await fetch('/api/transfers/stats');
            const stats = await res.json();
            if (!res.ok) return;

            const num = (v) => (v || 0).toLocaleString('ru-RU');
            document.getElementById('totalTransfers').textContent = num(stats.total_transfers);
            document.getElementById('completedTransfers').textContent = num(stats.completed);
            document.getElementById('runningTransfers').textContent = num(stats.running);
            document.getElementById('failedTransfers').textContent = num(stats.failed);
            document.getElementById('totalMessages').textContent = num(stats.total_messages_transferred);

            const list = document.getElementById('topSourcesList');
            if (stats.top_sources && stats.top_sources.length) {
                list.innerHTML = stats.top_sources.map(s => `
                    <div class="d-flex justify-content-between align-items-center py-2 border-bottom" style="border-color:var(--border)!important;">
                        <span class="text-truncate-mid" title="${escapeHtml(s.source_email)}">${escapeHtml(s.source_email)}</span>
                        <span class="badge badge-secondary">${s.count}</span>
                    </div>
                `).join('');
            } else {
                list.innerHTML = '<div class="text-muted">Нет данных</div>';
            }
        } catch (e) {
            console.error('Failed to load stats:', e);
        }
    }

    async function loadRecent() {
        try {
            const res = await fetch('/api/transfers/history?limit=6');
            const data = await res.json();
            if (!res.ok || !data.transfers) return;
            render(data.transfers);
        } catch (e) {
            console.error('Failed to load recent transfers:', e);
        }
    }

    function render(transfers) {
        const c = document.getElementById('recentTransfers');
        if (!transfers.length) {
            c.innerHTML = `
                <div class="empty-state">
                    <i class="bi bi-inbox empty-icon"></i>
                    <p class="mb-0">Операции переноса будут отображаться здесь</p>
                </div>`;
            return;
        }
        c.innerHTML = transfers.map(t => `
            <div class="transfer-item ${t.status}">
                <div class="d-flex justify-content-between align-items-start gap-2">
                    <div class="flex-grow-1 min-w-0">
                        <div class="route">
                            <span class="text-truncate-mid" title="${escapeHtml(t.source_email)}">${escapeHtml(t.source_email)}</span>
                            <i class="bi bi-arrow-right arrow"></i>
                            <span class="text-truncate-mid" title="${escapeHtml(t.target_email)}">${escapeHtml(t.target_email)}</span>
                        </div>
                        <small class="text-muted">${formatDateTime(t.created_at)}${t.total_messages ? ' · ' + t.total_messages + ' сообщ.' : ''}</small>
                    </div>
                    ${statusBadge(t.status)}
                </div>
            </div>
        `).join('');
    }

    document.addEventListener('DOMContentLoaded', () => {
        loadStats();
        loadRecent();
        const btn = document.getElementById('refreshStatsBtn');
        if (btn) btn.addEventListener('click', async () => {
            await Promise.all([loadStats(), loadRecent()]);
            toast('success', 'Статистика обновлена');
        });
    });
})();
