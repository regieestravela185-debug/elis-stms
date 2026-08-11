"""
AI-Assisted Identity Verification Module
Uses InsightFace for face recognition, MediaPipe for liveness/blink detection,
and OpenCV for camera handling.
"""

from __future__ import annotations

import cv2
import numpy as np
from pathlib import Path
from typing import Tuple, Optional, Dict, Any

# OpenCV is always available
CV2_AVAILABLE = True

# Try importing InsightFace for face recognition
try:
    from insightface.app import FaceAnalysis
    INSIGHTFACE_AVAILABLE = True
except ImportError:
    INSIGHTFACE_AVAILABLE = False
    FaceAnalysis = None

# Try importing MediaPipe for liveness detection
try:
    import mediapipe as mp
    MEDIAPIPE_AVAILABLE = True
except ImportError:
    MEDIAPIPE_AVAILABLE = False
    mp = None

# Try importing PIL for image processing
try:
    from PIL import Image, ImageChops
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# Global InsightFace app instance (lazy loaded)
_face_app = None


def _get_face_app():
    """Lazy load InsightFace FaceAnalysis app."""
    global _face_app
    if _face_app is None and INSIGHTFACE_AVAILABLE:
        try:
            _face_app = FaceAnalysis(
                name='buffalo_l',
                providers=['CPUExecutionProvider']
            )
            _face_app.prepare(ctx_id=-1, det_size=(640, 640))
        except Exception as e:
            print(f"InsightFace initialization error: {e}")
            return None
    return _face_app


def detect_fake_id(image_path: str) -> dict:
    """
    Advanced fake ID detection using multiple checks:
    - Image dimensions / aspect ratio (screenshots)
    - EXIF metadata (real phone photos have camera EXIF)
    - File format (AI-generated images often PNG, real photos JPEG)
    - Error Level Analysis (ELA) - detects edited regions
    - Sensor noise check (real photos have noise; AI/screenshots are too clean)
    Returns dict with fake_score (0-1, higher = more suspicious) and reasons.
    """
    reasons = []
    fake_score = 0.0
    
    if not PIL_AVAILABLE:
        return {"fake_score": 0.0, "is_fake": False, "reasons": ["PIL not available"]}
    
    try:
        img = Image.open(image_path)
        img_format = (img.format or "").upper()
        
        # 1. Check image dimensions
        width, height = img.size
        if width < 300 or height < 200:
            reasons.append("Image resolution too low")
            fake_score += 0.25
        
        # 2. Check aspect ratio
        aspect = max(width, height) / min(width, height)
        if aspect > 2.5:
            reasons.append("Unusual aspect ratio (possible screenshot)")
            fake_score += 0.2
        
        # 3. EXIF metadata - real phone photos have camera tags
        # NOTE: Many legitimate IDs are scanned/photographed without EXIF, so this is just a warning
        exif_data = img._getexif() if hasattr(img, '_getexif') else None
        has_camera_exif = False
        if exif_data:
            if 271 in exif_data or 272 in exif_data or 306 in exif_data:
                has_camera_exif = True
        
        if not has_camera_exif:
            # Reduced penalty - missing EXIF is common for scanned IDs, photos of IDs, etc.
            fake_score += 0.1  # minor penalty, not a rejection reason by itself
        
        # 4. File format check - real ID photos from phones are JPEG/JPG.
        # PNG, WEBP, GIF are common for AI-generated, downloaded, or edited images.
        if img_format in ("PNG", "WEBP", "GIF", "BMP", "TIFF"):
            reasons.append(f"{img_format} format (real phone photos are JPEG, not {img_format})")
            fake_score += 0.25
        
        # 5. Sensor noise check - real camera photos have natural noise.
        # AI-generated and screenshots are unnaturally smooth.
        noise_score = compute_noise_score(image_path)
        if noise_score < 1.0:
            reasons.append(f"Suspiciously clean/smooth image (noise={noise_score:.2f}, likely AI-generated)")
            fake_score += 0.35
        elif noise_score < 2.0:
            reasons.append(f"Low natural noise (noise={noise_score:.2f})")
            fake_score += 0.15
        
        # 6. Error Level Analysis (ELA) - detect tampering
        ela_score = compute_ela_score(image_path)
        if ela_score > 15.0:
            reasons.append(f"High tampering indicators (ELA={ela_score:.1f})")
            fake_score += 0.4
        elif ela_score > 10.0:
            reasons.append(f"Moderate tampering indicators (ELA={ela_score:.1f})")
            fake_score += 0.2
        
        # 7. QR Code validation - real Philippine government IDs have valid QR codes.
        # Fake/AI-generated IDs often have no QR or garbage QR that doesn't decode.
        qr_check = check_qr_code(image_path)
        if qr_check["has_qr_visual"] and not qr_check["decoded"]:
            reasons.append("QR code present but unreadable (likely fake/garbage QR)")
            fake_score += 0.35
        elif qr_check["decoded"] and not qr_check["valid_format"]:
            reasons.append(f"QR decodes but content is suspicious ({qr_check['data_preview']})")
            fake_score += 0.15
        elif qr_check["decoded"] and qr_check["valid_format"]:
            # Valid QR is a STRONG positive signal - reduce fake_score
            reasons.append(f"✓ Valid government QR code detected")
            fake_score = max(0.0, fake_score - 0.3)
        
        fake_score = min(fake_score, 1.0)
        
        return {
            "fake_score": fake_score,
            "is_fake": fake_score >= 0.5,  # balanced threshold - only reject clearly suspicious IDs
            "reasons": reasons,
            "ela_score": ela_score,
            "noise_score": noise_score,
            "has_exif": has_camera_exif,
            "format": img_format,
            "dimensions": (width, height),
            "qr_check": qr_check,
        }
    except Exception as e:
        return {
            "fake_score": 0.0,
            "is_fake": False,
            "reasons": [f"Fake ID check error: {str(e)}"],
        }


