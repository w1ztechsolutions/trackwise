(function () {
    let productsList = [];
    const container = document.getElementById('sale-items-container');
    if (!container) return;

    function addSaleRow() {
        const rowId = Date.now() + Math.random().toString(36).substr(2, 5);

        const rowHTML = document.createElement('div');
        rowHTML.className = 'item-row-grid';
        rowHTML.id = 'row-' + rowId;
        rowHTML.innerHTML =
            '<div class="form-group">' +
                '<label class="form-label">Select Product</label>' +
                '<select name="product_id[]" required class="form-control product-select" data-row-id="' + rowId + '">' +
                    '<option value="">-- Choose --</option>' +
                    productsList.map(function (p) {
                        const stockBadge = p.quantity_in_stock <= 0 ? ' (OUT OF STOCK)' : ' (' + p.quantity_in_stock + ' available)';
                        return '<option value="' + p.id + '" data-price="' + p.default_selling_price + '" data-stock="' + p.quantity_in_stock + '">' + p.name + stockBadge + '</option>';
                    }).join('') +
                '</select>' +
                '<span class="stock-info" id="stock-info-' + rowId + '"></span>' +
            '</div>' +
            '<div class="form-group">' +
                '<label class="form-label">Qty</label>' +
                '<input type="number" name="quantity[]" min="1" required class="form-control quantity-input" data-row-id="' + rowId + '" placeholder="0…">' +
                '<span class="field-error" id="qty-error-' + rowId + '" role="alert"></span>' +
            '</div>' +
            '<div class="form-group">' +
                '<label class="form-label">Unit Price (MWK)</label>' +
                '<input type="number" name="unit_price[]" step="0.01" min="0" required class="form-control price-input" data-row-id="' + rowId + '" placeholder="0.00…">' +
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
        const selectedOption = selectElem.options[selectElem.selectedIndex];
        const row = document.getElementById('row-' + rowId);
        if (!selectedOption || selectElem.value === '') {
            const stockInfo = document.getElementById('stock-info-' + rowId);
            if (stockInfo) stockInfo.textContent = '';
            const priceInput = row.querySelector('.price-input');
            if (priceInput) priceInput.value = '';
            calculateTotal();
            return;
        }

        const price = selectedOption.getAttribute('data-price');
        const stock = parseInt(selectedOption.getAttribute('data-stock')) || 0;
        const priceInput = row.querySelector('.price-input');
        const stockInfo = document.getElementById('stock-info-' + rowId);

        if (priceInput) priceInput.value = price;
        if (stockInfo) {
            stockInfo.textContent = stock + ' units in stock';
            if (stock <= 0) {
                stockInfo.classList.add('text-danger');
                stockInfo.classList.remove('text-success');
            } else {
                stockInfo.classList.add('text-success');
                stockInfo.classList.remove('text-danger');
            }
        }

        validateQuantity(rowId);
        calculateTotal();
    }

    function validateQuantity(rowId) {
        const row = document.getElementById('row-' + rowId);
        if (!row) return;
        const selectElem = row.querySelector('.product-select');
        const qtyInput = row.querySelector('.quantity-input');
        const stockInfo = document.getElementById('stock-info-' + rowId);
        const qtyError = document.getElementById('qty-error-' + rowId);

        if (!selectElem.value) return;

        const selectedOption = selectElem.options[selectElem.selectedIndex];
        const stock = parseInt(selectedOption.getAttribute('data-stock')) || 0;
        const qty = parseInt(qtyInput.value) || 0;

        if (qty > stock) {
            if (stockInfo) {
                stockInfo.textContent = 'Insufficient stock! (' + stock + ' available)';
                stockInfo.classList.add('text-danger');
                stockInfo.classList.remove('text-success');
            }
            qtyInput.classList.add('input-error');
            qtyInput.setAttribute('aria-invalid', 'true');
            if (qtyError) qtyError.textContent = 'Only ' + stock + ' units available';
        } else {
            if (stockInfo) {
                stockInfo.textContent = stock + ' units in stock';
                stockInfo.classList.add('text-success');
                stockInfo.classList.remove('text-danger');
            }
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
            const priceInput = row.querySelector('input[name="unit_price[]"]');
            const qty = parseInt(qtyInput.value) || 0;
            const price = parseFloat(priceInput.value) || 0;
            overallTotal += qty * price;
        });

        const totalEl = document.getElementById('overall-total');
        if (totalEl) {
            totalEl.textContent = 'MWK ' + overallTotal.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        }
    }

    function validateSaleSubmission() {
        const rows = container.querySelectorAll('.item-row-grid');
        let isValid = true;

        if (rows.length === 0) {
            alert('Please add at least one item to record a sale.');
            return false;
        }

        rows.forEach(function (row) {
            const selectElem = row.querySelector('.product-select');
            const qtyInput = row.querySelector('.quantity-input');
            const qtyError = row.querySelector('.field-error');

            if (selectElem.value === '') {
                isValid = false;
                selectElem.classList.add('input-error');
                selectElem.setAttribute('aria-invalid', 'true');
            }

            const selectedOption = selectElem.options[selectElem.selectedIndex];
            if (selectedOption) {
                const stock = parseInt(selectedOption.getAttribute('data-stock')) || 0;
                const qty = parseInt(qtyInput.value) || 0;

                if (qty <= 0) {
                    isValid = false;
                    qtyInput.classList.add('input-error');
                    qtyInput.setAttribute('aria-invalid', 'true');
                    if (qtyError) qtyError.textContent = 'Quantity must be greater than 0';
                } else if (qty > stock) {
                    isValid = false;
                    qtyInput.classList.add('input-error');
                    qtyInput.setAttribute('aria-invalid', 'true');
                    if (qtyError) qtyError.textContent = 'Only ' + stock + ' units available';
                } else {
                    qtyInput.classList.remove('input-error');
                    qtyInput.removeAttribute('aria-invalid');
                    if (qtyError) qtyError.textContent = '';
                }
            }
        });

        if (!isValid) {
            alert('Please fix the errors in the sales items (check stock levels and input quantities).');
        }

        return isValid;
    }

    fetch('/api/products')
        .then(function (res) { return res.json(); })
        .then(function (data) {
            productsList = data;
            addSaleRow();
        });

    const addBtn = document.getElementById('add-sale-row');
    if (addBtn) {
        addBtn.addEventListener('click', addSaleRow);
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
            validateQuantity(rowId);
            calculateTotal();
        } else if (input.classList.contains('price-input')) {
            calculateTotal();
        }
    });

    const saleForm = document.getElementById('sale-checkout-form');
    if (saleForm) {
        saleForm.addEventListener('submit', function (e) {
            return validateSaleSubmission();
        });
    }
})();
