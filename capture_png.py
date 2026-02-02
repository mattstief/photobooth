#!/usr/bin/python3

# Capture a PNG while still running in the preview mode.

import time
from datetime import datetime

from picamera2 import Picamera2, Preview
from libcamera import Transform

# Global reference to the preview window for fullscreen toggling
_preview_window = None
_picam2_instance = None

def show_countdown(duration=3, display_width=480, display_height=800):
	"""
	Show a countdown overlay on the screen
	
	Args:
		duration: Number of seconds to count down (default 3)
		display_width: Screen width (default 800)
		display_height: Screen height (default 480)
	"""
	try:
		# Try PyQt5 first
		try:
			from PyQt5.QtWidgets import QApplication, QLabel, QWidget, QVBoxLayout
			from PyQt5.QtCore import Qt, QTimer
			from PyQt5.QtGui import QFont
			qt_module = "PyQt5"
		except ImportError:
			# Try PySide2 if PyQt5 not available
			try:
				from PySide2.QtWidgets import QApplication, QLabel, QWidget, QVBoxLayout
				from PySide2.QtCore import Qt, QTimer
				from PySide2.QtGui import QFont
				qt_module = "PySide2"
			except ImportError:
				print("Warning: Qt not available, countdown will only print to console")
				# Fallback to console countdown
				for i in range(duration, 0, -1):
					print(f"Capturing in {i}...")
					time.sleep(1)
				return
		
		app = QApplication.instance()
		if not app:
			print("Warning: No Qt application instance, countdown will only print to console")
			for i in range(duration, 0, -1):
				print(f"Capturing in {i}...")
				time.sleep(1)
			return
		
		# Create overlay window with a widget container
		overlay = QWidget()
		overlay.setWindowFlags(
			Qt.WindowStaysOnTopHint | 
			Qt.FramelessWindowHint | 
			Qt.Tool |
			Qt.X11BypassWindowManagerHint
		)
		overlay.setAttribute(Qt.WA_TranslucentBackground)
		overlay.setAttribute(Qt.WA_ShowWithoutActivating)
		overlay.setGeometry(0, 0, display_width, display_height)
		overlay.resize(display_width, display_height)
		overlay.setMinimumSize(display_width, display_height)
		overlay.setMaximumSize(display_width, display_height)
		
		# Set background on the overlay widget itself
		overlay.setStyleSheet(f"""
			QWidget {{
				background-color: rgba(0, 0, 0, 150);
			}}
		""")
		
		# Create label for countdown text
		label = QLabel(overlay)
		label.setGeometry(0, 0, display_width, display_height)
		label.setMinimumSize(display_width, display_height)
		label.setMaximumSize(display_width, display_height)
		label.setAlignment(Qt.AlignCenter | Qt.AlignVCenter | Qt.AlignHCenter)
		
		# Style the countdown text (no background, just text)
		font = QFont()
		font.setPointSize(120)
		font.setBold(True)
		label.setFont(font)
		label.setStyleSheet("""
			QLabel {
				color: white;
				background-color: transparent;
			}
		""")
		label.setWordWrap(False)
		
		# Show countdown synchronously with proper event processing
		for i in range(duration, 0, -1):
			label.setText(str(i))
			label.setVisible(True)
			overlay.setVisible(True)
			overlay.show()
			overlay.raise_()
			overlay.activateWindow()
			label.update()
			label.repaint()
			overlay.update()
			overlay.repaint()
			app.processEvents()
			app.flush()
			
			# Wait 1 second, processing events frequently
			start = time.time()
			elapsed = 0
			while elapsed < 1.0:
				app.processEvents()
				time.sleep(0.01)
				elapsed = time.time() - start
		
		# Close overlay
		label.hide()
		overlay.hide()
		overlay.setVisible(False)
		overlay.close()
		label.deleteLater()
		overlay.deleteLater()
		app.processEvents()
		
	except Exception as e:
		print(f"Warning: Could not show countdown overlay: {e}")
		# Fallback to console countdown
		for i in range(duration, 0, -1):
			print(f"Capturing in {i}...")
			time.sleep(1)

