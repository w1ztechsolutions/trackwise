(function () {
    const lineItemsDataEl = document.getElementById('lineItemsData');
    const ALL_LINE_ITEMS = lineItemsDataEl ? JSON.parse(lineItemsDataEl.textContent) : [];

    function togglePayee() {
        const payeeType = document.querySelector('input[name="payee_type"]:checked').value;
        const supplierGroup = document.getElementById('supplierGroup');
        const staffGroup = document.getElementById('staffGroup');
        const billGroup = document.getElementById('billGroup');

        if (supplierGroup) supplierGroup.style.display = payeeType === 'supplier' ? 'block' : 'none';
        if (staffGroup) staffGroup.style.display = payeeType === 'staff' ? 'block' : 'none';
        if (billGroup) billGroup.style.display = 'none';
    }

    function filterBills() {
        const supplierId = document.getElementById('supplier_id').value;
        const billSelect = document.getElementById('bill_id');
        const billGroup = document.getElementById('billGroup');

        if (!supplierId) {
            if (billGroup) billGroup.style.display = 'none';
            return;
        }

        if (billGroup) billGroup.style.display = 'block';
        if (!billSelect) return;

        const options = billSelect.querySelectorAll('option');
        options.forEach(function (opt) {
            if (!opt.dataset.supplier || opt.value === '') {
                opt.style.display = '';
            } else if (opt.dataset.supplier === supplierId) {
                opt.style.display = '';
            } else {
                opt.style.display = 'none';
            }
        });
        billSelect.value = '';
    }

    function filterLineItems() {
        const categoryId = document.getElementById('category_id').value;
        const lineItemSelect = document.getElementById('line_item_id');
        if (!lineItemSelect) return;

        lineItemSelect.innerHTML = '<option value="">-- Select Line Item --</option>';

        if (!categoryId) {
            return;
        }

        const filtered = ALL_LINE_ITEMS.filter(function (item) {
            return String(item.category_id) === categoryId;
        });

        if (filtered.length === 0) {
            lineItemSelect.innerHTML = '<option value="">-- No line items for this category --</option>';
            return;
        }

        filtered.forEach(function (item) {
            const opt = document.createElement('option');
            opt.value = item.id;
            opt.textContent = item.name;
            lineItemSelect.appendChild(opt);
        });
    }

    document.querySelectorAll('input[name="payee_type"]').forEach(function (radio) {
        radio.addEventListener('change', togglePayee);
    });

    const supplierIdEl = document.getElementById('supplier_id');
    if (supplierIdEl) {
        supplierIdEl.addEventListener('change', filterBills);
    }

    const categoryIdEl = document.getElementById('category_id');
    if (categoryIdEl) {
        categoryIdEl.addEventListener('change', filterLineItems);
    }
})();
