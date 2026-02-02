# Receipt printer photobooth

Raspberry Pi photobooth: camera preview, touchscreen/button trigger, countdown, optional face-based brightness, receipt printing with QR code.

## Configuration

- **Store info and other defaults** live in `config_example.py` (tracked). Copy it to `local_config.py` and edit; `local_config.py` is not tracked by git.
- **App/hardware defaults** (camera, GPIO, etc.) are in `main.py` (class `Config`).
- Only set variables you want to change in `local_config.py`; anything not set there uses the default.

```bash
cp config_example.py local_config.py
# Edit local_config.py with your store name, QR URL, etc.
```

## Requirements

- Raspberry Pi with camera and (optional) touchscreen
- Python 3, picamera2, PIL, evdev, RPi.GPIO, python-escpos
- For face detection: `pip install opencv-python-headless` (use headless to avoid Qt conflicts)

## Run

```bash
python3 main.py
```

## Other files

- `image_to_stdout.py` – standalone script to print image files to stdout as ESC-POS (e.g. `python3 image_to_stdout.py image.png > /dev/usb/lp0`).
- `print_sample_images.py` – debug tool: print random sample images from a directory using the same processing as main (face detection, brightness, 1-bit). Runs headless. Options: `--dir images`, `--prefix ""`, `--num 3`, `--seed N`.

## License

See repository for license.
