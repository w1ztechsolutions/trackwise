document.addEventListener('click', function (e) {
    const btn = e.target.closest('button[data-bs-toggle="modal"]');
    if (!btn) return;
    const target = btn.getAttribute('data-bs-target');
    if (!target) return;
    const modalEl = document.querySelector(target);
    if (modalEl) {
        const modal = new bootstrap.Modal(modalEl);
        modal.show();
        e.preventDefault();
    }
});
