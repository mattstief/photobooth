#!/usr/bin/env python3
"""
Receipt Printer Application
Captures photos from camera and prints receipts with QR codes.
Supports both touchscreen and GPIO button triggers.
"""

import RPi.GPIO as GPIO
import time
import glob
from threading import Thread
from PIL import Image, ImageEnhance, ImageDraw, ImageFont, ImageStat
from evdev import InputDevice, ecodes

# Try to import OpenCV for face detection (optional).
# Use opencv-python-headless to avoid Qt conflicts with picamera2/PyQt.
try:
    import cv2
    import numpy as np
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False
    print("Warning: OpenCV not available. Face detection disabled. Install with: pip install opencv-python-headless")

from capture_png import capture_png, start_camera, exit_fullscreen, get_preview_window, show_countdown
from printer_interface import configure_printer
from line_maker import (
    top_dotted_line,
    bottom_dotted_line,
    top_dotted_line_2,
    bottom_dotted_line_2
)


# ============================================================================
# Configuration
# ============================================================================
# Defaults are defined here. Override by copying config_example.py to
# local_config.py and setting values there (local_config.py is not tracked by git).

class Config:
    """Application configuration constants (defaults). Override via local_config.py."""
    # Camera settings
    PHOTO_WIDTH = 480
    PHOTO_LENGTH = 800
    FLIP_UP_DOWN = False
    FLIP_LEFT_RIGHT = True

    # Display settings
    DISPLAY_WIDTH = 480
    DISPLAY_HEIGHT = 800
    FULLSCREEN = True
    HIDE_MOUSE_CURSOR = True
    LONG_PRESS_DURATION = 2.0  # Seconds to hold touchscreen to exit fullscreen
    CAPTURE_DELAY = 3.0  # Seconds to wait after trigger before capturing photo

    # GPIO settings
    GPIO_BUTTON_PIN = 18

    # Image processing
    BRIGHTNESS_ENHANCEMENT = 1.5  # Used only if AUTO_BRIGHTNESS is False
    AUTO_BRIGHTNESS = False
    TARGET_BRIGHTNESS = 210  # Target brightness (0-255)
    BRIGHTNESS_MIN = 0.5
    BRIGHTNESS_MAX = 3
    BRIGHTNESS_CENTER_WEIGHT = 0.00001
    BRIGHTNESS_PERCENTILE = 30
    USE_FACE_DETECTION = False
    FACE_DETECTION_SCALE_FACTOR = 1.05
    FACE_DETECTION_MIN_NEIGHBORS = 2
    FACE_DEBUG_DISPLAY = False  # Set True to show face detection boxes (debug)
    FACE_DEBUG_DISPLAY_SECONDS = 4

    # Store information: loaded from config_example.py, then overridden by local_config.py
    STORE_NAME = None
    STORE_SUBTITLE = None
    STORE_LOCATION = None
    STORE_SOCIAL = None
    STORE_QR_URL = None
    FOOTER_MESSAGE = None


# Default store strings used only when config files don't define them
_STORE_DEFAULTS = {
    "STORE_NAME": "My Store",
    "STORE_SUBTITLE": "Tagline or market name",
    "STORE_LOCATION": "City, State",
    "STORE_SOCIAL": "@mystore",
    "STORE_QR_URL": "https://example.com",
    "FOOTER_MESSAGE": "Thank you for shopping with us!",
}


def _load_local_config():
    """Load config: config_example.py (store defaults), then local_config.py overrides."""
    # 1) Apply store (and any other) defaults from config_example.py
    try:
        import config_example as example_cfg
        for name in dir(example_cfg):
            if name.isupper() and not name.startswith("_"):
                if hasattr(Config, name):
                    setattr(Config, name, getattr(example_cfg, name))
    except ImportError:
        pass
    # 2) Override with local_config.py if it exists (not tracked by git)
    try:
        import local_config
        for name in dir(local_config):
            if name.isupper() and not name.startswith("_"):
                if hasattr(Config, name):
                    setattr(Config, name, getattr(local_config, name))
    except ImportError:
        pass
    # 3) Ensure store keys always have a value
    for key, default in _STORE_DEFAULTS.items():
        if getattr(Config, key, None) is None:
            setattr(Config, key, default)


_load_local_config()


# ============================================================================
# Touchscreen Handler
# ============================================================================

