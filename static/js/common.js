/* Gmail Transfer Tool — shared utilities (loaded on every page) */
(function () {
    'use strict';

    /* ----------------------------- Toasts ------------------------------- */
    const ICONS = {
        success: 'bi-check-circle-fill',
        danger: 'bi-exclamation-octagon-fill',
        warning: 'bi-exclamation-triangle-fill',
        info: 'bi-info-circle-fill'
    };

    function toast(type, message, timeout = 4500) {
        const stack = document.getElementById('toastStack');
        if (!stack) return;

        const item = document.createElement('div');
        item.className = `toast-item ${type}`;
        item.innerHTML = `
            <i class="bi ${ICONS[type] || ICONS.info} toast-icon"></i>
            <div class="toast-msg">${message}</div>
            <button class="toast-close" aria-label="Закрыть">&times;</button>
        `;

        const close = () => {
            item.classList.add('hiding');
            setTimeout(() => item.remove(), 200);
        };
        item.querySelector('.toast-close').addEventListener('click', close);

        stack.appendChild(item);

        // Keep at most 4 toasts on screen
        while (stack.children.length > 4) stack.firstElementChild.remove();

        if (timeout) setTimeout(close, timeout);
    }

    /* ------------------------- Status indicator ------------------------- */
    async function checkHealth() {
        const pill = document.getElementById('statusPill');
        if (!pill) return;
        const text = pill.querySelector('.pill-text');

        const set = (cls, label) => {
            pill.classList.remove('is-ok', 'is-warn', 'is-err');
            pill.classList.add(cls);
            if (text) text.textContent = label;
        };

        try {
            const res = await fetch('/api/health');
            const data = await res.json();
            if (res.ok && data.status === 'healthy') {
                set('is-ok', 'Gmail API подключён');
            } else {
                set('is-err', 'API недоступен');
            }
        } catch (e) {
            set('is-err', 'Нет связи');
        }
    }

    /* ------------------------------ Helpers ----------------------------- */
    const STATUS = {
        completed: { label: 'Завершено', cls: 'success' },
        running:   { label: 'Выполняется', cls: 'running' },
        pending:   { label: 'Ожидание', cls: 'secondary' },
        error:     { label: 'Ошибка', cls: 'danger' },
        cancelled: { label: 'Отменено', cls: 'warning' },
        partial:   { label: 'Частично', cls: 'warning' }
    };

    function statusBadge(status) {
        const s = STATUS[status] || { label: status || 'Неизвестно', cls: 'secondary' };
        return `<span class="badge badge-status badge-${s.cls}">${s.label}</span>`;
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text == null ? '' : text;
        return div.innerHTML;
    }

    function formatDateTime(value) {
        if (!value) return '—';
        const d = new Date(value);
        if (isNaN(d)) return escapeHtml(value);
        return d.toLocaleString('ru-RU', {
            day: '2-digit', month: '2-digit', year: 'numeric',
            hour: '2-digit', minute: '2-digit'
        });
    }

    function formatDuration(seconds) {
        seconds = Math.max(0, Math.round(seconds || 0));
        const h = Math.floor(seconds / 3600);
        const m = Math.floor((seconds % 3600) / 60);
        const s = seconds % 60;
        if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
        return `${m}:${String(s).padStart(2, '0')}`;
    }

    function debounce(fn, wait) {
        let t;
        return function (...args) {
            clearTimeout(t);
            t = setTimeout(() => fn.apply(this, args), wait);
        };
    }

    const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    const isEmail = (v) => EMAIL_RE.test((v || '').trim());

    /* ------------------------------ Export ------------------------------ */
    window.App = {
        toast, statusBadge, escapeHtml, formatDateTime,
        formatDuration, debounce, isEmail, STATUS
    };

    document.addEventListener('DOMContentLoaded', checkHealth);
})();
