# Copy this file to local_config.py and edit with your settings.
# local_config.py is not tracked by git (see .gitignore).
#
# Only define variables you want to override; other defaults are in main.py Config.
# Store info below is loaded as the default; override any in local_config.py.

# ---------------------------------------------------------------------------
# Store / receipt branding (printed on every receipt)
# ---------------------------------------------------------------------------
STORE_NAME = "My Store"
STORE_SUBTITLE = "Tagline or market name"
STORE_LOCATION = "City, State"
STORE_SOCIAL = "@mystore"
STORE_QR_URL = "https://example.com"
FOOTER_MESSAGE = "Thank you for shopping with us!"

# ---------------------------------------------------------------------------
# Camera
# ---------------------------------------------------------------------------
# PHOTO_WIDTH = 480
# PHOTO_LENGTH = 800
# FLIP_UP_DOWN = False
# FLIP_LEFT_RIGHT = True

# ---------------------------------------------------------------------------
# Display (touchscreen)
# ---------------------------------------------------------------------------
# DISPLAY_WIDTH = 480
# DISPLAY_HEIGHT = 800
# FULLSCREEN = True
# HIDE_MOUSE_CURSOR = True
# LONG_PRESS_DURATION = 2.0   # Seconds to hold to exit fullscreen
# CAPTURE_DELAY = 3.0         # Seconds before photo is taken

# ---------------------------------------------------------------------------
# Hardware
# ---------------------------------------------------------------------------
# GPIO_BUTTON_PIN = 18

# ---------------------------------------------------------------------------
# Image processing / brightness
# ---------------------------------------------------------------------------
# BRIGHTNESS_ENHANCEMENT = 1.8      # Used only when AUTO_BRIGHTNESS is False
# AUTO_BRIGHTNESS = True
# TARGET_BRIGHTNESS = 200          # 0-255
# BRIGHTNESS_MIN = 0.5
# BRIGHTNESS_MAX = 3.0
# BRIGHTNESS_CENTER_WEIGHT = 0.7
# BRIGHTNESS_PERCENTILE = 75

# ---------------------------------------------------------------------------
# Face detection
# ---------------------------------------------------------------------------
# USE_FACE_DETECTION = True
# FACE_DETECTION_SCALE_FACTOR = 1.1
# FACE_DETECTION_MIN_NEIGHBORS = 5
# FACE_DEBUG_DISPLAY = False       # Set True to show face boxes on screen
# FACE_DEBUG_DISPLAY_SECONDS = 5
