// Base JavaScript for common functionality across all pages

function updateMessagesContainer() {
    const container = document.querySelector('.messages-container');
    if (container && container.children.length === 0) {
        container.style.display = 'none';
    }
}

function hideAlert(alert) {
    // Add fade-out animation
    alert.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
    alert.style.opacity = '0';
    alert.style.transform = 'translateX(100%)';
    
    // Remove element after animation completes
    setTimeout(function() {
        alert.remove();
        updateMessagesContainer();
    }, 500); // Wait for animation to complete
}

(function() {
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(function(alert) {
        // Set timeout to hide after 5 seconds
        const timeoutId = setTimeout(function() {
            hideAlert(alert);
        }, 5000); // 5 seconds
        
        // Store timeout ID so we can clear it if user clicks close
        alert.dataset.timeoutId = timeoutId;
        
        // Clear timeout if user manually closes the alert
        const closeBtn = alert.querySelector('.alert-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', function() {
                clearTimeout(timeoutId);
            });
        }
    });
})();

