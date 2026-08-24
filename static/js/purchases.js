(function () {
    let productsList = [];
    let suppliersList = [];

    const container = document.getElementById('purchase-items-container');
    if (!container) return;

    function populateSupplierDropdown() {
        const select = document.getElementById('supplier_id');
        if (!select) return;
        suppliersList.forEach(function (s) {
            const option = document.createElement('option');
            option.value = s.id;
            option.textContent = s.name;
            select.appendChild(option);
        });
    }

    function addPurchaseRow() {
        const rowId = Date.now() + Math.random().toString(36).substr(2, 5);

        const rowHTML = document.createElement('div');
        rowHTML.className = 'item-row-grid';
        rowHTML.id = 'row-' + rowId;
        rowHTML.innerHTML =
            '<div class="form-group">' +
                '<label class="form-label">Select Product</label>' +
                '<select name="product_id[]" required class="form-control product-select" data-row-id="' + rowId + '">' +
                    '<option value="">-- Choose --</option>' +
                    productsList.map(function (p) { return '<option value="' + p.id + '" data-price="' + p.default_selling_price + '">' + p.name + ' (' + p.sku + ')</option>'; }).join('') +
                '</select>' +
            '</div>' +
            '<div class="form-group">' +
                '<label class="form-label">Qty</label>' +
                '<input type="number" name="quantity[]" min="1" required class="form-control quantity-input" data-row-id="' + rowId + '" placeholder="0">' +
                '<span class="field-error" id="qty-error-' + rowId + '" role="alert"></span>' +
            '</div>' +
            '<div class="form-group">' +
                '<label class="form-label">Unit Cost (MWK)</label>' +
                '<input type="number" name="unit_cost[]" step="0.01" min="0" required class="form-control price-input" data-row-id="' + rowId + '" placeholder="0.00">' +
                '<span class="field-error" id="price-error-' + rowId + '" role="alert"></span>' +
            '</div>' +
            '<button type="button" class="btn-remove-row" data-row-id="' + rowId + '" aria-label="Remove item">' +
                '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">' +
                    '<polyline points="3 6 5 6 21 6"></polyline>' +
                    '<path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>' +
                '</svg>' +
            '</button>';

        container.appendChild(rowHTML);
    }

    function removeRow(rowId) {
        const row = document.getElementById('row-' + rowId);
        if (row) {
            row.remove();
            calculateTotal();
        }
    }

    function updateRowDefaults(rowId, selectElem) {
        calculateTotal();
    }

    function validatePurchaseRow(rowId) {
        const row = document.getElementById('row-' + rowId);
        if (!row) return;
        const qtyInput = row.querySelector('.quantity-input');
        const qtyError = document.getElementById('qty-error-' + rowId);
        const qty = parseInt(qtyInput.value) || 0;
        if (qty <= 0) {
            qtyInput.classList.add('input-error');
            qtyInput.setAttribute('aria-invalid', 'true');
            if (qtyError) qtyError.textContent = 'Quantity must be at least 1';
        } else {
            qtyInput.classList.remove('input-error');
            qtyInput.removeAttribute('aria-invalid');
            if (qtyError) qtyError.textContent = '';
        }
    }

    function calculateTotal() {
        const rows = container.querySelectorAll('.item-row-grid');
        let overallTotal = 0;

        rows.forEach(function (row) {
            const qtyInput = row.querySelector('input[name="quantity[]"]');
            const costInput = row.querySelector('input[name="unit_cost[]"]');
            const qty = parseInt(qtyInput.value) || 0;
            const cost = parseFloat(costInput.value) || 0;
            overallTotal += qty * cost;
        });

        const totalEl = document.getElementById('overall-total');
        if (totalEl) {
            totalEl.textContent = 'MWK ' + overallTotal.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        }
    }

    fetch('/api/products')
        .then(function (res) { return res.json(); })
        .then(function (data) {
            productsList = data;
            addPurchaseRow();
        });

    fetch('/api/suppliers')
        .then(function (res) { return res.json(); })
        .then(function (data) {
            suppliersList = data;
            populateSupplierDropdown();
        });

    const addBtn = document.getElementById('add-purchase-row');
    if (addBtn) {
        addBtn.addEventListener('click', addPurchaseRow);
    }

    container.addEventListener('click', function (e) {
        const btn = e.target.closest('.btn-remove-row');
        if (!btn) return;
        const rowId = btn.getAttribute('data-row-id');
        removeRow(rowId);
    });

    container.addEventListener('change', function (e) {
        const select = e.target.closest('.product-select');
        if (!select) return;
        const rowId = select.getAttribute('data-row-id');
        updateRowDefaults(rowId, select);
    });

    container.addEventListener('input', function (e) {
        const input = e.target;
        if (input.classList.contains('quantity-input')) {
            const rowId = input.getAttribute('data-row-id');
            validatePurchaseRow(rowId);
            calculateTotal();
        } else if (input.classList.contains('price-input')) {
            calculateTotal();
        }
    });
})();
