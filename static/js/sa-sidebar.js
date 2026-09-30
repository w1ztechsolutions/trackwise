const saToggle = document.getElementById('saSidebarToggle');
const saSidebar = document.querySelector('.sidebar');
const saOverlay = document.getElementById('saSidebarOverlay');
const mainContent = document.getElementById('main-content');

function closeSaSidebar() {
    saSidebar.classList.remove('open');
    saOverlay.classList.remove('open');
    if (mainContent) {
        mainContent.removeAttribute('inert');
    }
    saToggle.focus();
}

function openSaSidebar() {
    saSidebar.classList.add('open');
    saOverlay.classList.add('open');
    if (mainContent) {
        mainContent.setAttribute('inert', '');
    }
    const firstLink = saSidebar.querySelector('.nav-link');
    if (firstLink) {
        firstLink.focus();
    }
}

if (saToggle && saSidebar && saOverlay) {
    saToggle.addEventListener('click', () => {
        const isOpen = saSidebar.classList.contains('open');
        if (isOpen) {
            closeSaSidebar();
        } else {
            openSaSidebar();
        }
    });

    saToggle.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            saToggle.click();
        }
    });

    saOverlay.addEventListener('click', closeSaSidebar);
    saOverlay.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
            closeSaSidebar();
        }
    });

    saSidebar.querySelectorAll('.nav-link').forEach(link => {
        link.addEventListener('click', closeSaSidebar);
    });

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && saSidebar.classList.contains('open')) {
            closeSaSidebar();
        }
    });
}
