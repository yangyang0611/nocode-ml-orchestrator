const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('fileInput');
let uploadedFile;
let datasetFilename;

dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('dragover');
});

dropZone.addEventListener('dragleave', () => {
    dropZone.classList.remove('dragover');
});

dropZone.addEventListener('drop', (e) => {
    console.log('File dropped');
    e.preventDefault();
    dropZone.classList.remove('dragover');
    handleFiles(e.dataTransfer.files);
});

fileInput.addEventListener('change', (e) => {
    console.log('File selected');
    handleFiles(e.target.files);
});

function handleFiles(files) {
    console.log('Handling files');
    if (files.length) {
        uploadFiles(files);
        // Extract the folder name from the first file's path
        const filePath = files[0].webkitRelativePath || files[0].name;
        const folderName = filePath.split('/')[0];

        // Log to verify what we get
        console.log('File path:', filePath);
        console.log('Folder name:', folderName);
        dropZone.innerHTML = `<p>Uploaded Folder: ${folderName}</p>`;
    }
}

function uploadFiles(files) {
    console.log('Starting upload');
    const formData = new FormData();
    for (let i = 0; i < files.length; i++) {
        formData.append('files', files[i]);
    }

    // Show the spinner
    const spinner = document.getElementById('uploadSpinner');
    if (spinner) {
        console.log('Showing upload spinner');
        spinner.style.display = 'block';
        spinner.style.visibility = 'visible';
        spinner.style.opacity = '1';
    } else {
        console.error('Upload spinner element not found');
    }

    fetch('http://localhost:5000/upload', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        // Hide the spinner
        console.log('Upload complete, hiding upload spinner');
        if (spinner) spinner.style.display = 'none';

        if (data.message) {
            showUploadStatus(true, 'Files uploaded successfully!');
            datasetFilename = data.datasetFilename;
        }
    })
    .catch(error => {
        // Hide the spinner
        console.log('Upload failed, hiding spinner');
        if (spinner) spinner.style.display = 'none';

        showUploadStatus(false, 'Error uploading files');
    });
}





function showUploadStatus(success, message) {
    const statusDiv = document.getElementById('uploadStatus');
    statusDiv.textContent = message;
    statusDiv.className = success ? 'alert alert-success' : 'alert alert-danger';
    statusDiv.style.display = 'block';
}

function addStep() {
    const steps = ['Resize', 'Rotate', 'Mirror', 'Add Noise'];
    steps.forEach(step => {
        const checkbox = document.getElementById(step.toLowerCase().replace(/\s+/g, ''));
        if (checkbox.checked) {
            let params = {};
            switch (step) {
                case 'Resize':
                    params.width = document.getElementById('resizeWidth').value;
                    params.height = document.getElementById('resizeHeight').value;
                    document.getElementById('resizeWidth').value = '';
                    document.getElementById('resizeHeight').value = '';
                    break;
                case 'Rotate':
                    params.angle = document.getElementById('rotateAngle').value;
                    document.getElementById('rotateAngle').value = '';
                    break;
                case 'Mirror':
                    break;
                    case 'Add Noise':
                    params.type = document.getElementById('noiseType').value;
                    if (params.type === 'Gaussian') {
                        params.mean = document.getElementById('noiseMean').value;
                        params.std = document.getElementById('noiseStd').value;
                        document.getElementById('noiseMean').value = '';
                        document.getElementById('noiseStd').value = '';
                    } else if (params.type === 'Brightness') {
                        params.factor1 = document.getElementById('brightnessFactor1').value;
                        params.factor2 = document.getElementById('brightnessFactor2').value;
                        document.getElementById('brightnessFactor1').value = '';
                        document.getElementById('brightnessFactor2').value = '';
                    } else if (params.type === 'Saturation') {
                        params.factor1 = document.getElementById('saturationFactor1').value;
                        params.factor2 = document.getElementById('saturationFactor2').value;
                        document.getElementById('saturationFactor1').value = '';
                        document.getElementById('saturationFactor2').value = '';
                    }
                    document.getElementById('noiseType').value = 'Gaussian';
                    break;
            }
            addStepToList(step, params);
            checkbox.checked = false;
        }
    });

    // Hide input sections
    document.getElementById('resizeInputs').style.display = 'none';
    document.getElementById('rotateInputs').style.display = 'none';
    document.getElementById('noiseInputs').style.display = 'none';
}

