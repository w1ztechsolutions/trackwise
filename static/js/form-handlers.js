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
        // REVIEW: nav select values are server-rendered app routes, but never trust
        // REVIEW: DOM values for navigation — only same-origin relative paths
        // REVIEW: (blocks javascript: and protocol-relative //evil.com payloads).
        if (url && url.charAt(0) === '/' && url.charAt(1) !== '/') {
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