def check_qr_code(image_path: str) -> dict:
    """Detect and validate QR codes on ID image. Real gov IDs have decodable QRs."""
    result = {"has_qr_visual": False, "decoded": False, "data": "", "data_preview": "", "valid_format": False}
    try:
        img = cv2.imread(image_path)
        if img is None:
            return result
        qr_detector = cv2.QRCodeDetector()
        data, points, _ = qr_detector.detectAndDecode(img)
        if points is not None and len(points) > 0:
            result["has_qr_visual"] = True
        if data:
            result["decoded"] = True
            result["data"] = data
            result["data_preview"] = data[:80] + ("..." if len(data) > 80 else "")
            result["valid_format"] = _is_valid_gov_qr(data)
        if not result["decoded"]:
            try:
                ok, decoded_info, points_multi, _ = qr_detector.detectAndDecodeMulti(img)
                if ok and decoded_info:
                    for d in decoded_info:
                        if d:
                            result["decoded"] = True
                            result["data"] = d
                            result["data_preview"] = d[:80] + ("..." if len(d) > 80 else "")
                            result["valid_format"] = _is_valid_gov_qr(d)
                            break
            except Exception:
                pass
        return result
    except Exception:
        return result


def _is_valid_gov_qr(data: str) -> bool:
    """Check if QR data looks like a valid Philippine government ID QR."""
    if not data:
        return False
    data_lower = data.lower()
    gov_keywords = [
        "philsys", "psa", "lto", "sss", "gsis", "pagibig", "pag-ibig",
        "comelec", "voter", "license", "driver", "national id", "umid",
        "postal", "philhealth", "tin", "bir",
    ]
    if any(kw in data_lower for kw in gov_keywords):
        return True
    if data.startswith("http") and any(g in data_lower for g in ["gov.ph", "psa.gov", "lto.gov"]):
        return True
    if len(data) > 50 and ("," in data or "|" in data or ":" in data):
        return True
    return False


def compute_noise_score(image_path: str) -> float:
    """
    Compute sensor noise score. Real camera photos have natural noise.
    Uses high-pass filter (Laplacian) on small uniform regions.
    """
    try:
        img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            return 5.0  # don't penalize if we can't read
        # Apply a small Gaussian blur to get the "denoised" version
        denoised = cv2.GaussianBlur(img, (5, 5), 0)
        # Difference = noise component
        noise = cv2.absdiff(img, denoised)
        # Use standard deviation of noise as the score
        noise_std = float(np.std(noise))
        return noise_std
    except Exception:
        return 5.0


def compute_ela_score(image_path: str, quality: int = 90) -> float:
    """
    Error Level Analysis: re-saves image at known quality and compares
    differences. Tampered/edited regions show higher error levels.
    Returns mean error score (higher = more tampering indicators).
    """
    if not PIL_AVAILABLE:
        return 0.0
    try:
        original = Image.open(image_path).convert('RGB')
        # Save and reload at known JPEG quality
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            tmp_path = tmp.name
        original.save(tmp_path, 'JPEG', quality=quality)
        recompressed = Image.open(tmp_path).convert('RGB')
        # Compute pixel-wise difference
        diff = ImageChops.difference(original, recompressed)
        diff_arr = np.array(diff)
        # Mean error (excluding very dark pixels)
        mean_err = float(np.mean(diff_arr))
        # Cleanup
        try:
            Path(tmp_path).unlink()
        except Exception:
            pass
        return mean_err
    except Exception:
        return 0.0