class TouchscreenHandler:
    """Handles touchscreen input detection"""
    
    def __init__(self, long_press_duration=3.0):
        self.touch_detected = False
        self._touch_down = False
        self._touch_start_time = None
        self._long_press_duration = long_press_duration
        self._device_path = None
        self._monitor_thread = None
        self._long_press_check_thread = None
        self._stop_long_press_check = False
        self._long_press_detected = False  # Flag to track if long press was detected
    
    def find_device(self):
        """Find and return the touchscreen input device path"""
        devices = [InputDevice(path) for path in glob.glob('/dev/input/event*')]
        
        for device in devices:
            capabilities = device.capabilities()
            
            # Check for single-touch capability
            if (ecodes.EV_KEY in capabilities and 
                ecodes.BTN_TOUCH in capabilities[ecodes.EV_KEY]):
                print(f"Found touchscreen: {device.name} at {device.path}")
                return device.path
            
            # Check for multi-touch capability
            elif ecodes.EV_ABS in capabilities:
                abs_caps = capabilities[ecodes.EV_ABS]
                if (ecodes.ABS_MT_POSITION_X in abs_caps or 
                    ecodes.ABS_X in abs_caps):
                    print(f"Found touchscreen: {device.name} at {device.path}")
                    return device.path
        
        raise Exception("No touchscreen device found. Make sure your touchscreen is connected.")
    
    def _long_press_check_loop(self):
        """Check for long press in a background thread"""
        while not self._stop_long_press_check:
            if self._touch_down and self._touch_start_time:
                duration = time.time() - self._touch_start_time
                if duration >= self._long_press_duration:
                    print(f"Long press detected ({duration:.1f}s) - exiting fullscreen")
                    self._long_press_detected = True  # Mark that long press was detected
                    exit_fullscreen()
                    # Reset touch state
                    self._touch_down = False
                    self._touch_start_time = None
            time.sleep(0.1)  # Check every 100ms
    
    def _monitor_loop(self, device_path):
        """Monitor touchscreen events in a background thread"""
        device = InputDevice(device_path)
        print(f"Monitoring touchscreen: {device.name}")
        
        for event in device.read_loop():
            if event.type == ecodes.EV_KEY:
                # Single-touch event
                if event.code == ecodes.BTN_TOUCH:
                    if event.value == 1 and not self._touch_down:
                        # Touch down
                        self._touch_down = True
                        self._touch_start_time = time.time()
                        self._long_press_detected = False  # Reset flag on new touch
                        print("Touch detected!")
                    elif event.value == 0:
                        # Touch up
                        if self._touch_down and self._touch_start_time:
                            duration = time.time() - self._touch_start_time
                            # Only trigger print if it was a short press (not long press)
                            # Also check that long press wasn't detected during this touch
                            if duration < self._long_press_duration and not self._long_press_detected:
                                self.touch_detected = True
                        # Reset touch state
                        self._touch_down = False
                        self._touch_start_time = None
                        self._long_press_detected = False  # Reset long press flag
            
            elif event.type == ecodes.EV_ABS:
                # Multi-touch event
                if event.code == ecodes.ABS_MT_TRACKING_ID:
                    if event.value >= 0 and not self._touch_down:
                        # Touch down
                        self._touch_down = True
                        self._touch_start_time = time.time()
                        self._long_press_detected = False  # Reset flag on new touch
                        print("Touch detected!")
                    elif event.value == -1:
                        # Touch up
                        if self._touch_down and self._touch_start_time:
                            duration = time.time() - self._touch_start_time
                            # Only trigger print if it was a short press (not long press)
                            # Also check that long press wasn't detected during this touch
                            if duration < self._long_press_duration and not self._long_press_detected:
                                self.touch_detected = True
                        # Reset touch state
                        self._touch_down = False
                        self._touch_start_time = None
                        self._long_press_detected = False  # Reset long press flag
            
    
    def start(self):
        """Initialize and start touchscreen monitoring"""
        try:
            self._device_path = self.find_device()
            self._monitor_thread = Thread(
                target=self._monitor_loop,
                args=(self._device_path,),
                daemon=True
            )
            self._monitor_thread.start()
            
            # Start long press check thread
            self._stop_long_press_check = False
            self._long_press_check_thread = Thread(
                target=self._long_press_check_loop,
                daemon=True
            )
            self._long_press_check_thread.start()
            
            return True
        except Exception as e:
            print(f"Warning: Could not initialize touchscreen: {e}")
            print("Falling back to GPIO button only")
            return False
    
    def reset(self):
        """Reset the touch detected flag"""
        self.touch_detected = False