document.addEventListener('DOMContentLoaded', function() {
    document.getElementById('uploadSpinner').style.display = 'none';
    document.getElementById('processSpinner').style.display = 'none';
});

// Add event listeners to enable/disable input fields
document.getElementById('resize').addEventListener('change', function() {
    document.getElementById('resizeInputs').style.display = this.checked ? 'block' : 'none';
});

document.getElementById('rotate').addEventListener('change', function() {
    document.getElementById('rotateInputs').style.display = this.checked ? 'block' : 'none';
});

document.getElementById('addnoise').addEventListener('change', function() {
    document.getElementById('noiseInputs').style.display = this.checked ? 'block' : 'none';
    updateNoiseInputs();
});

function updateNoiseInputs() {
    const noiseType = document.getElementById('noiseType').value;
    document.getElementById('gaussianInputs').style.display = noiseType === 'Gaussian' ? 'block' : 'none';
    document.getElementById('brightnessInputs').style.display = noiseType === 'Brightness' ? 'block' : 'none';
    document.getElementById('saturationInputs').style.display = noiseType === 'Saturation' ? 'block' : 'none';
}

document.getElementById('noiseType').addEventListener('change', updateNoiseInputs);

// Add validation for input fields
document.getElementById('noiseMean').addEventListener('blur', function() {
    var meanValue = parseFloat(this.value);
    if (meanValue > 50 || meanValue < -50) {
        alert('Warning: The mean value for Gaussian noise should be between -50 and 50.');
        this.value = '';
    }
});

document.getElementById('noiseStd').addEventListener('blur', function() {
    var stdValue = parseFloat(this.value);
    if (stdValue > 50 || stdValue < 0) {
        alert('Warning: The standard deviation value for Gaussian noise should be between 0 and 50.');
        this.value = '';
    }
});

document.getElementById('brightnessFactor1').addEventListener('blur', function() {
    var brightnessFactor1 = parseFloat(this.value);
    if (brightnessFactor1 < -50 || brightnessFactor1 > 50) {
        alert('Warning: The brightness adjustment factor should be in the range of -50 to 50.');
        this.value = ''; // Clear the input field
    }
});

document.getElementById('brightnessFactor2').addEventListener('blur', function() {
    var brightnessFactor2 = parseFloat(this.value);
    if (brightnessFactor2 < -50 || brightnessFactor2 > 50) {
        alert('Warning: The brightness adjustment factor should be in the range of -50 to 50.');
        this.value = ''; // Clear the input field
    }
});

document.getElementById('saturationFactor1').addEventListener('blur', function() {
    var saturationFactor1 = parseFloat(this.value);
    if (saturationFactor1 < 0.0 || saturationFactor1 > 2.0) {
        alert('Warning: The saturation adjustment factor should be in the range of 0.0 to 2.0.');
        this.value = ''; // Clear the input field
    }
});

document.getElementById('saturationFactor2').addEventListener('blur', function() {
    var saturationFactor2 = parseFloat(this.value);
    if (saturationFactor2 < 0.0 || saturationFactor2 > 2.0) {
        alert('Warning: The saturation adjustment factor should be in the range of 0.0 to 2.0.');
        this.value = ''; // Clear the input field
    }
});

