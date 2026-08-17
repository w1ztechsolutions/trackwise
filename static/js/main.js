// ============================================================
// CSRF Protection (no tokens exposed in initial HTML DOM)
// ============================================================

function getCsrfToken() {
    const input = document.querySelector('input[name="csrf_token"]');
    return input ? input.value : null;
}

function ensureCsrfInForm(form) {
    if (!form || form.method.toLowerCase() !== 'post') return;
    if (form.querySelector('input[name="csrf_token"]')) return;
    const token = getCsrfToken();
    if (!token) return;
    const input = document.createElement('input');
    input.type = 'hidden';
    input.name = 'csrf_token';
    input.value = token;
    form.appendChild(input);
}

document.addEventListener('submit', function (e) {
    const form = e.target;
    if (form && form.tagName === 'FORM') {
        ensureCsrfInForm(form);
    }
});

const originalFetch = window.fetch;
window.fetch = function (...args) {
    const [url, options = {}] = args;
    const csrfToken = getCsrfToken();
    if (csrfToken) {
        const headers = new Headers(options.headers || {});
        if (!headers.has('X-CSRFToken') && !headers.has('X-CSRF-Token')) {
            headers.set('X-CSRFToken', csrfToken);
        }
        options.headers = headers;
    }
    return originalFetch(url, options);
};

// ============================================================
// Sidebar toggle for mobile (with keyboard accessibility)
// ============================================================
const toggleBtn = document.getElementById('sidebarToggle');
if (toggleBtn) {
    function setSidebarAria() {
        const sidebar = document.querySelector('.sidebar');
        const expanded = sidebar && sidebar.classList.contains('open');
        toggleBtn.setAttribute('aria-expanded', String(Boolean(expanded)));
    }
    toggleBtn.addEventListener('click', () => {
        const sidebar = document.querySelector('.sidebar');
        sidebar.classList.toggle('open');
        setSidebarAria();
    });
    // Keyboard accessibility: Enter and Space
    toggleBtn.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            const sidebar = document.querySelector('.sidebar');
            sidebar.classList.toggle('open');
            setSidebarAria();
        }
    });
    document.querySelectorAll('.sidebar .nav-link').forEach((link) => {
        link.addEventListener('click', () => {
            const sidebar = document.querySelector('.sidebar');
            sidebar.classList.remove('open');
            setSidebarAria();
        });
    });
    setSidebarAria();
}

// ============================================================
// Theme toggle (persisted in localStorage; respects OS preference)
// ============================================================
(function () {
    const btn = document.getElementById('themeToggle');
    if (!btn) return;

    const label = btn.querySelector('#themeLabel');
    const html = document.documentElement;

    const prefersLight = () => window.matchMedia('(prefers-color-scheme: light)').matches;

    function applyTheme(theme) {
        const isLight = theme === 'light';
        html.classList.toggle('theme-light', isLight);
        if (label) label.textContent = isLight ? 'Light Mode' : 'Dark Mode';
        btn.setAttribute('aria-pressed', String(isLight));
        localStorage.setItem('theme', theme);
    }

    function resolveTheme() {
        const saved = localStorage.getItem('theme');
        if (saved === 'light' || saved === 'dark') return saved;
        return prefersLight() ? 'light' : 'dark';
    }

    applyTheme(resolveTheme());

    btn.addEventListener('click', () => {
        applyTheme(html.classList.contains('theme-light') ? 'dark' : 'light');
    });
})();

// ============================================================
// Flash messages auto-dismiss
// ============================================================
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.flash-close').forEach((btn) => {
        btn.addEventListener('click', () => {
            const flash = btn.closest('.flash-message');
            if (flash) flash.remove();
        });
    });
});

// ============================================================
// Focus trap for Bootstrap modals
// ============================================================
document.addEventListener('shown.bs.modal', function (e) {
    const modal = e.target;
    const focusableSelector = 'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';
    const focusableElements = modal.querySelectorAll(focusableSelector);
    if (focusableElements.length === 0) return;

    const firstFocusable = focusableElements[0];
    const lastFocusable = focusableElements[focusableElements.length - 1];

    // Return focus to trigger on hide
    const trigger = document.querySelector(`[data-bs-target="${modal.id}"]`);
    if (trigger && trigger.id) {
        modal._focusReturnTarget = trigger;
    }

    modal.addEventListener('keydown', function trapHandler(e) {
        if (e.key !== 'Tab') return;
        if (e.shiftKey) {
            if (document.activeElement === firstFocusable) {
                e.preventDefault();
                lastFocusable.focus();
            }
        } else {
            if (document.activeElement === lastFocusable) {
                e.preventDefault();
                firstFocusable.focus();
            }
        }
    });
});