def detect_faces_opencv(image_path: str) -> Optional[list]:
    """
    Detect faces in an image using OpenCV Haar Cascade.
    Returns list of face coordinates or None if no face detected.
    """
    try:
        image = cv2.imread(image_path)
        if image is None:
            return None
        
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
        
        return faces.tolist() if len(faces) > 0 else None
    except Exception as e:
        print(f"Face detection error: {e}")
        return None


def detect_faces_insightface(image_path: str) -> Optional[list]:
    """
    Detect faces using InsightFace (more accurate than OpenCV).
    Returns list of face objects with embeddings.
    """
    if not INSIGHTFACE_AVAILABLE:
        return None
    
    try:
        app = _get_face_app()
        if app is None:
            return None
        
        img = cv2.imread(image_path)
        if img is None:
            return None
        
        faces = app.get(img)
        return faces if len(faces) > 0 else None
    except Exception as e:
        print(f"InsightFace detection error: {e}")
        return None


def get_face_embedding(image_path: str) -> Optional[np.ndarray]:
    """
    Get face embedding using InsightFace.
    Returns 512-dimensional embedding vector or None.
    """
    if not INSIGHTFACE_AVAILABLE:
        return None
    
    try:
        faces = detect_faces_insightface(image_path)
        if faces and len(faces) > 0:
            # Return embedding of the largest face
            largest_face = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
            return largest_face.embedding
        return None
    except Exception as e:
        print(f"Face embedding error: {e}")
        return None


def compare_faces_insightface(id_image_path: str, selfie_image_path: str) -> Tuple[float, bool]:
    """
    Compare faces using InsightFace embeddings.
    Returns (similarity_score, is_match)
    """
    if not INSIGHTFACE_AVAILABLE:
        return 0.0, False
    
    try:
        # Get embeddings for both images
        id_embedding = get_face_embedding(id_image_path)
        selfie_embedding = get_face_embedding(selfie_image_path)
        
        if id_embedding is None:
            print("No face detected in ID image")
            return 0.0, False
        
        if selfie_embedding is None:
            print("No face detected in selfie")
            return 0.0, False
        
        # Compute cosine similarity
        similarity = np.dot(id_embedding, selfie_embedding) / (
            np.linalg.norm(id_embedding) * np.linalg.norm(selfie_embedding)
        )
        
        # Convert to 0-1 range (cosine similarity is -1 to 1)
        similarity = (similarity + 1) / 2
        
        # Threshold for match (0.5 = 50% similarity after normalization)
        # This corresponds to ~0.0 cosine similarity, which is quite lenient
        # For stricter matching, use 0.6 or higher
        is_match = similarity >= 0.45
        
        return float(similarity), is_match
    except Exception as e:
        print(f"Face comparison error: {e}")
        return 0.0, False


def detect_blink_mediapipe(image: np.ndarray) -> Dict[str, Any]:
    """
    Detect eye blink using MediaPipe Face Mesh.
    Used for liveness detection.
    Returns dict with blink detection results.
    """
    if not MEDIAPIPE_AVAILABLE:
        return {"available": False, "blink_detected": False}
    
    try:
        mp_face_mesh = mp.solutions.face_mesh
        
        with mp_face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        ) as face_mesh:
            
            # Convert BGR to RGB
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            results = face_mesh.process(rgb_image)
            
            if not results.multi_face_landmarks:
                return {"available": True, "face_detected": False, "blink_detected": False}
            
            landmarks = results.multi_face_landmarks[0].landmark
            
            # Eye landmarks for blink detection
            # Left eye: 159 (top), 145 (bottom)
            # Right eye: 386 (top), 374 (bottom)
            left_eye_top = landmarks[159]
            left_eye_bottom = landmarks[145]
            right_eye_top = landmarks[386]
            right_eye_bottom = landmarks[374]
            
            # Calculate eye aspect ratio (EAR)
            left_ear = abs(left_eye_top.y - left_eye_bottom.y)
            right_ear = abs(right_eye_top.y - right_eye_bottom.y)
            avg_ear = (left_ear + right_ear) / 2
            
            # Blink threshold (eyes closed when EAR < 0.02)
            blink_detected = avg_ear < 0.02
            
            return {
                "available": True,
                "face_detected": True,
                "blink_detected": blink_detected,
                "eye_aspect_ratio": float(avg_ear),
                "left_ear": float(left_ear),
                "right_ear": float(right_ear),
            }
    except Exception as e:
        print(f"MediaPipe blink detection error: {e}")
        return {"available": True, "error": str(e), "blink_detected": False}


