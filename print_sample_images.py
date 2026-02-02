#!/usr/bin/env python3
"""
Debug tool: print sample photos from an images directory using the same
processing as main.py (face detection, auto brightness, flips, 1-bit conversion).
Originals are never modified: each image is copied to a temp file, processed
and printed, then the temp file is removed.

Runs without a display: FACE_DEBUG_DISPLAY is forced off so it works over
SSH, headless, or in batch. Use --dir, --prefix, --num, and optional --seed
to control which images are printed.

Examples:
  python3 print_sample_images.py
  python3 print_sample_images.py --dir images --num 5
  python3 print_sample_images.py --prefix 11-22 --seed 42
"""

import argparse
import glob
import os
import random
import shutil
import tempfile

from main import Config, ImageProcessor, ReceiptPrinter

# Headless: avoid Qt window / display when running without a GUI
Config.FACE_DEBUG_DISPLAY = False

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp"}


def is_image(path):
    return os.path.splitext(path)[1].lower() in IMAGE_EXTENSIONS


def main():
    parser = argparse.ArgumentParser(
        description="Print random sample images using main.py processing (debug tool)."
    )
    parser.add_argument(
        "--dir",
        default="images",
        metavar="DIR",
        help="Directory containing images (default: images)",
    )
    parser.add_argument(
        "--prefix",
        default="",
        metavar="PREFIX",
        help="Only consider files whose name starts with PREFIX (default: all)",
    )
    parser.add_argument(
        "--num",
        type=int,
        default=3,
        metavar="N",
        help="Number of images to print (default: 3)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        metavar="N",
        help="Random seed for reproducible runs (default: none)",
    )
    args = parser.parse_args()

    pattern = os.path.join(args.dir, f"{args.prefix}*")
    paths = sorted(p for p in glob.glob(pattern) if os.path.isfile(p) and is_image(p))

    if not paths:
        print(f"No image files found matching {pattern}")
        return

    if args.seed is not None:
        random.seed(args.seed)
    n = min(args.num, len(paths))
    samples = random.sample(paths, n)

    processor = ImageProcessor(
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
        face_debug_seconds=Config.FACE_DEBUG_DISPLAY_SECONDS,
    )
    receipt_printer = ReceiptPrinter()

    print(f"Found {len(paths)} image(s); printing {n} random sample(s)")
    for path in samples:
        print(f"Processing: {path}")
        fd, tmp = tempfile.mkstemp(suffix=os.path.splitext(path)[1])
        try:
            os.close(fd)
            shutil.copy2(path, tmp)
            processor.process_image(tmp)
            receipt_printer.print_receipt(tmp)
        finally:
            try:
                os.unlink(tmp)
            except OSError:
                pass

    print("Done.")


if __name__ == "__main__":
    main()
