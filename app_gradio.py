"""
XAI Morphing Studio - Gradio Interface for Hugging Face Spaces
"""

import os
import random
import gradio as gr
from backend.morph_engine import MorphEngine
from backend.gradcam_engine import GradCAMEngine
import tempfile
from PIL import Image

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
                    # Create absolute file path
                    image_files.append(file_path)
        
        if image_files:
            image_categories[category] = image_files
    
    return image_categories

# Initialize engines
morph_engine = MorphEngine()
gradcam_engine = GradCAMEngine()

# Load image categories
IMAGE_CATEGORIES = load_local_images()

def get_random_images():
    """Get random pair of images from the same category"""
    if not IMAGE_CATEGORIES:
        return None, None, "No image categories found"
    
    # Randomly select a category
    category = random.choice(list(IMAGE_CATEGORIES.keys()))
    images = IMAGE_CATEGORIES[category]
    
    # Filter out any images that don't actually exist
    valid_images = [img for img in images if os.path.exists(img) and os.path.isfile(img)]
    
    if len(valid_images) < 2:
        return None, None, f"Not enough images in category '{category}'"
    
    # Select two different random images
    selected = random.sample(valid_images, 2)
    
    return selected[0], selected[1], f"Category: {category}"

def generate_morph(image1_path, image2_path, progress=gr.Progress()):
    """Generate morph and Grad-CAM visualization"""
    if image1_path is None or image2_path is None:
        return None, None, "Please select two images"
    
    try:
        # Generate unique session ID
        import time
        session_id = f"gradio_{int(time.time())}"
        
        progress(0, desc="Starting morph generation...")
        
        # Create progress callback wrapper for morph engine
        # The engine expects: progress_callback(current, total, stage)
        def morph_progress(curr, total, stage):
            # Map to 0-60% of overall progress
            overall_progress = 0.1 + 0.5 * (curr / total) if total > 0 else 0.1
            progress(overall_progress, desc=f"Generating morph frames... {curr}/{total}")
        
        # Step 1: Generate morph sequence
        morph_result = morph_engine.generate_morph(
            image1_path,
            image2_path,
            output_dir=OUTPUT_DIR,
            session_id=session_id,
            progress_callback=morph_progress
        )
        
        if not morph_result['success']:
            return None, None, f"Error: {morph_result.get('error', 'Unknown error')}"
        
        # Create progress callback wrapper for Grad-CAM engine
        def gradcam_progress(curr, total, stage):
            # Map to 60-95% of overall progress
            overall_progress = 0.6 + 0.35 * (curr / total) if total > 0 else 0.6
            progress(overall_progress, desc=f"Computing Grad-CAM... {curr}/{total}")
        
        # Step 2: Generate Grad-CAM analysis
        gradcam_result = gradcam_engine.analyze_morph(
            morph_result['frames'],
            output_dir=OUTPUT_DIR,
            session_id=session_id,
            progress_callback=gradcam_progress
        )
        
        if not gradcam_result['success']:
            return None, None, f"Error: {gradcam_result.get('error', 'Unknown error')}"
        
        progress(1.0, desc="Complete!")
        
        # Get video paths
        morph_video = os.path.join(OUTPUT_DIR, f"{session_id}_morph.mp4")
        gradcam_video = os.path.join(OUTPUT_DIR, f"{session_id}_gradcam.mp4")
        
        if os.path.exists(morph_video) and os.path.exists(gradcam_video):
            return morph_video, gradcam_video, "Generation complete!"
        else:
            return None, None, "Videos not found after generation"
            
    except Exception as e:
        import traceback
        error_msg = f"Error: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        return None, None, error_msg

# Create Gradio interface
with gr.Blocks(title="XAI Morphing Studio") as demo:
    gr.Markdown("""
    # XAI Morphing Studio
    
    **Visualize CNN Attention During Image Morphing**
    
    This tool generates smooth morphing animations between two images and visualizes how a ResNet50 CNN pays attention to different features throughout the morphing process using Grad-CAM.
    """)
    
    with gr.Row():
        with gr.Column():
            gr.Markdown("### Image Selection")
            image1 = gr.Image(label="Source Image", type="filepath")
            image2 = gr.Image(label="Target Image", type="filepath")
            
            with gr.Row():
                random_btn = gr.Button("🎲 Get Random Images", variant="primary")
                generate_btn = gr.Button("🚀 Generate Morph", variant="primary")
            
            category_info = gr.Markdown("")
        
        with gr.Column():
            gr.Markdown("### Results")
            morph_video = gr.Video(label="Morph Animation")
            gradcam_video = gr.Video(label="Grad-CAM Visualization")
            status = gr.Textbox(label="Status", interactive=False)
    
    # Event handlers
    random_btn.click(
        fn=get_random_images,
        outputs=[image1, image2, category_info]
    )
    
    generate_btn.click(
        fn=generate_morph,
        inputs=[image1, image2],
        outputs=[morph_video, gradcam_video, status]
    )
    
    gr.Markdown("""
    ### How to Use:
    1. Click "Get Random Images" to select two random images from the same category
    2. Or upload your own images
    3. Click "Generate Morph" to create the morphing sequence and Grad-CAM visualization
    4. Watch the results appear below!
    
    **Note:** Generation takes 30-60 seconds depending on your hardware.
    """)

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, share=False)

