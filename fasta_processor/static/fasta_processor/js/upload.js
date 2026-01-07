// Upload page JavaScript

function showFileNames(input) {
    const fileNamesDiv = document.getElementById('file-names');
    if (input.files && input.files.length > 0) {
        const fileCount = input.files.length;
        if (fileCount > 3) {
            fileNamesDiv.innerHTML = '<span style="color: #c62828;">⚠️ Too many files! Maximum 3 files allowed. You selected ' + fileCount + ' files.</span>';
            fileNamesDiv.style.display = 'block';
            input.value = ''; // Clear selection
            return;
        }
        
        let fileList = '<strong>Selected ' + fileCount + ' file(s):</strong><br>';
        for (let i = 0; i < fileCount; i++) {
            fileList += '• ' + input.files[i].name + '<br>';
        }
        fileNamesDiv.innerHTML = fileList;
        fileNamesDiv.style.display = 'block';
    } else {
        fileNamesDiv.style.display = 'none';
    }
}

