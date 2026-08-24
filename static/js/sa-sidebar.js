const saToggle = document.getElementById('saSidebarToggle');
const saSidebar = document.querySelector('.sidebar');
const saOverlay = document.getElementById('saSidebarOverlay');

function closeSaSidebar() {
    saSidebar.classList.remove('open');
    saOverlay.classList.remove('open');
}

if (saToggle && saSidebar && saOverlay) {
    saToggle.addEventListener('click', () => {
        saSidebar.classList.toggle('open');
        saOverlay.classList.toggle('open');
    });
    saOverlay.addEventListener('click', closeSaSidebar);
    saSidebar.querySelectorAll('.nav-link').forEach(link => {
        link.addEventListener('click', closeSaSidebar);
    });
}
