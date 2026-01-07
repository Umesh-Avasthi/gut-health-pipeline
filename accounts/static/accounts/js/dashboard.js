// Dashboard JavaScript functionality

function switchTab(tabName, buttonElement) {
    // Handle profile tab differently - open as side panel
    if (tabName === 'profile') {
        openProfilePanel();
        return;
    }
    
    // Hide all tabs
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    
    // Remove active class from all buttons
    document.querySelectorAll('.tab-button').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Show selected tab
    const selectedTab = document.getElementById(tabName + '-tab');
    if (selectedTab) {
        selectedTab.classList.add('active');
    }
    
    // Add active class to clicked button
    if (buttonElement) {
        buttonElement.classList.add('active');
    }
    
    // Save to localStorage
    localStorage.setItem('dashboardActiveTab', tabName);
}

function openProfilePanel() {
    const profileTab = document.getElementById('profile-tab');
    const overlay = document.getElementById('profile-overlay');
    
    if (profileTab && overlay) {
        profileTab.classList.add('active');
        overlay.classList.add('active');
        document.body.style.overflow = 'hidden'; // Prevent background scrolling
    }
}

function closeProfilePanel() {
    const profileTab = document.getElementById('profile-tab');
    const overlay = document.getElementById('profile-overlay');
    
    if (profileTab && overlay) {
        profileTab.classList.remove('active');
        overlay.classList.remove('active');
        document.body.style.overflow = ''; // Restore scrolling
        
        // Remove active class from profile button
        const profileButton = Array.from(document.querySelectorAll('.tab-button')).find(btn => 
            btn.textContent.includes('Profile')
        );
        if (profileButton) {
            profileButton.classList.remove('active');
        }
    }
}

function showFileNames(input) {
    const fileNamesDiv = document.getElementById('file-names');
    if (input.files.length > 0) {
        const fileNames = Array.from(input.files).map(file => file.name).join(', ');
        fileNamesDiv.textContent = `Selected: ${fileNames}`;
        fileNamesDiv.style.display = 'block';
    } else {
        fileNamesDiv.style.display = 'none';
    }
}

function hideWelcomeMessage() {
    const welcomeMsg = document.getElementById('welcome-message');
    if (welcomeMsg) {
        welcomeMsg.style.animation = 'fadeOut 0.3s ease';
        setTimeout(() => {
            welcomeMsg.style.display = 'none';
        }, 300);
    }
}

// Restore last active tab on page load and show welcome message
document.addEventListener('DOMContentLoaded', function() {
    // Show welcome message for 5 seconds
    const welcomeMsg = document.getElementById('welcome-message');
    if (welcomeMsg) {
        welcomeMsg.style.display = 'block';
        setTimeout(() => {
            hideWelcomeMessage();
        }, 5000);
    }
    
    // Restore last active tab
    const savedTab = localStorage.getItem('dashboardActiveTab');
    if (savedTab && savedTab !== 'upload') {
        const tabButtons = document.querySelectorAll('.tab-button');
        let targetButton = null;
        if (savedTab === 'jobs') {
            targetButton = tabButtons[1];
        } else if (savedTab === 'profile') {
            targetButton = tabButtons[2];
        }
        if (targetButton) {
            switchTab(savedTab, targetButton);
        }
    }
});

