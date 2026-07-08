// Sidebar toggle for mobile
const toggleBtn = document.getElementById('sidebarToggle');
if (toggleBtn) {
  toggleBtn.addEventListener('click', () => {
    document.querySelector('.sidebar').classList.toggle('open');
  });
  document.querySelectorAll('.sidebar .nav-link').forEach((link) => {
    link.addEventListener('click', () => {
      document.querySelector('.sidebar').classList.remove('open');
    });
  });
}

// Flash messages auto-dismiss
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.flash-close').forEach((btn) => {
    btn.addEventListener('click', () => {
      const flash = btn.closest('.flash-message');
      if (flash) flash.remove();
    });
  });
});

// CSRF token for AJAX / fetch requests
function getCsrfToken() {
  const meta = document.querySelector('meta[name="csrf-token"]');
  if (meta && meta.content) return meta.content;
  const input = document.querySelector('input[name="csrf_token"]');
  if (input && input.value) return input.value;
  return null;
}

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

// Loading states for forms
(function () {
  const forms = document.querySelectorAll('form');
  forms.forEach((form) => {
    const btn = form.querySelector('button[type="submit"]');
    if (!btn) return;

    form.addEventListener('submit', () => {
      const overlay = document.createElement('div');
      overlay.className = 'loading-overlay';
      overlay.innerHTML = '<div class="spinner"></div>';
      document.body.appendChild(overlay);
      btn.disabled = true;
    });
  });
})();