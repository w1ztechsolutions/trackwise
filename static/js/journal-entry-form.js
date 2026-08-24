(function () {
    const tbody = document.getElementById('linesBody');
    if (!tbody) return;

    const templateSelect = document.getElementById('accountTemplate');
    const optionsHtml = templateSelect ? templateSelect.innerHTML.trim() : '';

    function cloneSelect() {
        const sel = document.createElement('select');
        sel.name = 'account_id';
        sel.className = 'form-control account-select';
        sel.innerHTML = '<option value="">-- Select account --</option>' + optionsHtml;
        return sel;
    }

    function refreshSelects() {
        document.querySelectorAll('select.account-select').forEach(function (sel) {
            if (!sel.options.length || sel.options[0].value !== '') {
                sel.innerHTML = '<option value="">-- Select account --</option>' + optionsHtml;
            }
        });
    }

    function sumField(cls) {
        let total = 0;
        document.querySelectorAll('input.' + cls).forEach(function (i) {
            const v = parseFloat(i.value) || 0;
            total += v >= 0 ? v : 0;
        });
        return total;
    }

    function updateTotals() {
        const d = sumField('debit');
        const c = sumField('credit');
        const totalDebitEl = document.getElementById('totalDebit');
        const totalCreditEl = document.getElementById('totalCredit');
        const balanceBadge = document.getElementById('balanceBadge');

        if (totalDebitEl) totalDebitEl.textContent = d.toFixed(2);
        if (totalCreditEl) totalCreditEl.textContent = c.toFixed(2);
        if (balanceBadge) {
            if (Math.abs(d - c) <= 0.01) {
                balanceBadge.textContent = 'Balanced';
                balanceBadge.className = 'badge badge-success ms-3';
            } else {
                balanceBadge.textContent = 'Unbalanced';
                balanceBadge.className = 'badge badge-danger ms-3';
            }
        }
    }

    function addRow() {
        const tr = document.createElement('tr');
        tr.className = 'line-row';
        tr.innerHTML =
            '<td><select name="account_id" class="form-control account-select" required></select></td>' +
            '<td><input type="number" name="debit_amount" class="form-control debit" step="0.01" min="0" value="0"></td>' +
            '<td><input type="number" name="credit_amount" class="form-control credit" step="0.01" min="0" value="0"></td>' +
            '<td><button type="button" class="btn btn-sm btn-outline-danger remove-line" aria-label="Remove line">Remove</button></td>';
        tbody.appendChild(tr);
        refreshSelects();
    }

    tbody.addEventListener('input', updateTotals);
    const addLineBtn = document.getElementById('addLine');
    if (addLineBtn) {
        addLineBtn.addEventListener('click', addRow);
    }
    tbody.addEventListener('click', function (e) {
        const btn = e.target.closest('.remove-line');
        if (!btn) return;
        const tr = btn.closest('tr');
        if (tr && tbody.children.length > 1) {
            tr.remove();
            updateTotals();
        }
    });

    refreshSelects();
    updateTotals();
})();