document.addEventListener('hidden.bs.modal', function (e) {
    const modal = e.target;
    modal.removeEventListener('keydown', modal._trapHandler);
    if (modal._focusReturnTarget) {
        modal._focusReturnTarget.focus();
        delete modal._focusReturnTarget;
    }
});

// ============================================================
// Confirmation dialogs for destructive actions
// ============================================================
document.addEventListener('click', function (e) {
    const trigger = e.target.closest('[data-confirm]');
    if (!trigger) return;
    e.preventDefault();
    const message = trigger.getAttribute('data-confirm') || 'Are you sure you want to proceed? This action cannot be undone.';
    const confirmed = window.confirm(message);
    if (confirmed && trigger.form) {
        trigger.form.submit();
    } else if (confirmed && !trigger.form) {
        const href = trigger.getAttribute('href');
        if (href) window.location.href = href;
    }
});

// ============================================================
// Inline form validation helper
// ============================================================
function showFieldError(input, message) {
    input.classList.add('input-error');
    input.setAttribute('aria-invalid', 'true');
    let errorEl = input.parentElement.querySelector('.input-error-message');
    if (!errorEl) {
        errorEl = document.createElement('span');
        errorEl.className = 'input-error-message';
        input.parentElement.appendChild(errorEl);
    }
    errorEl.textContent = message;
    if (input.hasAttribute('aria-describedby')) {
        const hintId = input.getAttribute('aria-describedby');
        const hint = document.getElementById(hintId);
        if (hint) hint.setAttribute('hidden', '');
    }
}

function clearFieldError(input) {
    input.classList.remove('input-error');
    input.removeAttribute('aria-invalid');
    const errorEl = input.parentElement.querySelector('.input-error-message');
    if (errorEl) errorEl.remove();
    if (input.hasAttribute('aria-describedby')) {
        const hintId = input.getAttribute('aria-describedby');
        const hint = document.getElementById(hintId);
        if (hint) hint.removeAttribute('hidden');
    }
}

// Clear errors on input
document.addEventListener('input', function (e) {
    if (e.target.matches('.input-error')) {
        clearFieldError(e.target);
    }
});

// ============================================================
// Chart.js touch-friendly configuration
// ============================================================
function getTouchFriendlyChartOptions(baseOptions) {
    const isTouchDevice = ('ontouchstart' in window) || (navigator.maxTouchPoints > 0);
    if (!isTouchDevice) return baseOptions;

    const options = JSON.parse(JSON.stringify(baseOptions || {}));
    if (!options.plugins) options.plugins = {};
    if (!options.plugins.tooltip) options.plugins.tooltip = {};
    options.plugins.tooltip.mode = 'nearest';
    options.plugins.tooltip.intersect = false;

    if (!options.interaction) options.interaction = {};
    options.interaction.mode = 'nearest';
    options.interaction.intersect = false;

    if (!options.elements) options.elements = {};
    if (!options.elements.point) options.elements.point = {};
    options.elements.point.hitRadius = 12;
    options.elements.point.radius = 5;
    options.elements.point.hoverRadius = 8;

    return options;
}

// ============================================================
// Chart.js doughnut initialization from data attributes
// ============================================================
function initDoughnutChart(canvas) {
    const ctx = canvas.getContext('2d');
    const labels = JSON.parse(canvas.dataset.labels || '[]');
    const data = JSON.parse(canvas.dataset.values || '[]');
    const colors = JSON.parse(canvas.dataset.colors || '[]');

    new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: data,
                backgroundColor: colors,
                borderWidth: 0,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'right',
                    labels: {
                        color: '#9ca3af',
                        font: { family: 'Outfit', size: 12 },
                    }
                }
            }
        }
    });
}

document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('canvas[data-chart-type="doughnut"]').forEach(initDoughnutChart);
});

// ============================================================
// Loading states for forms
// ============================================================
(function () {
    const forms = document.querySelectorAll('form');
    forms.forEach((form) => {
        const btn = form.querySelector('button[type="submit"]');
        if (!btn) return;

        form.addEventListener('submit', () => {
            const overlay = document.createElement('div');
            overlay.className = 'loading-overlay';
            overlay.setAttribute('role', 'status');
            overlay.setAttribute('aria-live', 'polite');
            const spinner = document.createElement('div');
            spinner.className = 'spinner';
            const hint = document.createElement('span');
            hint.className = 'visually-hidden';
            hint.textContent = 'Loading...';
            spinner.appendChild(hint);
            overlay.appendChild(spinner);
            document.body.appendChild(overlay);
            btn.disabled = true;
        });
    });
})();
