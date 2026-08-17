(function () {
    const modal = document.getElementById('coaSeederModal');
    if (!modal) return;

    const preview = document.getElementById('coa-preview');
    const countEl = document.getElementById('coa-count');
    const importBtn = document.getElementById('btn-import-coa');
    const feedback = document.getElementById('coa-feedback');

    function getSelected() {
        return Array.from(modal.querySelectorAll('.coa-leaf-check:checked')).map(cb => ({
            code: cb.value,
            name: cb.dataset.name,
            type: cb.dataset.type,
        }));
    }

    function renderPreview() {
        const selected = getSelected();
        countEl.textContent = `${selected.length} selected`;
        importBtn.disabled = selected.length === 0;

        if (selected.length === 0) {
            preview.innerHTML = '<p class="text-muted mb-0">No accounts selected.</p>';
            return;
        }

        const grouped = {};
        selected.forEach(item => {
            const major = item.type.charAt(0).toUpperCase() + item.type.slice(1);
            grouped[major] = grouped[major] || [];
            grouped[major].push(item);
        });

        let html = '';
        for (const [group, items] of Object.entries(grouped)) {
            html += `<div class="mb-2"><strong>${group}</strong>`;
            items.forEach(item => {
                html += `<div class="d-flex justify-content-between align-items-center ms-2">
                    <span>${item.name} <span class="text-muted">(${item.code})</span></span>
                    <button class="btn btn-sm btn-outline-danger btn-remove-coa" data-code="${item.code}" aria-label="Remove ${item.code}">×</button>
                </div>`;
            });
            html += '</div>';
        }
        preview.innerHTML = html;
    }

    modal.addEventListener('change', renderPreview);
    preview.addEventListener('click', (e) => {
        const btn = e.target.closest('.btn-remove-coa');
        if (!btn) return;
        const code = btn.dataset.code;
        const cb = modal.querySelector(`.coa-leaf-check[value="${code}"]`);
        if (cb) cb.checked = false;
        renderPreview();
    });

    importBtn.addEventListener('click', async () => {
        const selected = getSelected();
        if (selected.length === 0) return;

        importBtn.disabled = true;
        importBtn.textContent = 'Importing...';
        feedback.innerHTML = '';

        try {
            const response = await fetch('/accounting/chart-of-accounts/seed', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ selected_codes: selected.map(s => s.code) }),
            });
            const data = await response.json();
            feedback.innerHTML = `<div class="alert alert-${data.imported > 0 ? 'success' : 'info'} mb-0">${data.message}</div>`;
            if (data.imported > 0) {
                setTimeout(() => location.reload(), 1200);
            }
        } catch (err) {
            feedback.innerHTML = `<div class="alert alert-danger mb-0">Import failed: ${err.message}</div>`;
        } finally {
            importBtn.disabled = selected.length === 0;
            importBtn.textContent = 'Import Selected Accounts';
        }
    });

    renderPreview();
})();
