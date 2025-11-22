// XAI Morphing Studio - Frontend JavaScript

let currentImages = {
    image1: null,
    image2: null,
    category: null
};

// DOM Elements
const randomBtn = document.getElementById('randomBtn');
const generateBtn = document.getElementById('generateBtn');
const loadingIndicator = document.getElementById('loadingIndicator');
const loadingText = document.getElementById('loadingText');
const resultsSection = document.getElementById('resultsSection');
const image1Box = document.getElementById('image1Box');
const image2Box = document.getElementById('image2Box');
const categoryInfo = document.getElementById('categoryInfo');
const morphVideo = document.getElementById('morphVideo');
const gradcamVideo = document.getElementById('gradcamVideo');

// Event Listeners
randomBtn.addEventListener('click', loadRandomImages);
generateBtn.addEventListener('click', generateMorph);

// Load random images
async function loadRandomImages() {
    try {
        randomBtn.disabled = true;
        randomBtn.textContent = '⏳ Loading...';
        
        const response = await fetch('/api/random-images');
        const data = await response.json();
        
        if (data.success) {
            currentImages.image1 = data.image1;
            currentImages.image2 = data.image2;
            currentImages.category = data.category;
            
            // Display images
            displayImage(image1Box, data.image1);
            displayImage(image2Box, data.image2);
            
            // Show category
            categoryInfo.textContent = `📁 Category: ${capitalizeFirst(data.category)}`;
            categoryInfo.style.display = 'block';
            
            // Enable generate button
            generateBtn.disabled = false;
            
            // Hide previous results
            resultsSection.style.display = 'none';
        } else {
            alert('Error loading images: ' + data.error);
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Failed to load images. Please try again.');
    } finally {
        randomBtn.disabled = false;
        randomBtn.textContent = '🎲 Get Random Images';
    }
}

// Display image in box
// function displayImage(box, url) {
//     box.innerHTML = `<img src="${url}" alt="Image">`;
//     box.classList.add('loaded');
// }

// NEW CODE with error handling:
function displayImage(box, url) {
    box.innerHTML = `<img src="${url}" alt="Image" onerror="this.onerror=null; this.src='data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 width=%22400%22 height=%22400%22%3E%3Crect width=%22400%22 height=%22400%22 fill=%22%23f3f4f6%22/%3E%3Ctext x=%2250%25%22 y=%2250%25%22 text-anchor=%22middle%22 dy=%22.3em%22 fill=%22%239ca3af%22 font-size=%2224%22%3EImage Load Error%3C/text%3E%3C/svg%3E';">`;
    box.classList.add('loaded');
}



// Generate morph video
async function generateMorph() {
    let eventSource = null;
    let finalResult = null;
    
    try {
        generateBtn.disabled = true;
        loadingIndicator.classList.add('active');
        loadingText.textContent = 'Starting...';
        
        const response = await fetch('/api/generate-morph', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                image1_url: currentImages.image1,
                image2_url: currentImages.image2
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            const sessionId = data.session_id;
            
            // Connect to progress stream
            eventSource = new EventSource(`/api/progress/${sessionId}`);
            
            eventSource.onmessage = function(event) {
                try {
                    const progress = JSON.parse(event.data);
                    
                    if (progress.error) {
                        console.error('Progress error:', progress.error);
                        loadingText.textContent = 'Error: ' + progress.error;
                        eventSource.close();
                        return;
                    }
                    
                    // Update progress display
                    if (progress.stage === 'waiting') {
                        loadingText.textContent = 'Initializing...';
                    } else if (progress.stage === 'loading') {
                        loadingText.textContent = 'Loading images...';
                    } else if (progress.stage === 'detecting') {
                        loadingText.textContent = 'Detecting faces...';
                    } else if (progress.stage === 'morph') {
                        loadingText.textContent = `Generating morph... Frame ${progress.current}/${progress.total}`;
                    } else if (progress.stage === 'gradcam') {
                        loadingText.textContent = `Computing Grad-CAM... Frame ${progress.current}/${progress.total}`;
                    } else if (progress.stage === 'complete') {
                        if (progress.result) {
                            finalResult = progress.result;
                            loadingText.textContent = 'Complete!';
                            eventSource.close();
                            
                            loadingIndicator.classList.remove('active');
                            
                            // Show results section first - use important to ensure visibility
                            console.log('Showing results section');
                            if (resultsSection) {
                                // Force show using multiple methods
                                resultsSection.removeAttribute('style');
                                resultsSection.style.cssText = 'display: block !important; visibility: visible !important; opacity: 1 !important;';
                                resultsSection.classList.add('fade-in');
                                
                                // Force reflow to ensure rendering
                                void resultsSection.offsetHeight;
                                
                                console.log('Results section display:', window.getComputedStyle(resultsSection).display);
                                console.log('Results section visibility:', window.getComputedStyle(resultsSection).visibility);
                                console.log('Results section opacity:', window.getComputedStyle(resultsSection).opacity);
                            } else {
                                console.error('resultsSection element not found!');
                            }
                            
                            // Display results
                            try {
                                displayResults(finalResult);
                            } catch (error) {
                                console.error('Error in displayResults:', error);
                                alert('Error displaying results: ' + error.message);
                            }
                            
                            // Scroll to results with multiple attempts
                            setTimeout(() => {
                                if (resultsSection) {
                                    // Force scroll
                                    resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
                                    // Also try scrolling window
                                    window.scrollTo({
                                        top: resultsSection.offsetTop - 100,
                                        behavior: 'smooth'
                                    });
                                    console.log('Scrolled to results section at:', resultsSection.offsetTop);
                                }
                            }, 300);
                            
                            generateBtn.disabled = false;
                        }
                    } else {
                        loadingText.textContent = 'Processing...';
                    }
                } catch (e) {
                    console.error('Error parsing progress:', e);
                }
            };
            
            eventSource.onerror = function(event) {
                console.log('Progress stream error or closed');
                if (!finalResult) {
                    // Stream closed but no result yet - might be an error
                    loadingText.textContent = 'Connection lost. Please try again.';
                    loadingIndicator.classList.remove('active');
                    generateBtn.disabled = false;
                }
                eventSource.close();
            };
            
        } else {
            alert('Error generating morph: ' + data.error);
            loadingIndicator.classList.remove('active');
            generateBtn.disabled = false;
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Failed to generate morph. Please try again.');
        loadingIndicator.classList.remove('active');
        if (eventSource) {
            eventSource.close();
        }
        generateBtn.disabled = false;
    }
}

// Display results
function displayResults(data) {
    try {
        console.log('Displaying results:', data);
        
        // Check if video elements exist
        if (!morphVideo || !gradcamVideo) {
            console.error('Video elements not found');
            throw new Error('Video elements not found in DOM');
        }
        
        // Check if data has required fields
        if (!data.morph_video || !data.gradcam_video) {
            console.error('Video URLs missing from data:', data);
            throw new Error('Video URLs missing from result data');
        }
        
        // Set video sources
        morphVideo.src = data.morph_video + '?t=' + Date.now();
        gradcamVideo.src = data.gradcam_video + '?t=' + Date.now();
        
        // Add error handlers for videos
        morphVideo.onerror = function() {
            console.error('Error loading morph video:', morphVideo.src);
            const errorMsg = document.createElement('p');
            errorMsg.style.color = 'red';
            errorMsg.textContent = 'Error loading morph video. Video file may not exist yet.';
            morphVideo.parentElement.appendChild(errorMsg);
        };
        
        gradcamVideo.onerror = function() {
            console.error('Error loading gradcam video:', gradcamVideo.src);
            const errorMsg = document.createElement('p');
            errorMsg.style.color = 'red';
            errorMsg.textContent = 'Error loading Grad-CAM video. Video file may not exist yet.';
            gradcamVideo.parentElement.appendChild(errorMsg);
        };
        
        // Add loaded handlers
        morphVideo.onloadeddata = function() {
            console.log('Morph video loaded successfully');
        };
        
        gradcamVideo.onloadeddata = function() {
            console.log('Grad-CAM video loaded successfully');
        };
        
        // Load and play videos
        morphVideo.load();
        gradcamVideo.load();
        
        console.log('Videos loading:', {
            morph: morphVideo.src,
            gradcam: gradcamVideo.src
        });
        
        // Morph info
        const morphInfo = document.getElementById('morphInfo');
        if (morphInfo) {
            morphInfo.innerHTML = `
                <div class="info-item">
                    <div class="info-label">Morph Type</div>
                    <div class="info-value">${formatMorphType(data.morph_type)}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Total Frames</div>
                    <div class="info-value">${data.num_frames}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Duration</div>
                    <div class="info-value">${(data.num_frames / 30).toFixed(2)} seconds</div>
                </div>
            `;
        }
        
        // Timeline info - Table format
        const timelineInfo = document.getElementById('timelineInfo');
        if (!timelineInfo) {
            console.error('timelineInfo element not found');
            return;
        }
        
        const analysis = data.analysis;
        if (!analysis || !analysis.detailed_frames) {
            console.error('Analysis data missing:', data);
            timelineInfo.innerHTML = '<p>Analysis data not available</p>';
            // Still show results section even if analysis is missing
            resultsSection.style.display = 'block';
            resultsSection.classList.add('fade-in');
            return;
        }
        
        // Prepare data for table
        const tableData = analysis.detailed_frames.map(frame => {
            const percentage = Math.round(frame.alpha * 100);
            let morphStage;
            if (frame.alpha === 0) {
                morphStage = 'Start (100% Source)';
            } else if (frame.alpha === 1) {
                morphStage = 'End (100% Target)';
            } else if (frame.alpha === 0.5) {
                morphStage = 'Middle (50/50)';
            } else {
                morphStage = `${percentage}%`;
            }
            
            return {
                morphDegree: percentage,
                morphStage: morphStage,
                prediction: frame.class_name,
                confidence: (frame.confidence * 100).toFixed(1)
            };
        });
        
        // Build table HTML
        let tableHTML = '<div class="prediction-table-container">';
        tableHTML += '<table class="prediction-table">';
        
        // Header row
        tableHTML += '<thead><tr>';
        tableHTML += '<th>Morph Degree</th>';
        tableData.forEach(data => {
            tableHTML += `<th>${data.morphDegree}%</th>`;
        });
        tableHTML += '</tr></thead>';
        
        // Model Prediction row
        tableHTML += '<tbody>';
        tableHTML += '<tr>';
        tableHTML += '<td class="row-label">Model Prediction</td>';
        tableData.forEach(data => {
            tableHTML += `<td class="prediction-cell">${data.prediction}</td>`;
        });
        tableHTML += '</tr>';
        
        // Model Confidence row
        tableHTML += '<tr>';
        tableHTML += '<td class="row-label">Model Confidence</td>';
        tableData.forEach(data => {
            tableHTML += `<td class="confidence-cell">${data.confidence}%</td>`;
        });
        tableHTML += '</tr>';
        
        tableHTML += '</tbody></table>';
        tableHTML += '</div>';
        
        // Add caveat note
        const caveatHTML = `
            <div class="caveat-note">
                <strong>Note:</strong> Model predictions are generated using ResNet50, a model pre-trained on ImageNet (1,000 object classes). Since ImageNet is optimized for general object recognition, not face recognition, when analyzing human faces, the model may classify them as objects rather than face-specific categories. However, the Grad-CAM attention visualization remains valid and shows what features the model focuses on.
            </div>
        `;
        
        timelineInfo.innerHTML = tableHTML + caveatHTML;
        
        console.log('Results displayed successfully');
    } catch (error) {
        console.error('Error displaying results:', error);
        console.error('Error stack:', error.stack);
        // Show error message in timeline section
        const timelineInfo = document.getElementById('timelineInfo');
        if (timelineInfo) {
            timelineInfo.innerHTML = `<p style="color: red;">Error displaying analysis: ${error.message}</p>`;
        }
        throw error; // Re-throw to be caught by caller
    }
}

// Helper functions
function capitalizeFirst(str) {
    return str.charAt(0).toUpperCase() + str.slice(1);
}

function formatMorphType(type) {
    const types = {
        'face_landmark_warp': 'Face Landmark Warping',
        'simple_blend': 'Simple Alpha Blending'
    };
    return types[type] || type;
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    console.log('XAI Morphing Studio loaded');
    categoryInfo.style.display = 'none';
});
