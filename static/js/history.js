/* Gmail Transfer Tool — history page */
(function () {
    'use strict';
    const { toast, statusBadge, escapeHtml, formatDateTime } = window.App;
    const $ = (id) => document.getElementById(id);

    class History {
        constructor() {
            this.pageSize = 10;
            this.singlePage = 1;
            this.bulkPage = 1;
            this.bulkLoaded = false;
            this.modal = new bootstrap.Modal($('detailsModal'));
            this.bindEvents();
            this.loadSingle();
        }

        bindEvents() {
            $('bulk-tab').addEventListener('shown.bs.tab', () => { if (!this.bulkLoaded) this.loadBulk(); });
            $('applySingleFilters').addEventListener('click', () => { this.singlePage = 1; this.loadSingle(); });
            $('applyBulkFilters').addEventListener('click', () => { this.bulkPage = 1; this.loadBulk(); });
        }

        /* ----------------------------- Single ---------------------------- */
        async loadSingle() {
            const status = $('singleStatusFilter').value;
            const source = $('singleSourceFilter').value.trim();
            let url = `/api/transfers/history?page=${this.singlePage}&limit=${this.pageSize}`;
            if (status) url += `&status=${status}`;
            if (source) url += `&source_email=${encodeURIComponent(source)}`;

            try {
                const res = await fetch(url);
                const data = await res.json();
                if (!res.ok) throw new Error(data.error);
                this.renderSingle(data.transfers || []);
                this.renderPagination('singlePagination', this.singlePage, data.total || 0,
                    'singleShowing', 'singleTotal', (data.transfers || []).length,
                    (p) => { this.singlePage = p; this.loadSingle(); });
            } catch (e) {
                this.renderSingle([]);
            }
        }

        renderSingle(rows) {
            const tbody = $('singleTableBody');
            if (!rows.length) {
                tbody.innerHTML = this.emptyRow(6, 'История одиночных переносов пуста', '/single', 'Создать перенос');
                return;
            }
            tbody.innerHTML = rows.map((t) => `
                <tr>
                    <td><small>${formatDateTime(t.created_at)}</small></td>
                    <td><span class="text-truncate-mid" title="${escapeHtml(t.source_email)}">${escapeHtml(t.source_email)}</span></td>
                    <td><span class="text-truncate-mid" title="${escapeHtml(t.target_email)}">${escapeHtml(t.target_email)}</span></td>
                    <td><span class="badge badge-info">${t.transferred_messages || 0} / ${t.total_messages || 0}</span></td>
                    <td>${statusBadge(t.status)}</td>
                    <td class="text-end">
                        <button class="btn btn-outline-secondary btn-sm" data-single="${escapeHtml(t.id)}" title="Детали"><i class="bi bi-eye"></i></button>
                    </td>
                </tr>`).join('');
            tbody.querySelectorAll('[data-single]').forEach((b) =>
                b.addEventListener('click', () => this.showSingle(b.dataset.single)));
        }

        async showSingle(id) {
            this.openModal('Детали переноса', '<div class="text-center py-3"><i class="bi bi-arrow-clockwise spin"></i></div>');
            try {
                const res = await fetch(`/api/transfers/${id}`);
                const t = await res.json();
                if (!res.ok) throw new Error(t.error);
                this.setModalBody(`
                    <div class="route mb-3" style="font-size:1.05rem;">
                        <span>${escapeHtml(t.source_email)}</span><i class="bi bi-arrow-right arrow"></i><span>${escapeHtml(t.target_email)}</span>
                    </div>
                    ${this.kv([
                        ['Статус', statusBadge(t.status)],
                        ['Создан', formatDateTime(t.created_at)],
                        ['Завершён', formatDateTime(t.end_time)],
                        ['Фильтр', t.query_filter ? `<code>${escapeHtml(t.query_filter)}</code>` : '—'],
                        ['Всего сообщений', t.total_messages || 0],
                        ['Перенесено', t.transferred_messages || 0],
                        ['Пропущено', t.skipped_messages || 0],
                        ['Ошибок', t.error_messages || 0],
                    ])}
                    ${t.error_message ? `<div class="text-danger mt-2"><i class="bi bi-exclamation-octagon me-1"></i>${escapeHtml(t.error_message)}</div>` : ''}
                `);
            } catch (e) {
                this.setModalBody(`<div class="text-danger">Не удалось загрузить детали: ${escapeHtml(e.message)}</div>`);
            }
        }

        /* ------------------------------ Bulk ----------------------------- */
        async loadBulk() {
            this.bulkLoaded = true;
            const status = $('bulkStatusFilter').value;
            const name = $('bulkNameFilter').value.trim();
            let url = `/api/bulk-transfers?page=${this.bulkPage}&limit=${this.pageSize}`;
            if (status) url += `&status=${status}`;
            if (name) url += `&name=${encodeURIComponent(name)}`;

            try {
                const res = await fetch(url);
                const data = await res.json();
                if (!res.ok) throw new Error(data.error);
                this.renderBulk(data.bulk_transfers || []);
                this.renderPagination('bulkPagination', this.bulkPage, data.total || 0,
                    'bulkShowing', 'bulkTotalCount', (data.bulk_transfers || []).length,
                    (p) => { this.bulkPage = p; this.loadBulk(); });
            } catch (e) {
                this.renderBulk([]);
            }
        }

        renderBulk(rows) {
            const tbody = $('bulkTableBody');
            if (!rows.length) {
                tbody.innerHTML = this.emptyRow(7, 'История массовых переносов пуста', '/bulk', 'Создать массовый перенос');
                return;
            }
            tbody.innerHTML = rows.map((b) => `
                <tr>
                    <td><div class="fw-semibold">${escapeHtml(b.name)}</div></td>
                    <td><small>${formatDateTime(b.created_at)}</small></td>
                    <td><span class="badge badge-info">${b.total_transfers || 0}</span></td>
                    <td><span class="badge badge-success">${b.completed_transfers || 0}</span></td>
                    <td><span class="badge badge-danger">${b.failed_transfers || 0}</span></td>
                    <td>${statusBadge(b.status)}</td>
                    <td class="text-end">
                        <button class="btn btn-outline-secondary btn-sm" data-bulk="${escapeHtml(b.id)}" title="Детали"><i class="bi bi-eye"></i></button>
                        ${b.status === 'running' ? `<button class="btn btn-outline-danger btn-sm" data-cancel="${escapeHtml(b.id)}" title="Отменить"><i class="bi bi-stop-fill"></i></button>` : ''}
                    </td>
                </tr>`).join('');
            tbody.querySelectorAll('[data-bulk]').forEach((b) =>
                b.addEventListener('click', () => this.showBulk(b.dataset.bulk)));
            tbody.querySelectorAll('[data-cancel]').forEach((b) =>
                b.addEventListener('click', () => this.cancelBulk(b.dataset.cancel)));
        }

        async showBulk(id) {
            this.openModal('Детали массового переноса', '<div class="text-center py-3"><i class="bi bi-arrow-clockwise spin"></i></div>');
            try {
                const res = await fetch(`/api/bulk-transfer/status/${id}`);
                const b = await res.json();
                if (!res.ok) throw new Error(b.error);
                const list = Array.isArray(b.transfers_data) ? b.transfers_data : [];
                this.setModalBody(`
                    <h6 class="mb-2">${escapeHtml(b.name || '')}</h6>
                    ${this.kv([
                        ['Статус', statusBadge(b.status)],
                        ['Создан', formatDateTime(b.created_at)],
                        ['Всего переносов', b.total_transfers ?? list.length],
                        ['Завершено', b.completed_transfers || 0],
                        ['Ошибок', b.failed_transfers || 0],
                    ])}
                    ${list.length ? `<hr class="divider"><div class="small text-muted mb-2">Переносы в наборе:</div>
                        ${list.map((t) => `<div class="transfer-item"><div class="route"><span>${escapeHtml(t.source_email)}</span><i class="bi bi-arrow-right arrow"></i><span>${escapeHtml(t.target_email)}</span></div>${t.query ? `<small class="text-muted">Фильтр: ${escapeHtml(t.query)}</small>` : ''}</div>`).join('')}` : ''}
                `);
            } catch (e) {
                this.setModalBody(`<div class="text-danger">Не удалось загрузить детали: ${escapeHtml(e.message)}</div>`);
            }
        }

        async cancelBulk(id) {
            if (!confirm('Отменить массовый перенос?')) return;
            try {
                const res = await fetch('/api/bulk-transfer/cancel', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ bulk_id: id })
                });
                const data = await res.json();
                if (res.ok) { toast('warning', 'Массовый перенос отменён'); this.loadBulk(); }
                else toast('danger', data.error || 'Не удалось отменить');
            } catch (e) {
                toast('danger', `Ошибка: ${e.message}`);
            }
        }

        /* ----------------------------- Helpers --------------------------- */
        kv(pairs) {
            return `<div class="row g-2">${pairs.map(([k, v]) => `
                <div class="col-sm-6 d-flex justify-content-between border-bottom py-1" style="border-color:var(--border)!important;">
                    <span class="text-muted">${k}</span><span class="fw-medium text-end">${v}</span>
                </div>`).join('')}</div>`;
        }

        emptyRow(cols, text, href, cta) {
            return `<tr><td colspan="${cols}">
                <div class="empty-state">
                    <i class="bi bi-inbox empty-icon"></i>
                    <p class="mb-2">${text}</p>
                    <a href="${href}" class="btn btn-outline-primary btn-sm"><i class="bi bi-plus-lg"></i>${cta}</a>
                </div></td></tr>`;
        }

        renderPagination(elId, current, total, showingId, totalId, shownCount, onChange) {
            const pages = Math.ceil(total / this.pageSize);
            $(showingId).textContent = shownCount;
            $(totalId).textContent = total;
            const ul = $(elId);
            if (pages <= 1) { ul.innerHTML = ''; return; }

            let html = '';
            const item = (label, page, disabled, active) =>
                `<li class="page-item ${disabled ? 'disabled' : ''} ${active ? 'active' : ''}">
                    <a class="page-link" href="#" data-page="${page}">${label}</a></li>`;

            html += item('‹', current - 1, current <= 1, false);
            for (let i = Math.max(1, current - 2); i <= Math.min(pages, current + 2); i++) {
                html += item(i, i, false, i === current);
            }
            html += item('›', current + 1, current >= pages, false);
            ul.innerHTML = html;
            ul.querySelectorAll('.page-link').forEach((a) =>
                a.addEventListener('click', (e) => {
                    e.preventDefault();
                    const p = parseInt(a.dataset.page);
                    if (p >= 1 && p <= pages && p !== current) onChange(p);
                }));
        }

        openModal(title, body) {
            $('detailsTitle').textContent = title;
            $('detailsBody').innerHTML = body;
            this.modal.show();
        }
        setModalBody(html) { $('detailsBody').innerHTML = html; }
    }

    document.addEventListener('DOMContentLoaded', () => { window.historyApp = new History(); });
})();