def capture_png(picam):
	timestamp = datetime.now().strftime("%m-%d_%H%M%S")
	filename = f"images/{timestamp}.png"
	picam.capture_file(filename)
	return filename

def get_preview_window():
	"""Get the preview window reference"""
	return _preview_window

def toggle_fullscreen():
	"""Toggle fullscreen mode"""
	global _preview_window
	if _preview_window:
		try:
			if _preview_window.isFullScreen():
				_preview_window.showNormal()
				print("Exited fullscreen mode")
			else:
				_preview_window.showFullScreen()
				print("Entered fullscreen mode")
		except Exception as e:
			print(f"Error toggling fullscreen: {e}")

def exit_fullscreen():
	"""Exit fullscreen mode"""
	global _preview_window, _picam2_instance
	print("Attempting to exit fullscreen...")
	
	# Method 1: Try using the stored window reference
	if _preview_window:
		try:
			if hasattr(_preview_window, 'isFullScreen'):
				if _preview_window.isFullScreen():
					_preview_window.showNormal()
					print("Exited fullscreen mode via stored window reference")
					return True
			elif hasattr(_preview_window, 'showNormal'):
				_preview_window.showNormal()
				print("Exited fullscreen mode (forced normal)")
				return True
		except Exception as e:
			print(f"Error with stored window: {e}")
	
	# Method 2: Try accessing through picam2 preview object
	if _picam2_instance and hasattr(_picam2_instance, '_preview'):
		try:
			if hasattr(_picam2_instance._preview, 'qpicamera2'):
				if _picam2_instance._preview.qpicamera2 is not None:
					widget = _picam2_instance._preview.qpicamera2
					window = widget.window() if hasattr(widget, 'window') else widget
					if window:
						try:
							if hasattr(window, 'isFullScreen') and window.isFullScreen():
								window.showNormal()
								_preview_window = window
								print("Exited fullscreen mode via picam2 preview")
								return True
						except Exception as e:
							print(f"Error with picam2 window: {e}")
		except Exception as e:
			print(f"Error accessing picam2 preview: {e}")
	
	# Method 3: Try to find the window through Qt application
	try:
		try:
			from PyQt5.QtWidgets import QApplication
			app = QApplication.instance()
			if app:
				windows = app.topLevelWidgets()
				for window in windows:
					try:
						if hasattr(window, 'isFullScreen'):
							if window.isFullScreen():
								window.showNormal()
								_preview_window = window
								print("Exited fullscreen mode via QApplication (PyQt5)")
								return True
						# Try anyway if we can't check
						if hasattr(window, 'showNormal'):
							window.showNormal()
							_preview_window = window
							print("Exited fullscreen mode via QApplication (forced)")
							return True
					except Exception as e:
						continue
		except ImportError:
			try:
				from PySide2.QtWidgets import QApplication
				app = QApplication.instance()
				if app:
					windows = app.topLevelWidgets()
					for window in windows:
						try:
							if hasattr(window, 'isFullScreen'):
								if window.isFullScreen():
									window.showNormal()
									_preview_window = window
									print("Exited fullscreen mode via QApplication (PySide2)")
									return True
							if hasattr(window, 'showNormal'):
								window.showNormal()
								_preview_window = window
								print("Exited fullscreen mode via QApplication (forced)")
								return True
						except Exception as e:
							continue
			except ImportError:
				pass
	except Exception as e:
		print(f"Error accessing Qt application: {e}")
	
	print("Warning: Could not exit fullscreen - trying all windows...")
	return False

def hide_cursor():
	"""Hide the mouse cursor"""
	try:
		# Try PyQt5 first
		try:
			from PyQt5.QtWidgets import QApplication
			from PyQt5.QtCore import Qt
			app = QApplication.instance()
			if app:
				# Set blank cursor for all widgets
				app.setOverrideCursor(Qt.BlankCursor)
				return True
		except ImportError:
			# Try PySide2 if PyQt5 not available
			try:
				from PySide2.QtWidgets import QApplication
				from PySide2.QtCore import Qt
				app = QApplication.instance()
				if app:
					app.setOverrideCursor(Qt.BlankCursor)
					return True
			except ImportError:
				pass
	except Exception as e:
		print(f"Warning: Could not hide cursor: {e}")
	return False

