/* Gmail Transfer Tool — single transfer page */
(function () {
    'use strict';
    const { toast, isEmail, formatDuration, debounce } = window.App;
    const $ = (id) => document.getElementById(id);

    class SingleTransfer {
        constructor() {
            this.socket = io();
            this.taskId = null;
            this.pollTimer = null;
            this.bindSocket();
            this.bindEvents();
            this.restore();
        }

        bindSocket() {
            this.socket.on('transfer_progress', (d) => this.updateProgress(d.progress));
            this.socket.on('transfer_status', (d) => this.onStatus(d.status, d.message));
            this.socket.on('transfer_error', (d) => {
                toast('danger', `Ошибка переноса: ${d.error}`);
                this.hideProgress();
            });
        }

        bindEvents() {
            $('transferForm').addEventListener('submit', (e) => { e.preventDefault(); this.start(); });
            $('testSourceBtn').addEventListener('click', () => this.test('source'));
            $('testTargetBtn').addEventListener('click', () => this.test('target'));
            $('previewBtn').addEventListener('click', () => this.preview());
            $('cancelBtn').addEventListener('click', () => this.cancel());
            $('restoreProgressBtn').addEventListener('click', () => this.restore(true));

            ['sourceEmail', 'targetEmail'].forEach((id) => {
                const el = $(id);
                el.addEventListener('input', () => this.validateField(el));
            });
            $('sourceEmail').addEventListener('blur', () => this.loadStats());
        }

        validateField(el) {
            el.classList.remove('is-valid', 'is-invalid');
            if (!el.value.trim()) return;
            el.classList.add(isEmail(el.value) ? 'is-valid' : 'is-invalid');
        }

        async test(type) {
            const email = $(type === 'source' ? 'sourceEmail' : 'targetEmail').value.trim();
            const btn = $(type === 'source' ? 'testSourceBtn' : 'testTargetBtn');
            if (!email) { toast('warning', 'Введите email для проверки'); return; }

            const original = btn.innerHTML;
            btn.innerHTML = '<i class="bi bi-arrow-clockwise spin"></i>';
            btn.disabled = true;
            try {
                const res = await fetch('/api/test-connection', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email })
                });
                const data = await res.json();
                if (res.ok && data.accessible) {
                    btn.innerHTML = '<i class="bi bi-check-circle-fill text-accent"></i>';
                    toast('success', `${email} доступен`);
                    if (type === 'source') this.loadStats();
                } else {
                    btn.innerHTML = '<i class="bi bi-x-circle text-danger"></i>';
                    toast('danger', `Нет доступа к ${email}: ${data.error || ''}`);
                }
            } catch (e) {
                btn.innerHTML = '<i class="bi bi-x-circle text-danger"></i>';
                toast('danger', `Ошибка проверки: ${e.message}`);
            } finally {
                btn.disabled = false;
                setTimeout(() => { btn.innerHTML = original; }, 2500);
            }
        }

        async loadStats() {
            const email = $('sourceEmail').value.trim();
            if (!isEmail(email)) return;
            const query = $('queryFilter').value.trim();
            try {
                const res = await fetch('/api/user-stats', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email, query })
                });
                const data = await res.json();
                if (!res.ok) return;
                $('sourceTotal').textContent = (data.total_messages || 0).toLocaleString('ru-RU');
                $('sourceLabels').textContent = data.labels_count ?? '—';
                const badge = $('sourceStatus');
                badge.className = 'badge badge-success';
                badge.textContent = 'Доступен';
            } catch (e) { /* silent */ }
        }

        async preview() {
            const email = $('sourceEmail').value.trim();
            const query = $('queryFilter').value.trim();
            const max = $('maxMessages').value;
            if (!isEmail(email)) { toast('warning', 'Введите корректный исходный email'); return; }

            const btn = $('previewBtn');
            const original = btn.innerHTML;
            btn.innerHTML = '<i class="bi bi-arrow-clockwise spin"></i>Анализ…';
            btn.disabled = true;
            try {
                const res = await fetch('/api/user-stats', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email, query })
                });
                const data = await res.json();
                if (res.ok) {
                    const total = max ? Math.min(data.total_messages, parseInt(max)) : data.total_messages;
                    toast('info', `К переносу: <strong>${(total || 0).toLocaleString('ru-RU')}</strong> сообщений${query ? ` (фильтр: ${query})` : ''}`);
                    this.loadStats();
                } else {
                    toast('danger', `Ошибка анализа: ${data.error}`);
                }
            } catch (e) {
                toast('danger', `Ошибка: ${e.message}`);
            } finally {
                btn.innerHTML = original;
                btn.disabled = false;
            }
        }

        async start() {
            const source = $('sourceEmail').value.trim();
            const target = $('targetEmail').value.trim();
            if (!isEmail(source) || !isEmail(target)) { toast('warning', 'Проверьте корректность email адресов'); return; }
            if (source === target) { toast('warning', 'Исходный и целевой адреса должны отличаться'); return; }
            if (!confirm(`Перенести почту от ${source} к ${target}?`)) return;

            const payload = {
                source_email: source,
                target_email: target,
                query: $('queryFilter').value.trim(),
                max_messages: $('maxMessages').value ? parseInt($('maxMessages').value) : null,
                create_transfer_label: $('createLabel').checked,
                exclude_emails: $('excludeEmails').value.trim()
            };

            try {
                const res = await fetch('/api/start-transfer', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await res.json();
                if (res.ok) {
                    this.taskId = data.task_id;
                    this.showProgress();
                    this.socket.emit('join_task', { task_id: this.taskId });
                    this.startPolling();
                    toast('success', 'Перенос запущен');
                } else {
                    toast('danger', `Не удалось запустить: ${data.error}`);
                }
            } catch (e) {
                toast('danger', `Ошибка: ${e.message}`);
            }
        }

        async cancel() {
            if (!this.taskId) return;
            if (!confirm('Отменить перенос?')) return;
            try {
                const res = await fetch('/api/cancel-transfer', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ task_id: this.taskId })
                });
                if (res.ok) { toast('warning', 'Перенос отменён'); this.hideProgress(); }
            } catch (e) {
                toast('danger', `Ошибка отмены: ${e.message}`);
            }
        }

        showProgress() {
            const card = $('progressCard');
            card.style.display = 'block';
            card.classList.add('fade-in');
            card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }

        hideProgress() {
            $('progressCard').style.display = 'none';
            this.taskId = null;
            localStorage.removeItem('currentTransfer');
            if (this.pollTimer) { clearInterval(this.pollTimer); this.pollTimer = null; }
        }

        startPolling() {
            if (this.pollTimer) clearInterval(this.pollTimer);
            this.pollTimer = setInterval(async () => {
                if (!this.taskId) return;
                try {
                    const res = await fetch(`/api/task-status/${this.taskId}`);
                    const data = await res.json();
                    if (data.status === 'completed') {
                        this.onStatus('completed', 'Перенос завершён');
                    } else if (data.status === 'not_found') {
                        this.hideProgress();
                    } else if (data.status === 'running' && data.progress) {
                        this.updateProgress(data.progress);
                    }
                } catch (e) { /* silent */ }
            }, 2000);
        }

        updateProgress(p) {
            if (!p) return;
            const total = p.total || 0;
            const transferred = p.transferred || 0;
            const errors = p.errors || 0;
            const skipped = p.skipped || 0;
            const processed = p.processed != null ? p.processed : (transferred + errors + skipped);
            const pct = total > 0 ? Math.round((processed / total) * 100) : 0;

            $('progressBar').style.width = `${pct}%`;
            $('progressPct').textContent = `${pct}%`;
            $('statTransferred').textContent = transferred.toLocaleString('ru-RU');
            $('statTotal').textContent = total.toLocaleString('ru-RU');
            $('statSkipped').textContent = skipped.toLocaleString('ru-RU');
            $('statErrors').textContent = errors.toLocaleString('ru-RU');
            $('statSpeed').textContent = p.messages_per_minute ? Math.round(p.messages_per_minute) : 0;
            $('statElapsed').textContent = formatDuration(p.elapsed_time);

            const title = $('progressTitle');
            if (processed > 0) title.textContent = 'Перенос в процессе…';
            else if (total > 0) title.textContent = 'Начинаем перенос…';
            else title.textContent = 'Анализ сообщений…';

            if (this.taskId) {
                localStorage.setItem('currentTransfer', JSON.stringify({
                    taskId: this.taskId, progress: p, timestamp: Date.now()
                }));
            }
        }

        onStatus(status, message) {
            const title = $('progressTitle');
            if (message) title.textContent = message;
            if (status === 'completed') {
                $('progressBar').style.width = '100%';
                $('progressPct').textContent = '100%';
                localStorage.removeItem('currentTransfer');
                toast('success', 'Перенос успешно завершён');
                setTimeout(() => this.hideProgress(), 4000);
            } else if (status === 'error' || status === 'cancelled') {
                localStorage.removeItem('currentTransfer');
            }
        }

        async restore(manual = false) {
            try {
                const res = await fetch('/api/active-tasks');
                const data = await res.json();
                if (data.active_tasks && data.active_tasks.length) {
                    const task = data.active_tasks[0];
                    this.taskId = task.task_id;
                    this.showProgress();
                    this.socket.emit('join_task', { task_id: this.taskId });
                    this.startPolling();
                    if (task.progress && Object.keys(task.progress).length) this.updateProgress(task.progress);
                    toast('info', 'Восстановлен активный перенос');
                    return;
                }
                if (manual) toast('info', 'Активных переносов не найдено');
            } catch (e) {
                if (manual) toast('danger', 'Не удалось проверить активные переносы');
            }
        }
    }

    document.addEventListener('DOMContentLoaded', () => { window.singleTransfer = new SingleTransfer(); });
})();