# ============================================================================
# GPIO Button Handler
# ============================================================================

class GPIOButtonHandler:
    """Handles GPIO button input"""
    
    def __init__(self, pin):
        self.pin = pin
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    
    def is_pressed(self):
        """Check if button is pressed (returns True when pressed)"""
        return GPIO.input(self.pin) == False


# ============================================================================
# Keyboard Handler
# ============================================================================

class KeyboardHandler:
    """Handles keyboard input for triggering photo capture"""
    
    def __init__(self):
        self._monitor_thread = None
        self._device_path = None
        self.space_pressed = False
    
    def find_keyboard_device(self):
        """Find a keyboard input device"""
        devices = []
        for path in glob.glob('/dev/input/event*'):
            try:
                devices.append(InputDevice(path))
            except (OSError, IOError, PermissionError):
                continue
        
        # Try to find a keyboard device
        for device in devices:
            try:
                capabilities = device.capabilities()
                # Check if device has keyboard keys
                if ecodes.EV_KEY in capabilities:
                    keys = capabilities[ecodes.EV_KEY]
                    # Check for Space key (KEY_SPACE = 57)
                    if ecodes.KEY_SPACE in keys:
                        print(f"Found keyboard: {device.name} at {device.path}")
                        return device.path
                    # Also check for other common keyboard keys as fallback
                    keyboard_keys = [ecodes.KEY_SPACE, ecodes.KEY_ENTER, ecodes.KEY_A]
                    if any(key in keys for key in keyboard_keys):
                        print(f"Found keyboard: {device.name} at {device.path}")
                        return device.path
            except (OSError, IOError, PermissionError):
                continue
            except Exception:
                continue
        
        return None
    
    def _monitor_loop(self, device_path):
        """Monitor keyboard events in a background thread"""
        device = None
        try:
            device = InputDevice(device_path)
            print(f"Monitoring keyboard: {device.name} (press SPACEBAR to take photo)")
            
            for event in device.read_loop():
                if event.type == ecodes.EV_KEY:
                    # Spacebar pressed (KEY_SPACE = 57)
                    # event.value: 0=release, 1=press, 2=repeat
                    if event.code == ecodes.KEY_SPACE and event.value == 1:  # Key press (not release)
                        print("Spacebar pressed - triggering photo capture")
                        self.space_pressed = True
        except PermissionError as e:
            print(f"Permission error in keyboard monitoring: {e}")
            print("  Try running with sudo or add user to input group")
        except Exception as e:
            print(f"Error in keyboard monitoring loop: {e}")
        finally:
            if device:
                try:
                    device.ungrab()
                except:
                    pass
    
    def start(self):
        """Initialize and start keyboard monitoring"""
        try:
            self._device_path = self.find_keyboard_device()
            if self._device_path:
                self._monitor_thread = Thread(
                    target=self._monitor_loop,
                    args=(self._device_path,),
                    daemon=True
                )
                self._monitor_thread.start()
                return True
            else:
                print("No keyboard device found - spacebar trigger unavailable")
                return False
        except Exception as e:
            print(f"Warning: Could not initialize keyboard monitoring: {e}")
            return False
    
    def reset(self):
        """Reset the space pressed flag"""
        self.space_pressed = False


# ============================================================================
# Image Processor
# ============================================================================