def detect_face_mediapipe(image: np.ndarray) -> Dict[str, Any]:
    """
    Detect face and landmarks using MediaPipe Face Mesh.
    Returns dict with face detection results and landmarks.
    """
    if not MEDIAPIPE_AVAILABLE:
        return {"available": False, "face_detected": False}
    
    try:
        mp_face_mesh = mp.solutions.face_mesh
        
        with mp_face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        ) as face_mesh:
            
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            results = face_mesh.process(rgb_image)
            
            if not results.multi_face_landmarks:
                return {"available": True, "face_detected": False}
            
            landmarks = results.multi_face_landmarks[0].landmark
            h, w = image.shape[:2]
            
            # Get face bounding box from landmarks
            x_coords = [lm.x * w for lm in landmarks]
            y_coords = [lm.y * h for lm in landmarks]
            
            bbox = {
                "x": int(min(x_coords)),
                "y": int(min(y_coords)),
                "width": int(max(x_coords) - min(x_coords)),
                "height": int(max(y_coords) - min(y_coords)),
            }
            
            # Get nose tip for face centering
            nose_tip = landmarks[1]
            
            return {
                "available": True,
                "face_detected": True,
                "bbox": bbox,
                "nose_tip": {"x": nose_tip.x, "y": nose_tip.y},
                "num_landmarks": len(landmarks),
            }
    except Exception as e:
        print(f"MediaPipe face detection error: {e}")
        return {"available": True, "error": str(e), "face_detected": False}


def check_image_quality(image_path: str) -> dict:
    """
    Check image quality for potential fake ID detection.
    Returns dict with quality metrics.
    """
    try:
        image = cv2.imread(image_path)
        if image is None:
            return {"valid": False, "reason": "Cannot read image"}
        
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        brightness = np.mean(gray)
        contrast = gray.std()
        
        is_blurred = laplacian_var < 100
        is_too_dark = brightness < 50
        is_too_bright = brightness > 200
        is_low_contrast = contrast < 30
        
        reasons = []
        if is_blurred:
            reasons.append("Image is blurred")
        if is_too_dark:
            reasons.append("Image is too dark")
        if is_too_bright:
            reasons.append("Image is too bright/overexposed")
        if is_low_contrast:
            reasons.append("Image has low contrast")
        
        return {
            "valid": len(reasons) == 0,
            "reasons": reasons,
            "metrics": {
                "blur_score": float(laplacian_var),
                "brightness": float(brightness),
                "contrast": float(contrast),
            }
        }
    except Exception as e:
        return {"valid": False, "reason": f"Quality check error: {str(e)}"}


def verify_identity(id_image_path: str, selfie_image_path: str) -> dict:
    """
    Main function to verify identity by comparing ID photo with selfie.
    Uses InsightFace for face recognition.
    Returns verification result with match score and quality checks.
    """
    # Check if InsightFace is available
    if not INSIGHTFACE_AVAILABLE:
        return {
            "success": False,
            "error": "Face recognition libraries not available (InsightFace)",
            "face_match_score": 0.0,
            "verification_status": "manual_review",
            "fake_id_flag": False,
        }
    
    # Check image quality
    id_quality = check_image_quality(id_image_path)
    selfie_quality = check_image_quality(selfie_image_path)
    
    fake_id_flag = False
    quality_issues = []
    
    if not id_quality["valid"]:
        quality_issues.extend([f"ID image: {r}" for r in id_quality.get("reasons", [])])
    
    if not selfie_quality["valid"]:
        quality_issues.extend([f"Selfie image: {r}" for r in selfie_quality.get("reasons", [])])
    
    # Detect faces using InsightFace
    id_faces = detect_faces_insightface(id_image_path)
    selfie_faces = detect_faces_insightface(selfie_image_path)
    
    if not id_faces or len(id_faces) == 0:
        quality_issues.append("No face detected in ID image")
        # Try OpenCV as fallback
        opencv_faces = detect_faces_opencv(id_image_path)
        if not opencv_faces:
            fake_id_flag = True
    
    if not selfie_faces or len(selfie_faces) == 0:
        quality_issues.append("No face detected in selfie image")
    
    # Compare faces
    face_match_score = 0.0
    is_match = False
    
    if id_faces and selfie_faces:
        face_match_score, is_match = compare_faces_insightface(id_image_path, selfie_image_path)
    
    # Determine verification status
    if fake_id_flag:
        verification_status = "failed"
    elif is_match and face_match_score >= 0.5:
        verification_status = "verified"
    elif face_match_score >= 0.35:
        verification_status = "manual_review"
    else:
        verification_status = "failed"
    
    return {
        "success": True,
        "face_match_score": face_match_score,
        "verification_status": verification_status,
        "fake_id_flag": fake_id_flag,
        "quality_issues": quality_issues,
        "id_face_detected": id_faces is not None and len(id_faces) > 0,
        "selfie_face_detected": selfie_faces is not None and len(selfie_faces) > 0,
    }


# Export availability flags
FACE_VERIFICATION_AVAILABLE = INSIGHTFACE_AVAILABLE
LIVENESS_DETECTION_AVAILABLE = MEDIAPIPE_AVAILABLE
