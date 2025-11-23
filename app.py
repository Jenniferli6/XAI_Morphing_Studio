"""
XAI Morphing Studio - Flask Web Application
"""

from flask import Flask, render_template, jsonify, request, send_file, url_for, Response
from flask_cors import CORS
import os
import random
import json
from datetime import datetime
import threading
from backend.morph_engine import MorphEngine
from backend.gradcam_engine import GradCAMEngine

app = Flask(__name__)
CORS(app)

# Configuration
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'outputs')
os.makedirs(OUTPUT_DIR, exist_ok=True)
IMAGES_DIR = os.path.join(os.path.dirname(__file__), 'static', 'images')

# Load local images from static/images directory
def load_local_images():
    """Scan static/images directory and build IMAGE_CATEGORIES dictionary"""
    image_categories = {}
    
    if not os.path.exists(IMAGES_DIR):
        print(f"Warning: Images directory not found: {IMAGES_DIR}")
        return image_categories
    
    # Scan each category folder
    for category in os.listdir(IMAGES_DIR):
        category_path = os.path.join(IMAGES_DIR, category)
        
        # Skip if not a directory
        if not os.path.isdir(category_path):
            continue
        
        # Get all image files in the category folder
        image_files = []
        for filename in sorted(os.listdir(category_path)):
            if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.avif', '.webp')):
                # Verify file actually exists before adding
                file_path = os.path.join(category_path, filename)
                if os.path.exists(file_path) and os.path.isfile(file_path):
                    # Create URL path for Flask static files
                    image_path = f'/static/images/{category}/{filename}'
                    image_files.append(image_path)
        
        if image_files:
            image_categories[category] = image_files
    
    return image_categories

# Load image categories from local files
IMAGE_CATEGORIES = load_local_images()






# Initialize engines
morph_engine = MorphEngine()
gradcam_engine = GradCAMEngine()

# Store progress for SSE
progress_store = {}

@app.route('/')
def index():
    """Main application page"""
    return render_template('index.html')

