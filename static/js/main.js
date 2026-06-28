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