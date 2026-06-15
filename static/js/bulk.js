/* Gmail Transfer Tool — bulk transfer page */
(function () {
    'use strict';
    const { toast, escapeHtml, isEmail } = window.App;
    const $ = (id) => document.getElementById(id);

    class BulkTransfer {
        constructor() {
            this.socket = io();
            this.bulkId = null;
            this.socket.on('bulk_transfer_progress', (d) => this.onProgress(d));
            this.bindEvents();
        }

        bindEvents() {
            $('bulkTransferForm').addEventListener('submit', (e) => { e.preventDefault(); this.start(); });
            $('validateTransfersBtn').addEventListener('click', () => this.validate());
            $('cancelBulkBtn').addEventListener('click', () => this.cancel());
        }

        parse(text) {
            const transfers = [];
            for (const raw of text.split('\n')) {
                const line = raw.trim();
                if (!line || line.startsWith('#') || !line.includes('->')) continue;
                const [src, rest] = line.split('->');
                const source = src.trim();
                const parts = rest.trim().split(/\s+/);
                const target = parts[0];
                let query = '', maxMessages = null;
                for (const p of parts.slice(1)) {
                    if (p.startsWith('max:')) {
                        const n = parseInt(p.slice(4));
                        if (!isNaN(n)) maxMessages = n;
                    } else {
                        query += (query ? ' ' : '') + p;
                    }
                }
                if (isEmail(source) && isEmail(target)) {
                    transfers.push({ source_email: source, target_email: target, query, max_messages: maxMessages });
                }
            }
            return transfers;
        }

        validate() {
            const text = $('transfersList').value.trim();
            if (!text) { toast('warning', 'Введите список переносов'); return; }
            const transfers = this.parse(text);
            const wrap = $('validationResults');
            const content = $('validationContent');

            if (!transfers.length) {
                content.innerHTML = `<div class="text-danger"><i class="bi bi-x-circle me-1"></i>Не удалось распознать ни одного переноса. Проверьте формат.</div>`;
            } else {
                content.innerHTML = `
                    <div class="text-accent mb-2"><i class="bi bi-check-circle me-1"></i>Распознано <strong>${transfers.length}</strong> переносов:</div>
                    ${transfers.map((t, i) => `
                        <div class="transfer-item">
                            <div class="route"><span>${escapeHtml(t.source_email)}</span><i class="bi bi-arrow-right arrow"></i><span>${escapeHtml(t.target_email)}</span></div>
                            ${(t.query || t.max_messages) ? `<small class="text-muted">${t.query ? 'Фильтр: ' + escapeHtml(t.query) : ''}${t.max_messages ? (t.query ? ' · ' : '') + 'max: ' + t.max_messages : ''}</small>` : ''}
                        </div>`).join('')}
                `;
            }
            wrap.style.display = 'block';
        }

        async start() {
            const name = $('bulkName').value.trim();
            const text = $('transfersList').value.trim();
            const maxWorkers = parseInt($('maxWorkers').value);
            const excludeEmails = $('bulkExcludeEmails').value.trim();

            if (!name || !text) { toast('warning', 'Заполните название и список переносов'); return; }
            const transfers = this.parse(text);
            if (!transfers.length) { toast('danger', 'Не удалось распознать список переносов'); return; }
            if (!confirm(`Запустить массовый перенос «${name}» (${transfers.length} переносов)?`)) return;

            try {
                const createRes = await fetch('/api/bulk-transfer/create', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name, transfers_text: text, exclude_emails: excludeEmails })
                });
                const createData = await createRes.json();
                if (!createRes.ok) throw new Error(createData.error || 'Ошибка создания');

                this.bulkId = createData.bulk_id;
                const startRes = await fetch('/api/bulk-transfer/start', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ bulk_id: this.bulkId, max_workers: maxWorkers })
                });
                const startData = await startRes.json();
                if (!startRes.ok) throw new Error(startData.error || 'Ошибка запуска');

                this.showProgress();
                this.socket.emit('join_bulk_task', { bulk_id: this.bulkId });
                toast('success', 'Массовый перенос запущен');
            } catch (e) {
                toast('danger', `Ошибка: ${e.message}`);
            }
        }

        showProgress() {
            $('bulkIdleCard').style.display = 'none';
            $('bulkProgressCard').style.display = 'block';
            ['bulkTotal', 'bulkCompleted', 'bulkFailed'].forEach((id) => { $(id).textContent = '0'; });
            $('bulkProgressBar').style.width = '0%';
            $('bulkProgressText').textContent = '0%';
            $('currentTransfer').textContent = 'Инициализация…';
        }

        hideProgress() {
            $('bulkProgressCard').style.display = 'none';
            $('bulkIdleCard').style.display = 'block';
            this.bulkId = null;
        }

        onProgress(data) {
            if (data.bulk_id !== this.bulkId) return;
            if (data.total) {
                const completed = data.completed || 0;
                const failed = data.failed || 0;
                const pct = Math.round(((completed + failed) / data.total) * 100);
                $('bulkTotal').textContent = data.total;
                $('bulkCompleted').textContent = completed;
                $('bulkFailed').textContent = failed;
                $('bulkProgressBar').style.width = `${pct}%`;
                $('bulkProgressText').textContent = `${pct}%`;
                $('bulkProgressBar').className = 'progress-bar' + (failed > 0 ? ' bg-warning' : '');
            }
            if (data.current_transfer) {
                $('currentTransfer').innerHTML =
                    `<span>${escapeHtml(data.current_transfer.source_email)}</span><i class="bi bi-arrow-right arrow"></i><span>${escapeHtml(data.current_transfer.target_email)}</span>`;
            }
            if (['completed', 'error', 'partial', 'cancelled'].includes(data.status)) {
                toast(data.status === 'completed' ? 'success' : 'info', data.message || 'Массовый перенос завершён');
                setTimeout(() => this.hideProgress(), 4000);
            }
        }

        async cancel() {
            if (!this.bulkId) return;
            if (!confirm('Отменить массовый перенос?')) return;
            try {
                const res = await fetch('/api/bulk-transfer/cancel', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ bulk_id: this.bulkId })
                });
                if (res.ok) { toast('warning', 'Массовый перенос отменён'); this.hideProgress(); }
            } catch (e) {
                toast('danger', `Ошибка отмены: ${e.message}`);
            }
        }
    }

    document.addEventListener('DOMContentLoaded', () => { window.bulkTransfer = new BulkTransfer(); });
})();
