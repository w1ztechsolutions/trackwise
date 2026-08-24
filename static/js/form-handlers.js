document.addEventListener('submit', function (e) {
    const form = e.target;
    if (form.matches('[data-confirm]')) {
        const message = form.getAttribute('data-confirm');
        if (!confirm(message)) {
            e.preventDefault();
        }
    }
});

document.addEventListener('change', function (e) {
    const target = e.target;
    if (target.matches('[data-autosubmit]')) {
        target.form.dispatchEvent(new Event('submit', { cancelable: true }));
    }
    if (target.matches('[data-nav-url]')) {
        const url = target.value;
        if (url) {
            window.location.href = url;
        }
    }
});

document.addEventListener('click', function (e) {
    const btn = e.target.closest('[data-action="print"]');
    if (btn) {
        window.print();
    }
});
