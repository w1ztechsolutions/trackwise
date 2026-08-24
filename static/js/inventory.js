(function () {
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        searchInput.addEventListener('input', function () {
            const filter = this.value.toLowerCase();
            const rows = document.querySelectorAll('.product-row');
            rows.forEach(function (row) {
                const sku = row.cells[0].textContent.toLowerCase();
                const name = row.querySelector('.product-name').textContent.toLowerCase();
                row.style.display = (sku.includes(filter) || name.includes(filter)) ? '' : 'none';
            });
        });
    }

    const editModal = document.getElementById('editProductModal');
    if (editModal) {
        editModal.addEventListener('show.bs.modal', function (event) {
            const button = event.relatedTarget;
            const id = button.getAttribute('data-id');
            const name = button.getAttribute('data-name');
            const description = button.getAttribute('data-description');
            const price = button.getAttribute('data-price');
            const threshold = button.getAttribute('data-threshold');

            document.getElementById('edit_product_id').value = id;
            document.getElementById('edit_name').value = name;
            document.getElementById('edit_description').value = description;
            document.getElementById('edit_default_selling_price').value = price;
            document.getElementById('edit_low_stock_threshold').value = threshold;
        });
    }
})();