@app.route('/api/random-images', methods=['GET'])
def get_random_images():
    """
    Get random pair of images from the same category
    Returns: JSON with image URLs and category
    """
    try:
        # Reload images to ensure we have the latest files (in case files were renamed/deleted)
        current_categories = load_local_images()
        
        if not current_categories:
            return jsonify({
                'success': False,
                'error': 'No image categories found'
            }), 404
        
        # Randomly select a category
        category = random.choice(list(current_categories.keys()))
        images = current_categories[category]
        
        # Filter out any images that don't actually exist (safety check)
        valid_images = []
        for img_path in images:
            # Convert Flask static path to absolute file path
            if img_path.startswith('/static/'):
                file_path = os.path.join(os.path.dirname(__file__), img_path.lstrip('/'))
                if os.path.exists(file_path) and os.path.isfile(file_path):
                    valid_images.append(img_path)
        
        if len(valid_images) < 2:
            return jsonify({
                'success': False,
                'error': f'Not enough valid images in category "{category}" (found {len(valid_images)}, need at least 2)'
            }), 404
        
        # Select two different random images
        selected = random.sample(valid_images, 2)
        
        return jsonify({
            'success': True,
            'category': category,
            'image1': selected[0],
            'image2': selected[1]
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def run_morph_generation(session_id, image1_path, image2_path):
    """Run morph generation in background thread"""
    try:
        # Ensure output directory exists
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        
        # Initialize progress store
        progress_store[session_id] = {'current': 0, 'total': 100, 'stage': 'loading', 'result': None}
        
        print(f"[{session_id}] Starting morph generation...")
        print(f"[{session_id}] Image1 path: {image1_path}")
        print(f"[{session_id}] Image2 path: {image2_path}")
        print(f"[{session_id}] Output dir: {OUTPUT_DIR}")
        print(f"[{session_id}] Output dir exists: {os.path.exists(OUTPUT_DIR)}")
        print(f"[{session_id}] Output dir writable: {os.access(OUTPUT_DIR, os.W_OK)}")
        
        # Progress callback function - updates progress store
        def progress_callback(current, total, stage='morph'):
            progress_store[session_id] = {
                'current': current,
                'total': total,
                'stage': stage,
                'result': None
            }
            # Force update by accessing the dict (helps with thread safety)
            _ = progress_store[session_id]['current']
        
        # Step 1: Generate morph sequence
        print(f"[{session_id}] Generating morph frames...")
        morph_result = morph_engine.generate_morph(
            image1_path, 
            image2_path,
            output_dir=OUTPUT_DIR,
            session_id=session_id,
            progress_callback=progress_callback
        )
        
        if not morph_result['success']:
            progress_store[session_id] = {'error': morph_result.get('error', 'Unknown error'), 'stage': 'error'}
            return
        
        # Step 2: Generate Grad-CAM analysis
        print(f"[{session_id}] Computing Grad-CAM...")
        progress_store[session_id] = {'current': 0, 'total': morph_result['num_frames'], 'stage': 'gradcam', 'result': None}
        
        gradcam_result = gradcam_engine.analyze_morph(
            morph_result['frames'],
            output_dir=OUTPUT_DIR,
            session_id=session_id,
            progress_callback=progress_callback
        )
        
        if not gradcam_result['success']:
            progress_store[session_id] = {'error': gradcam_result.get('error', 'Unknown error'), 'stage': 'error'}
            return
        
        print(f"[{session_id}] Complete!")
        
        # Store final result
        progress_store[session_id] = {
            'current': morph_result['num_frames'],
            'total': morph_result['num_frames'],
            'stage': 'complete',
            'result': {
                'success': True,
                'session_id': session_id,
                'morph_video': f'/api/video/{session_id}_morph.mp4',
                'gradcam_video': f'/api/video/{session_id}_gradcam.mp4',
                'analysis': gradcam_result['analysis'],
                'num_frames': morph_result['num_frames'],
                'morph_type': morph_result['morph_type']
            }
        }
        
    except Exception as e:
        error_msg = str(e)
        print(f"[{session_id}] ERROR in run_morph_generation: {error_msg}")
        import traceback
        traceback.print_exc()
        progress_store[session_id] = {
            'error': error_msg,
            'stage': 'error',
            'current': 0,
            'total': 100
        }

@app.route('/api/generate-morph', methods=['POST'])
def generate_morph():
    """
    Generate morph video from two images (runs in background)
    Expects: JSON with image1_url, image2_url (can be local paths or URLs)
    Returns: JSON with session_id immediately, progress via SSE
    """
    try:
        data = request.get_json()
        image1_path = data.get('image1_url')  # Can be local path or URL
        image2_path = data.get('image2_url')  # Can be local path or URL
        
        if not image1_path or not image2_path:
            return jsonify({
                'success': False,
                'error': 'Missing image paths'
            }), 400
        
        # Convert Flask static paths to absolute file paths if needed
        # The morph_engine expects paths relative to project root or absolute paths
        if image1_path.startswith('/static/'):
            # Convert /static/images/category/file.jpg to absolute path
            base_dir = os.path.dirname(os.path.abspath(__file__))
            image1_path = os.path.join(base_dir, image1_path.lstrip('/'))
            print(f"Converted image1_path to: {image1_path}")
        if image2_path.startswith('/static/'):
            base_dir = os.path.dirname(os.path.abspath(__file__))
            image2_path = os.path.join(base_dir, image2_path.lstrip('/'))
            print(f"Converted image2_path to: {image2_path}")
        
        # Verify images exist before starting thread
        if not os.path.exists(image1_path):
            return jsonify({
                'success': False,
                'error': f'Image1 not found: {image1_path}'
            }), 400
        if not os.path.exists(image2_path):
            return jsonify({
                'success': False,
                'error': f'Image2 not found: {image2_path}'
            }), 400
        
        # Generate unique session ID
        session_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Start generation in background thread
        thread = threading.Thread(
            target=run_morph_generation,
            args=(session_id, image1_path, image2_path)
        )
        thread.daemon = True
        thread.start()
        
        # Return immediately with session_id
        return jsonify({
            'success': True,
            'session_id': session_id,
            'message': 'Generation started'
        })
        
    except Exception as e:
        print(f"Error in generate_morph: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/progress/<session_id>')
def get_progress(session_id):
    """Get progress updates via Server-Sent Events"""
    def generate():
        import time
        last_current = -1
        while True:
            if session_id in progress_store:
                progress = progress_store[session_id]
                
                if progress.get('error'):
                    data = json.dumps({
                        'error': progress['error'],
                        'stage': 'error'
                    })
                    yield f"data: {data}\n\n"
                    break
                
                # Only send update if progress changed
                current = progress.get('current', 0)
                if current != last_current or progress.get('stage') == 'complete':
                    data = json.dumps({
                        'current': current,
                        'total': progress.get('total', 100),
                        'stage': progress.get('stage', 'unknown')
                    })
                    yield f"data: {data}\n\n"
                    last_current = current
                
                # Stop if complete and send final result
                if progress.get('stage') == 'complete':
                    if progress.get('result'):
                        result_data = json.dumps({
                            'stage': 'complete',
                            'result': progress['result']
                        })
                        yield f"data: {result_data}\n\n"
                    break
            else:
                # Session not found yet, wait a bit
                yield f"data: {json.dumps({'stage': 'waiting'})}\n\n"
            
            time.sleep(0.1)  # Update every 100ms for smoother updates
    
    return Response(generate(), mimetype='text/event-stream', headers={
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no'
    })

@app.route('/api/video/<filename>')
def serve_video(filename):
    """Serve generated video files"""
    try:
        video_path = os.path.join(OUTPUT_DIR, filename)
        if os.path.exists(video_path):
            return send_file(video_path, mimetype='video/mp4')
        else:
            return jsonify({'error': 'Video not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/categories', methods=['GET'])
def get_categories():
    """Get available image categories"""
    return jsonify({
        'success': True,
        'categories': list(IMAGE_CATEGORIES.keys())
    })

if __name__ == '__main__':
    print("="*70)
    print("XAI MORPHING STUDIO - WEB APPLICATION")
    print("="*70)
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"Images directory: {IMAGES_DIR}")
    print(f"Available categories: {list(IMAGE_CATEGORIES.keys())}")
    print(f"Total images: {sum(len(images) for images in IMAGE_CATEGORIES.values())}")
    print("="*70)
    
    # Use PORT environment variable for deployment (Render, Railway, etc.)
    port = int(os.environ.get('PORT', 5006))
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    print(f"\n🚀 Starting server at http://0.0.0.0:{port}")
    if debug:
        print("Debug mode: ON")
    print("Press Ctrl+C to stop\n")
    
    app.run(debug=debug, host='0.0.0.0', port=port)