def show_cursor():
	"""Show the mouse cursor"""
	try:
		try:
			from PyQt5.QtWidgets import QApplication
			app = QApplication.instance()
			if app:
				app.restoreOverrideCursor()
				return True
		except ImportError:
			try:
				from PySide2.QtWidgets import QApplication
				app = QApplication.instance()
				if app:
					app.restoreOverrideCursor()
					return True
			except ImportError:
				pass
	except Exception as e:
		print(f"Warning: Could not show cursor: {e}")
	return False


def start_camera(x=512, y=700, display_width=800, display_height=480, fullscreen=False, hide_mouse=True):
	"""
	Start camera with preview window
	
	Args:
		x: Camera capture width
		y: Camera capture height
		display_width: Display window width (default 800)
		display_height: Display window height (default 480)
		fullscreen: Whether to make window fullscreen (default False)
		hide_mouse: Whether to hide the mouse cursor (default True)
	"""
	global _preview_window, _picam2_instance
	_picam2_instance = None
	picam2 = Picamera2()
	_picam2_instance = picam2  # Store reference for later access
	
	# Start preview with display dimensions
	picam2.start_preview(
		Preview.QTGL,
		transform=Transform(hflip=1),
		width=display_width,
		height=display_height
	)

	preview_config = picam2.create_preview_configuration(main={"size": (x, y)})
	picam2.configure(preview_config)

	picam2.start()
	time.sleep(0.5)  # Give preview time to initialize
	
	# Hide cursor if requested
	if hide_mouse:
		if hide_cursor():
			print("Mouse cursor hidden")
	
	# Get window reference and set up fullscreen/exit handlers
	_preview_window = None
	if fullscreen:
		# Wait a bit more for Qt window to be fully created
		time.sleep(0.5)
		try:
			# Try accessing through preview object
			if hasattr(picam2._preview, 'qpicamera2'):
				# The qpicamera2 might not be set immediately, wait a bit
				for _ in range(10):  # Try up to 10 times
					if picam2._preview.qpicamera2 is not None:
						widget = picam2._preview.qpicamera2
						window = widget.window() if hasattr(widget, 'window') else widget
						if window:
							_preview_window = window
							window.showFullScreen()
							# Also set blank cursor on the window itself
							if hide_mouse:
								try:
									from PyQt5.QtCore import Qt
									window.setCursor(Qt.BlankCursor)
								except ImportError:
									try:
										from PySide2.QtCore import Qt
										window.setCursor(Qt.BlankCursor)
									except ImportError:
										pass
							print(f"Preview window set to fullscreen ({display_width}x{display_height})")
							print("Long-press touchscreen (3+ seconds) to exit fullscreen")
							break
					time.sleep(0.1)
				else:
					# Fallback: try accessing Qt application directly
					try:
						from PyQt5.QtWidgets import QApplication
						app = QApplication.instance()
						if app:
							windows = app.topLevelWidgets()
							if windows:
								_preview_window = windows[0]
								windows[0].showFullScreen()
								# Set blank cursor on window
								if hide_mouse:
									try:
										from PyQt5.QtCore import Qt
										windows[0].setCursor(Qt.BlankCursor)
									except ImportError:
										try:
											from PySide2.QtCore import Qt
											windows[0].setCursor(Qt.BlankCursor)
										except ImportError:
											pass
								print(f"Preview window set to fullscreen via QApplication ({display_width}x{display_height})")
								print("Long-press touchscreen (3+ seconds) to exit fullscreen")
					except (ImportError, AttributeError):
						pass
		except Exception as e:
			print(f"Warning: Could not set fullscreen: {e}")
			print("Preview will run in windowed mode")
	
	return picam2

if __name__ == "__main__":
	cam = start_camera()
	capture_png(cam)
