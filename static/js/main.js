/**
 * TrackWise Global UI JS
 */

console.log("TrackWise Accounting System initialized.");

// Global Modal Toggle
function toggleModal(modalId, show) {
    const modal = document.getElementById(modalId);
    if (modal) {
        if (show) {
            modal.classList.add('active');
        } else {
            modal.classList.remove('active');
        }
    }
}
