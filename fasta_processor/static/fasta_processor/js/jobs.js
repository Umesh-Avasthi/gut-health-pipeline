// Jobs page JavaScript functionality

// Tab switching functionality
function showTab(tabName) {
    // Hide all tab contents
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });
    
    // Remove active class from all tabs
    document.querySelectorAll('.tab').forEach(tab => {
        tab.classList.remove('active');
    });
    
    // Show selected tab content
    document.getElementById('tab-' + tabName).classList.add('active');
    
    // Add active class to clicked tab button
    event.currentTarget.classList.add('active');
}

// Progress polling for running jobs
function initializeProgressPolling(runningJobs, progressUrlTemplate) {
    if (runningJobs.length === 0) {
        return; // No running jobs, no need to poll
    }
    
    function updateProgress(jobId) {
        const url = progressUrlTemplate.replace('999', jobId);
        fetch(url)
            .then(response => response.json())
            .then(data => {
                const progressBar = document.getElementById(`progress-bar-${jobId}`);
                const progressText = document.getElementById(`progress-text-${jobId}`);
                const progressMessage = document.getElementById(`progress-message-${jobId}`);
                
                if (progressBar && progressText && progressMessage) {
                    const progress = data.progress || 0;
                    progressBar.style.width = progress + '%';
                    progressText.textContent = progress + '%';
                    progressMessage.textContent = data.progress_message || 'Processing...';
                    
                    // If completed or failed, stop polling and reload page after a delay
                    if (data.completed || data.failed) {
                        setTimeout(() => {
                            window.location.reload();
                        }, 2000);
                    }
                }
            })
            .catch(error => {
                console.error('Error fetching progress:', error);
            });
    }
    
    // Poll every 3 seconds for each running job
    runningJobs.forEach(jobId => {
        updateProgress(jobId); // Initial update
        setInterval(() => updateProgress(jobId), 3000);
    });
}