function addStepToList(step, params) {
    const list = document.getElementById('sortable-list');
    const newItem = document.createElement('li');
    newItem.classList.add('sortable-item', 'list-group-item');
    newItem.setAttribute('draggable', 'true');
    newItem.dataset.step = step;
    newItem.dataset.params = JSON.stringify(params);

    let paramString = Object.entries(params).map(([key, value]) => `${key}: ${value}`).join(', ');
    newItem.textContent = `${step} (${paramString})`;

    const deleteBtn = document.createElement('button');
    deleteBtn.textContent = 'X';
    deleteBtn.className = 'btn btn-danger btn-sm ml-2';
    deleteBtn.onclick = function() {
        list.removeChild(newItem);
    };
    newItem.appendChild(deleteBtn);

    list.appendChild(newItem);

    newItem.addEventListener('dragstart', () => newItem.classList.add('dragging'));
    newItem.addEventListener('dragend', () => newItem.classList.remove('dragging'));
}

function processImage() {
    if (!datasetFilename) {
        alert('Please upload a folder first.');
        return;
    }

    const steps = Array.from(document.querySelectorAll('.sortable-item'))
        .map(item => ({
            step: item.dataset.step,
            params: JSON.parse(item.dataset.params)
        }));

    if (steps.length === 0) {
        alert('Please add at least one processing step.');
        return;
    }

    const options = { sequence: steps };
    const spinner = document.getElementById('processSpinner');
    
    if (spinner) {
        console.log('Showing process spinner');
        spinner.style.display = 'block'; // Show the spinner
    } else {
        console.error('Process spinner element not found');
    }

    fetch('http://localhost:5000/process', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ datasetFilename, options })
    })
    .then(response => response.json())
    .then(() => {
        console.log('Processing complete, hiding process spinner');
        if (spinner) {
            spinner.style.display = 'none'; // Hide the spinner
        }
        document.getElementById('downloadDataset').disabled = false;
        document.getElementById('nextStepBanner').style.display = 'block';
        datasetFilename = 'processed_dataset.zip';
    })
    .catch(error => {
        console.log('Error processing images');
        if (spinner) {
            spinner.style.display = 'none'; // Hide the spinner
        }
        alert('Error processing images');
    });
}



function downloadDataset() {
    if (datasetFilename) {
        const downloadLink = document.createElement('a');
        downloadLink.href = `http://localhost:5000/download/processed_dataset.zip`;
        downloadLink.download = 'processed_dataset.zip';
        downloadLink.click();
    }
}

// Add event listeners to enable/disable input fields
document.getElementById('resize').addEventListener('change', function() {
    document.getElementById('resizeInputs').style.display = this.checked ? 'block' : 'none';
});

document.getElementById('rotate').addEventListener('change', function() {
    document.getElementById('rotateInputs').style.display = this.checked ? 'block' : 'none';
});

document.getElementById('addnoise').addEventListener('change', function() {
    document.getElementById('noiseInputs').style.display = this.checked ? 'block' : 'none';
    updateNoiseInputs();
});

function updateNoiseInputs() {
    const noiseType = document.getElementById('noiseType').value;
    document.getElementById('gaussianInputs').style.display = noiseType === 'Gaussian' ? 'block' : 'none';
    document.getElementById('brightnessInputs').style.display = noiseType === 'Brightness' ? 'block' : 'none';
    document.getElementById('saturationInputs').style.display = noiseType === 'Saturation' ? 'block' : 'none';
}

document.getElementById('noiseType').addEventListener('change', updateNoiseInputs);

// sorted the list by drag and drop Functions
const sortableList = document.getElementById('sortable-list');

sortableList.addEventListener('dragover', (e) => {
    e.preventDefault();
    const dragging = document.querySelector('.dragging');
    const afterElement = getDragAfterElement(sortableList, e.clientY);
    if (afterElement == null) {
        sortableList.appendChild(dragging);
    } else {
        sortableList.insertBefore(dragging, afterElement);
    }
});

function getDragAfterElement(container, y) {
    const draggableElements = [...container.querySelectorAll('.sortable-item:not(.dragging)')];

    return draggableElements.reduce((closest, child) => {
        const box = child.getBoundingClientRect();
        const offset = y - box.top - box.height / 2;
        if (offset < 0 && offset > closest.offset) {
            return {
                offset: offset,
                element: child
            };
        } else {
            return closest;
        }
    }, {
        offset: Number.NEGATIVE_INFINITY
    }).element;
}
