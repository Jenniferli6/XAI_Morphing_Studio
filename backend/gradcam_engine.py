"""
Grad-CAM Engine - CNN attention analysis for morph frames
"""

import torch
import numpy as np
from PIL import Image
from torchvision import models, transforms
from pytorch_grad_cam import GradCAM
from pytorch_grad_cam.utils.image import show_cam_on_image
from pytorch_grad_cam.utils.model_targets import ClassifierOutputTarget
import imageio
import os
import requests

class GradCAMEngine:
    def __init__(self, fps=30):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.fps = fps
        
        # Lazy loading - don't load model until needed
        self.model = None
        self.target_layers = None
        
        # Preprocessing (lightweight, can be initialized)
        self.preprocess = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        ])
        
        # Load ImageNet labels (lightweight)
        self.labels = self._load_imagenet_labels()
    
    def _ensure_model_loaded(self):
        """Lazy load the model only when needed"""
        if self.model is None:
            print("  Loading ResNet50...")
            # Force CPU mode on Render (no GPU available anyway)
            self.device = torch.device("cpu")
            # Use newer API, avoid deprecated pretrained=True
            self.model = models.resnet50(weights='IMAGENET1K_V2')
            self.model = self.model.to(self.device)
            self.model.eval()
            # Freeze model to reduce memory
            for param in self.model.parameters():
                param.requires_grad = False
            self.target_layers = [self.model.layer4[-1]]
            print("  ✓ Model ready (CPU mode)")
    
    def _load_imagenet_labels(self):
        """Load ImageNet class labels"""
        try:
            url = "https://raw.githubusercontent.com/anishathalye/imagenet-simple-labels/master/imagenet-simple-labels.json"
            response = requests.get(url, timeout=10)
            return response.json()
        except:
            return [f"class_{i}" for i in range(1000)]
    
    def get_class_name(self, class_idx):
        """Get human-readable class name"""
        return self.labels[class_idx]
    
    def analyze_frame(self, frame_pil):
        """
        Analyze single frame with Grad-CAM
        Returns: prediction class, confidence, CAM image
        """
        # Lazy load model if not already loaded
        self._ensure_model_loaded()
        
        # Preprocess
        input_tensor = self.preprocess(frame_pil).unsqueeze(0).to(self.device)
        
        # Get prediction
        with torch.no_grad():
            output = self.model(input_tensor)
            probabilities = torch.nn.functional.softmax(output[0], dim=0)
            confidence, predicted_idx = torch.max(probabilities, 0)
        
        # Compute Grad-CAM
        cam = GradCAM(model=self.model, target_layers=self.target_layers)
        targets = [ClassifierOutputTarget(predicted_idx.item())]
        
        # Prepare frame for overlay
        frame_resized = frame_pil.resize((224, 224))
        frame_np = np.array(frame_resized).astype(np.float32) / 255.0
        
        # Generate CAM
        grayscale_cam = cam(input_tensor=input_tensor, targets=targets)
        grayscale_cam = grayscale_cam[0, :]
        
        # Overlay on image
        cam_image = show_cam_on_image(frame_np, grayscale_cam, use_rgb=True)
        
        return {
            'class_idx': predicted_idx.item(),
            'class_name': self.get_class_name(predicted_idx.item()),
            'confidence': confidence.item(),
            'cam_image': cam_image
        }
    
    def analyze_morph(self, frames, output_dir, session_id, sample_frames=5, progress_callback=None):
        """
        Analyze morph sequence and generate Grad-CAM video
        
        Args:
            frames: List of PIL images
            output_dir: Output directory
            session_id: Session identifier
            sample_frames: Number of frames to analyze in detail
            progress_callback: Function(current, total, stage) for progress updates
        
        Returns: dict with success status and analysis results
        """
        try:
            num_frames = len(frames)
            print(f"  Analyzing {num_frames} frames...")
            
            # Generate Grad-CAM for all frames
            gradcam_frames = []
            
            for i, frame in enumerate(frames):
                if (i + 1) % 10 == 0 or i == 0:
                    print(f"    Frame {i+1}/{num_frames}")
                
                result = self.analyze_frame(frame)
                
                # Resize CAM image to original frame size
                cam_image_resized = Image.fromarray(result['cam_image']).resize(
                    frame.size, 
                    Image.Resampling.LANCZOS
                )
                gradcam_frames.append(np.array(cam_image_resized))
                
                # Progress callback for Grad-CAM
                if progress_callback:
                    progress_callback(i + 1, num_frames, 'gradcam')
            
            # Save Grad-CAM video
            print(f"  Saving Grad-CAM video...")
            gradcam_video_path = os.path.join(output_dir, f'{session_id}_gradcam.mp4')
            imageio.mimsave(gradcam_video_path, gradcam_frames, fps=self.fps)
            print(f"  ✓ Grad-CAM video saved")
            
            # Detailed analysis on sampled frames
            sample_indices = np.linspace(0, num_frames-1, sample_frames, dtype=int)
            detailed_analysis = []
            
            for idx in sample_indices:
                result = self.analyze_frame(frames[idx])
                detailed_analysis.append({
                    'frame_index': int(idx),
                    'alpha': float(idx / (num_frames - 1)),
                    'class_name': result['class_name'],
                    'confidence': float(result['confidence'])
                })
            
            # Compute statistics
            all_predictions = [self.analyze_frame(f)['class_name'] for f in frames[::5]]
            unique_classes = list(set(all_predictions))
            
            return {
                'success': True,
                'gradcam_video_path': gradcam_video_path,
                'analysis': {
                    'detailed_frames': detailed_analysis,
                    'unique_classes': unique_classes,
                    'num_class_changes': len(unique_classes),
                    'dominant_class': max(set(all_predictions), key=all_predictions.count)
                }
            }
            
        except Exception as e:
            print(f"  ✗ Error in Grad-CAM analysis: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'error': str(e)
            }
