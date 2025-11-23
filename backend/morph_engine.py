"""
Morph Engine - Handles image morphing with face landmark warping
"""

import cv2
import numpy as np
from PIL import Image
import requests
from io import BytesIO
import mediapipe as mp
from scipy.spatial import Delaunay
import imageio
import os

class MorphEngine:
    def __init__(self, num_frames=120, fps=30, base_size=(320, 320)):
        self.num_frames = num_frames
        self.fps = fps
        self.base_size = base_size
        self.mp_face_mesh = mp.solutions.face_mesh
        
    def load_image_from_url(self, url_or_path):
        """Load and resize image from URL or local file path"""
        # Helper function to load image with AVIF fallback
        def load_image_safe(file_path):
            """Load image, with fallback for AVIF using imageio"""
            try:
                return Image.open(file_path).convert('RGB')
            except Exception as e:
                # If PIL fails (e.g., AVIF), try imageio
                if file_path.lower().endswith('.avif'):
                    try:
                        img_array = imageio.imread(file_path)
                        return Image.fromarray(img_array).convert('RGB')
                    except Exception as e2:
                        raise Exception(f"Could not load AVIF image. Consider converting to JPG/PNG. Error: {e2}")
                raise
        
        # Check if it's a local file path
        if os.path.exists(url_or_path):
            # Local file
            img = load_image_safe(url_or_path)
            img = img.resize(self.base_size, Image.Resampling.LANCZOS)
            return img
        elif url_or_path.startswith('/static/'):
            # Flask static path - convert to absolute path
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            file_path = os.path.join(base_dir, url_or_path.lstrip('/'))
            if os.path.exists(file_path):
                img = load_image_safe(file_path)
                img = img.resize(self.base_size, Image.Resampling.LANCZOS)
                return img
        else:
            # URL - download it
            response = requests.get(url_or_path, timeout=10)
            img = Image.open(BytesIO(response.content)).convert('RGB')
            img = img.resize(self.base_size, Image.Resampling.LANCZOS)
            return img
    
    def pil_to_cv(self, img_pil):
        """Convert PIL to OpenCV BGR"""
        return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
    
    def cv_to_pil(self, img_cv):
        """Convert OpenCV BGR to PIL RGB"""
        return Image.fromarray(cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB))
    
    def get_face_landmarks(self, image_bgr):
        """Detect face landmarks using MediaPipe"""
        h, w, _ = image_bgr.shape
        with self.mp_face_mesh.FaceMesh(
            static_image_mode=True,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5
        ) as face_mesh:
            results = face_mesh.process(cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB))
            if not results.multi_face_landmarks:
                return None
            
            landmarks = results.multi_face_landmarks[0]
            points = []
            for lm in landmarks.landmark:
                x = int(lm.x * w)
                y = int(lm.y * h)
                points.append((x, y))
            return points
    
    def add_boundary_points(self, points, w, h):
        """Add boundary points to prevent edge artifacts"""
        extra = [
            (0, 0), (w//2, 0), (w-1, 0),
            (0, h//2),           (w-1, h//2),
            (0, h-1), (w//2, h-1), (w-1, h-1)
        ]
        return points + extra
    
    def warp_triangle(self, img_src, img_dst, tri_src, tri_dst):
        """Warp triangular region from source to destination"""
        tri_src = np.float32(tri_src)
        tri_dst = np.float32(tri_dst)
        
        r_src = cv2.boundingRect(tri_src)
        r_dst = cv2.boundingRect(tri_dst)
        
        tri_src_rect = []
        tri_dst_rect = []
        for i in range(3):
            tri_src_rect.append((tri_src[i][0] - r_src[0], tri_src[i][1] - r_src[1]))
            tri_dst_rect.append((tri_dst[i][0] - r_dst[0], tri_dst[i][1] - r_dst[1]))
        
        tri_src_rect = np.float32(tri_src_rect)
        tri_dst_rect = np.float32(tri_dst_rect)
        
        mask = np.zeros((r_dst[3], r_dst[2], 3), dtype=np.float32)
        cv2.fillConvexPoly(mask, np.int32(tri_dst_rect), (1.0, 1.0, 1.0), lineType=cv2.LINE_AA)
        
        img_src_rect = img_src[r_src[1]:r_src[1]+r_src[3], r_src[0]:r_src[0]+r_src[2]]
        
        M = cv2.getAffineTransform(tri_src_rect, tri_dst_rect)
        warped = cv2.warpAffine(
            img_src_rect, M, (r_dst[2], r_dst[3]),
            flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101
        )
        
        img_dst_rect = img_dst[r_dst[1]:r_dst[1]+r_dst[3], r_dst[0]:r_dst[0]+r_dst[2]]
        img_dst_rect = img_dst_rect * (1 - mask) + warped * mask
        img_dst[r_dst[1]:r_dst[1]+r_dst[3], r_dst[0]:r_dst[0]+r_dst[2]] = img_dst_rect
    
    def morph_with_landmarks(self, imgA_cv, imgB_cv, pointsA, pointsB, triangles, progress_callback=None):
        """Generate morph sequence using face landmarks"""
        imgA_float = imgA_cv.astype(np.float32)
        imgB_float = imgB_cv.astype(np.float32)
        
        pointsA_np = np.array(pointsA, dtype=np.float32)
        pointsB_np = np.array(pointsB, dtype=np.float32)
        
        h, w, _ = imgA_cv.shape
        frames_pil = []
        total_frames = self.num_frames
        
        print(f"  Generating {total_frames} morph frames...")
        for i in range(total_frames):
            t = i / (self.num_frames - 1) if self.num_frames > 1 else 0
            points_t = (1 - t) * pointsA_np + t * pointsB_np
            
            morphedA = np.zeros((h, w, 3), dtype=np.float32)
            morphedB = np.zeros((h, w, 3), dtype=np.float32)
            
            for tri_indices in triangles:
                x, y, z = tri_indices
                triA = [pointsA_np[x], pointsA_np[y], pointsA_np[z]]
                triB = [pointsB_np[x], pointsB_np[y], pointsB_np[z]]
                triT = [points_t[x], points_t[y], points_t[z]]
                
                self.warp_triangle(imgA_float, morphedA, triA, triT)
                self.warp_triangle(imgB_float, morphedB, triB, triT)
            
            morphed = (1 - t) * morphedA + t * morphedB
            morphed = np.clip(morphed, 0, 255).astype(np.uint8)
            frames_pil.append(self.cv_to_pil(morphed))
            
            # Call progress callback if provided
            if progress_callback:
                progress_callback(i + 1, total_frames, 'morph')
        
        return frames_pil
    
    def morph_simple_blend(self, imgA_cv, imgB_cv, progress_callback=None):
        """Simple alpha blending fallback"""
        arrA = np.array(self.cv_to_pil(imgA_cv)).astype(np.float32) / 255.0
        arrB = np.array(self.cv_to_pil(imgB_cv)).astype(np.float32) / 255.0
        
        frames_pil = []
        total_frames = self.num_frames
        print(f"  Generating {total_frames} morph frames (simple blend)...")
        for i in range(total_frames):
            t = i / (self.num_frames - 1) if self.num_frames > 1 else 0
            blended = (1 - t) * arrA + t * arrB
            blended = np.clip(blended * 255, 0, 255).astype(np.uint8)
            frames_pil.append(Image.fromarray(blended))
            
            # Call progress callback if provided
            if progress_callback:
                progress_callback(i + 1, total_frames, 'morph')
        
        return frames_pil
    
    def generate_morph(self, image1_url, image2_url, output_dir, session_id, progress_callback=None):
        """
        Main function to generate morph video
        Returns: dict with success status, video path, and metadata
        """
        try:
            # Load images
            print(f"  Loading images...")
            print(f"  Image1 URL/path: {image1_url}")
            print(f"  Image2 URL/path: {image2_url}")
            if progress_callback:
                progress_callback(0, 100, 'loading')
            
            try:
                imgA = self.load_image_from_url(image1_url)  # Can be URL or local path
                print(f"  ✓ Image1 loaded successfully")
            except Exception as e:
                error_msg = f"Failed to load image1 from {image1_url}: {str(e)}"
                print(f"  ✗ {error_msg}")
                raise Exception(error_msg)
            
            try:
                imgB = self.load_image_from_url(image2_url)  # Can be URL or local path
                print(f"  ✓ Image2 loaded successfully")
            except Exception as e:
                error_msg = f"Failed to load image2 from {image2_url}: {str(e)}"
                print(f"  ✗ {error_msg}")
                raise Exception(error_msg)
            
            imgA_cv = self.pil_to_cv(imgA)
            imgB_cv = self.pil_to_cv(imgB)
            
            # Detect faces
            print(f"  Detecting faces...")
            if progress_callback:
                progress_callback(5, 100, 'detecting')
            pointsA = self.get_face_landmarks(imgA_cv)
            pointsB = self.get_face_landmarks(imgB_cv)
            
            use_face_warp = (pointsA is not None and pointsB is not None)
            
            if use_face_warp:
                print(f"  ✓ Faces detected - using landmark warping")
                w, h = self.base_size
                pointsA_ext = self.add_boundary_points(pointsA, w, h)
                pointsB_ext = self.add_boundary_points(pointsB, w, h)
                
                pointsA_np = np.array(pointsA_ext, dtype=np.float32)
                pointsB_np = np.array(pointsB_ext, dtype=np.float32)
                points_avg = (pointsA_np + pointsB_np) / 2.0
                
                tri = Delaunay(points_avg)
                triangles = tri.simplices
                
                frames = self.morph_with_landmarks(
                    imgA_cv, imgB_cv,
                    pointsA_ext, pointsB_ext,
                    triangles,
                    progress_callback=progress_callback
                )
                morph_type = "face_landmark_warp"
            else:
                print(f"  ⚠ No faces detected - using simple blend")
                frames = self.morph_simple_blend(imgA_cv, imgB_cv, progress_callback=progress_callback)
                morph_type = "simple_blend"
            
            # Save as video
            print(f"  Saving video...")
            video_path = os.path.join(output_dir, f'{session_id}_morph.mp4')
            frames_np = [np.array(f) for f in frames]
            imageio.mimsave(video_path, frames_np, fps=self.fps)
            
            print(f"  ✓ Video saved: {video_path}")
            
            return {
                'success': True,
                'video_path': video_path,
                'frames': frames,
                'num_frames': len(frames),
                'morph_type': morph_type
            }
            
        except Exception as e:
            print(f"  ✗ Error in morph generation: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'error': str(e)
            }