class ImageProcessor:
    """Handles image processing and manipulation"""
    
    def __init__(self, flip_up_down=True, flip_left_right=True, brightness=1.8, 
                 auto_brightness=True, target_brightness=128, 
                 brightness_min=0.5, brightness_max=3.0,
                 center_weight=0.7, percentile=75,
                 use_face_detection=True, face_scale_factor=1.1, face_min_neighbors=5,
                 face_debug_display=False, face_debug_seconds=5):
        self.flip_up_down = flip_up_down
        self.flip_left_right = flip_left_right
        self.brightness = brightness
        self.auto_brightness = auto_brightness
        self.target_brightness = target_brightness
        self.brightness_min = brightness_min
        self.brightness_max = brightness_max
        self.center_weight = center_weight
        self.percentile = percentile
        self.use_face_detection = use_face_detection and OPENCV_AVAILABLE
        self.face_scale_factor = face_scale_factor
        self.face_min_neighbors = face_min_neighbors
        self._face_cascade = None
        
        # Load face detection cascade if available
        if self.use_face_detection:
            try:
                # Try to load the Haar cascade (comes with OpenCV)
                cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
                self._face_cascade = cv2.CascadeClassifier(cascade_path)
                if self._face_cascade.empty():
                    print("Warning: Could not load face detection cascade. Falling back to center region method.")
                    self.use_face_detection = False
                else:
                    print("Face detection enabled")
            except Exception as e:
                print(f"Warning: Could not initialize face detection: {e}. Falling back to center region method.")
                self.use_face_detection = False
        self.face_debug_display = face_debug_display
        self.face_debug_seconds = face_debug_seconds
    
    def detect_faces(self, img):
        """
        Detect faces in the image using OpenCV.
        Returns list of face regions as (x, y, width, height) tuples.
        """
        if not self.use_face_detection or self._face_cascade is None:
            if self.face_debug_display:
                print("[Face debug] detect_faces: use_face_detection=%s, cascade=%s" % (
                    self.use_face_detection, self._face_cascade is not None))
            return []
        
        try:
            # Convert PIL image to OpenCV format
            if img.mode != 'L':
                gray_pil = img.convert('L')
            else:
                gray_pil = img
            
            # Convert PIL to numpy array
            gray_cv = np.array(gray_pil)
            
            # Detect faces
            faces = self._face_cascade.detectMultiScale(
                gray_cv,
                scaleFactor=self.face_scale_factor,
                minNeighbors=self.face_min_neighbors,
                minSize=(30, 30)  # Minimum face size
            )
            result = [(int(x), int(y), int(w), int(h)) for (x, y, w, h) in faces]
            if self.face_debug_display and len(result) > 0:
                print("[Face debug] detect_faces: found %d face(s)" % len(result))
            return result
        except Exception as e:
            print(f"[Face debug] Error during face detection: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def show_face_debug_display(self, img):
        """
        Draw rectangles around detected faces and show the image on screen briefly.
        Used to verify that face detection is working correctly.
        """
        print("[Face debug] show_face_debug_display called (face_debug_display=True)")
        print(f"[Face debug] use_face_detection={self.use_face_detection}, image size={img.size}, mode={img.mode}")
        if not self.use_face_detection:
            print("[Face debug] Skipping: use_face_detection is False (OpenCV missing or cascade failed)")
            return
        faces = self.detect_faces(img)
        print(f"[Face debug] detect_faces returned {len(faces)} face(s)")
        if len(faces) == 0:
            print("[Face debug] No faces detected - nothing to display")
            return
        for i, (x, y, w, h) in enumerate(faces):
            print(f"[Face debug] Face {i + 1}: x={x}, y={y}, w={w}, h={h}")
        # Draw on a copy so we don't modify the original
        img_display = img.copy()
        if img_display.mode != 'RGB':
            img_display = img_display.convert('RGB')
        draw = ImageDraw.Draw(img_display)
        # Use a thick green rectangle so it's visible
        rect_color = (0, 255, 0)  # Green
        thickness = max(4, min(img_display.size) // 120)
        print(f"[Face debug] Drawing {len(faces)} rectangle(s), thickness={thickness}")
        for (x, y, w, h) in faces:
            for t in range(thickness):
                draw.rectangle(
                    [x - t, y - t, x + w + t, y + h + t],
                    outline=rect_color
                )
        # Draw count label
        font = None
        for path in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                     "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"):
            try:
                font = ImageFont.truetype(path, 24)
                break
            except Exception:
                continue
        if font is None:
            font = ImageFont.load_default()
        for i, (x, y, w, h) in enumerate(faces):
            draw.text((x, y - 28), f"Face {i + 1}", fill=rect_color, font=font)
        print("[Face debug] Rectangles drawn, opening Qt display window...")
        # Display with Qt
        try:
            try:
                from PyQt5.QtWidgets import QApplication, QLabel
                from PyQt5.QtCore import Qt
                from PyQt5.QtGui import QImage, QPixmap
                print("[Face debug] Using PyQt5")
            except ImportError:
                from PySide2.QtWidgets import QApplication, QLabel
                from PySide2.QtCore import Qt
                from PySide2.QtGui import QImage, QPixmap
                print("[Face debug] Using PySide2")
            app = QApplication.instance()
            if not app:
                print("[Face debug] No Qt application instance - cannot show window (QApplication.instance() is None)")
                return
            print(f"[Face debug] Qt app found: {app}")
            width, height = img_display.size
            bytes_per_line = width * 3
            data = img_display.tobytes()
            print(f"[Face debug] Image data: {width}x{height}, bytes_per_line={bytes_per_line}, data length={len(data)}")
            qimg = QImage(data, width, height, bytes_per_line, QImage.Format_RGB888)
            if qimg.isNull():
                print("[Face debug] QImage is null - conversion failed")
                return
            print("[Face debug] QImage created successfully")
            pixmap = QPixmap.fromImage(qimg)
            if pixmap.isNull():
                print("[Face debug] QPixmap is null - conversion failed")
                return
            print(f"[Face debug] QPixmap size: {pixmap.width()}x{pixmap.height()}")
            label = QLabel()
            label.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
            label.setPixmap(pixmap)
            label.setScaledContents(True)
            label.resize(width, height)
            label.setWindowTitle("Face detection debug")
            print("[Face debug] Calling label.show()...")
            label.show()
            label.raise_()
            label.activateWindow()
            app.processEvents()
            print(f"[Face debug] Window shown, waiting {self.face_debug_seconds}s (label.visible={label.isVisible()})")
            start = time.time()
            while time.time() - start < self.face_debug_seconds:
                app.processEvents()
                time.sleep(0.05)
            print("[Face debug] Closing display window")
            label.close()
            label.deleteLater()
            app.processEvents()
        except Exception as e:
            import traceback
            print(f"[Face debug] Display error: {e}")
            traceback.print_exc()
    
    def calculate_brightness_from_region(self, gray_img, region):
        """
        Calculate brightness from a specific region of the image.
        Returns the percentile-based brightness value.
        """
        x, y, w, h = region
        # Ensure coordinates are within image bounds
        width, height = gray_img.size
        x = max(0, min(x, width - 1))
        y = max(0, min(y, height - 1))
        w = min(w, width - x)
        h = min(h, height - y)
        
        if w <= 0 or h <= 0:
            return None
        
        # Extract region
        region_img = gray_img.crop((x, y, x + w, y + h))
        pixels = list(region_img.getdata())
        
        if len(pixels) == 0:
            return None
        
        # Filter outliers (5th to 95th percentile)
        sorted_pixels = sorted(pixels)
        p5_idx = int(len(sorted_pixels) * 0.05)
        p95_idx = int(len(sorted_pixels) * 0.95)
        p5 = sorted_pixels[p5_idx] if p5_idx < len(sorted_pixels) else sorted_pixels[0]
        p95 = sorted_pixels[p95_idx] if p95_idx < len(sorted_pixels) else sorted_pixels[-1]
        filtered_pixels = [p for p in pixels if p5 <= p <= p95]
        
        if len(filtered_pixels) == 0:
            filtered_pixels = pixels
        
        # Calculate percentile
        sorted_filtered = sorted(filtered_pixels)
        percentile_index = int(len(sorted_filtered) * (self.percentile / 100.0))
        percentile_index = min(percentile_index, len(sorted_filtered) - 1)
        return sorted_filtered[percentile_index]
    
    def calculate_auto_brightness(self, img):
        """
        Calculate optimal brightness enhancement factor based on image analysis.
        
        First tries to detect faces and optimize for face regions.
        Falls back to center region method if no faces detected.
        Uses percentile-based analysis to ignore background extremes.
        """
        # Convert to grayscale for analysis if needed
        if img.mode != 'L':
            gray = img.convert('L')
        else:
            gray = img
        
        width, height = gray.size
        subject_brightness = None
        method_used = "unknown"
        
        # Try face detection first
        if self.use_face_detection:
            faces = self.detect_faces(img)
            if len(faces) > 0:
                print(f"Detected {len(faces)} face(s)")
                # Calculate brightness from all detected faces
                face_brightnesses = []
                for face_region in faces:
                    brightness = self.calculate_brightness_from_region(gray, face_region)
                    if brightness is not None:
                        face_brightnesses.append(brightness)
                
                if len(face_brightnesses) > 0:
                    # Use average of all face brightnesses
                    subject_brightness = sum(face_brightnesses) / len(face_brightnesses)
                    method_used = f"face_detection ({len(faces)} faces)"
        
        # Fallback to center region method if no faces detected
        if subject_brightness is None:
            method_used = "center_region"
            # Extract center region (where subjects are typically positioned)
            center_margin_x = int(width * (1 - self.center_weight) / 2)
            center_margin_y = int(height * (1 - self.center_weight) / 2)
            center_box = (
                center_margin_x,
                center_margin_y,
                width - center_margin_x,
                height - center_margin_y
            )
            center_region = gray.crop(center_box)
            
            # Get pixel values from center region
            center_pixels = list(center_region.getdata())
            
            # Filter out very dark pixels (likely background) and very bright pixels (overexposed)
            if len(center_pixels) > 0:
                sorted_pixels = sorted(center_pixels)
                p5 = sorted_pixels[int(len(sorted_pixels) * 0.05)]
                p95 = sorted_pixels[int(len(sorted_pixels) * 0.95)]
                filtered_pixels = [p for p in center_pixels if p5 <= p <= p95]
            else:
                filtered_pixels = center_pixels
            
            if len(filtered_pixels) == 0:
                filtered_pixels = center_pixels
            
            # Calculate percentile-based brightness
            sorted_filtered = sorted(filtered_pixels)
            percentile_index = int(len(sorted_filtered) * (self.percentile / 100.0))
            percentile_index = min(percentile_index, len(sorted_filtered) - 1)
            subject_brightness = sorted_filtered[percentile_index]
        
        # Also get full image mean for comparison
        stat = ImageStat.Stat(gray)
        full_mean = stat.mean[0]
        
        # Calculate brightness factor to reach target
        if subject_brightness > 0:
            brightness_factor = self.target_brightness / subject_brightness
        else:
            brightness_factor = 2.0  # Default if subject is completely black
        
        # Clamp to reasonable bounds
        brightness_factor = max(self.brightness_min, min(self.brightness_max, brightness_factor))
        
        print(f"Auto brightness ({method_used}): subject={subject_brightness:.1f} (p{self.percentile}), "
              f"full_mean={full_mean:.1f}, target={self.target_brightness}, factor={brightness_factor:.2f}")
        return brightness_factor
    
    def process_image(self, image_path):
        """Process image: flip, enhance brightness, convert to 1-bit"""
        img = Image.open(image_path)
        
        # Apply flips
        if self.flip_up_down:
            img = img.transpose(Image.FLIP_TOP_BOTTOM)
        if self.flip_left_right:
            img = img.transpose(Image.FLIP_LEFT_RIGHT)
        
        # Optional: show face detection markers for verification (set FACE_DEBUG_DISPLAY in config)
        if self.face_debug_display:
            self.show_face_debug_display(img)
        
        # Calculate brightness enhancement
        if self.auto_brightness:
            brightness_factor = self.calculate_auto_brightness(img)
        else:
            brightness_factor = self.brightness
        
        # ImageEnhance.Brightness only supports 'L' and 'RGB'; convert if needed (e.g. 1-bit, P, RGBA)
        if img.mode not in ("L", "RGB"):
            img = img.convert("L")
        # Enhance brightness
        brightener = ImageEnhance.Brightness(img)
        img = brightener.enhance(brightness_factor)
        
        # Convert to 1-bit (black and white)
        img = img.convert("L")
        img = img.convert("1", dither=Image.FLOYDSTEINBERG)
        
        img.save(image_path)
        return image_path


# ============================================================================
# Receipt Printer
# ============================================================================

class ReceiptPrinter:
    """Handles receipt printing operations"""
    
    def __init__(self):
        self.printer = configure_printer()
    
    def print_header(self):
        """Print store header with decorative lines"""
        self.printer.set(align='center')
        self.printer.image(top_dotted_line())
        self.printer.image(top_dotted_line_2())
        
        self.printer.set(align='center', bold=True, width=2, height=2)
        self.printer.text(f"{Config.STORE_NAME}\n")
        
        self.printer.set(align='center', bold=False, width=1, height=1)
        self.printer.text(f"{Config.STORE_SUBTITLE}\n")
        self.printer.text(f"{Config.STORE_LOCATION}\n")
        self.printer.text(f"{Config.STORE_SOCIAL}\n")
        
        self.printer.image(bottom_dotted_line_2())
        self.printer.image(bottom_dotted_line())
    
    def print_image(self, image_path):
        """Print processed image"""
        self.printer.image(image_path)
    
    def print_qr_code(self):
        """Print QR code"""
        self.printer.qr(Config.STORE_QR_URL, size=6, center=True)
    
    def print_footer(self):
        """Print footer message"""
        self.printer.text(f"{Config.FOOTER_MESSAGE}\n")
    
    def cut(self):
        """Cut the receipt"""
        self.printer.cut()
    
    def print_receipt(self, image_path):
        """Print complete receipt"""
        self.print_header()
        self.print_image(image_path)
        self.print_qr_code()
        self.print_footer()
        self.cut()

# ============================================================================
# Main Application
# ============================================================================

class ReceiptPrinterApp:
    """Main application class"""
    
    def __init__(self):
        self.camera = None
        self.touchscreen = TouchscreenHandler(long_press_duration=Config.LONG_PRESS_DURATION)
        self.keyboard = KeyboardHandler()
        self.gpio_button = GPIOButtonHandler(Config.GPIO_BUTTON_PIN)
        self.image_processor = ImageProcessor(
            flip_up_down=Config.FLIP_UP_DOWN,
            flip_left_right=Config.FLIP_LEFT_RIGHT,
            brightness=Config.BRIGHTNESS_ENHANCEMENT,
            auto_brightness=Config.AUTO_BRIGHTNESS,
            target_brightness=Config.TARGET_BRIGHTNESS,
            brightness_min=Config.BRIGHTNESS_MIN,
            brightness_max=Config.BRIGHTNESS_MAX,
            center_weight=Config.BRIGHTNESS_CENTER_WEIGHT,
            percentile=Config.BRIGHTNESS_PERCENTILE,
            use_face_detection=Config.USE_FACE_DETECTION,
            face_scale_factor=Config.FACE_DETECTION_SCALE_FACTOR,
            face_min_neighbors=Config.FACE_DETECTION_MIN_NEIGHBORS,
            face_debug_display=Config.FACE_DEBUG_DISPLAY,
            face_debug_seconds=Config.FACE_DEBUG_DISPLAY_SECONDS
        )
        self.receipt_printer = ReceiptPrinter()
    
    def initialize(self):
        """Initialize camera and input handlers"""
        # Start camera with display settings
        self.camera = start_camera(
            Config.PHOTO_WIDTH,
            Config.PHOTO_LENGTH,
            display_width=Config.DISPLAY_WIDTH,
            display_height=Config.DISPLAY_HEIGHT,
            fullscreen=Config.FULLSCREEN,
            hide_mouse=Config.HIDE_MOUSE_CURSOR
        )
        time.sleep(0.5)
        
        # Start touchscreen monitoring
        self.touchscreen.start()
        
        # Start keyboard monitoring for spacebar
        self.keyboard.start()
        
        print("Receipt printer ready!")
        print("Press button, tap screen, or press SPACEBAR to print receipt")
        if Config.FULLSCREEN:
            print("Long-press touchscreen (3+ seconds) to exit fullscreen")
    
    def capture_and_process_image(self):
        """Capture image from camera and process it"""
        print('Button pressed')
        # Show countdown overlay
        show_countdown(
            duration=int(Config.CAPTURE_DELAY),
            display_width=Config.DISPLAY_WIDTH,
            display_height=Config.DISPLAY_HEIGHT
        )
        filename = capture_png(self.camera)
        print('Photo captured')
        
        self.camera.stop()
        time.sleep(0.2)
        
        # Process image
        processed_path = self.image_processor.process_image(filename)
        return processed_path
    
    def run(self):
        """Main application loop"""
        self.initialize()
        
        try:
            while True:
                # Check for trigger (GPIO button, touchscreen, or spacebar)
                if (self.gpio_button.is_pressed() or 
                    self.touchscreen.touch_detected or
                    self.keyboard.space_pressed):
                    
                    # Capture and process image
                    image_path = self.capture_and_process_image()
                    
                    # Print receipt
                    self.receipt_printer.print_receipt(image_path)
                    
                    # Reset flags and restart camera
                    self.touchscreen.reset()
                    self.keyboard.reset()
                    time.sleep(1)
                    self.camera.start()
        
        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Clean up resources"""
        if self.camera:
            self.camera.stop()
        GPIO.cleanup()
        print("Cleanup complete")


# ============================================================================
# Entry Point
# ============================================================================

def main():
    """Main entry point"""
    app = ReceiptPrinterApp()
    app.run()


if __name__ == "__main__":
    main()
