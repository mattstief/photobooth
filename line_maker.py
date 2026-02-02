from PIL import Image, ImageDraw
from escpos.printer import usb
from printer_interface import configure_printer

def top_dotted_line(width=470, dot_width=30, gap=4):
    """
    Generates a dotted line bitmap matching typical 80mm printer width (384px).
    Returns a Pillow image 2 rows tall (double dotted).
    """
    # First dotted line (1 pixel tall)
    line = Image.new("L", (width, 1), 255)
    draw = ImageDraw.Draw(line)

    x = 0
    while x < width:
        draw.rectangle([x, 0, x + dot_width - 2, 0], fill=0)
        x += dot_width + gap

    # Create the double-line (two stacked dotted lines with a 1px gap)
    double_line = Image.new("L", (width, 8), 255)
    double_line.paste(line, (0,0))
    double_line.paste(line, (0,2))

    return double_line

def top_dotted_line_2(width=470, dot_width=3, gap=3):
    """
    Generates a dotted line bitmap matching typical 80mm printer width (384px).
    Returns a Pillow image 2 rows tall (double dotted).
    """
    # First dotted line (1 pixel tall)
    line = Image.new("L", (width, 1), 255)
    draw = ImageDraw.Draw(line)

    x = 0
    while x < width:
        draw.rectangle([x, 0, x + dot_width - 2, 0], fill=0)
        x += dot_width + gap

    # Create the double-line (two stacked dotted lines with a 1px gap)
    double_line = Image.new("L", (width, 10), 255)
    double_line.paste(line, (0,0))
    double_line.paste(line, (0,1))

    return double_line


def bottom_dotted_line(width=470, dot_width=30, gap=4):
    """
    Generates a dotted line bitmap matching typical 80mm printer width (384px).
    Returns a Pillow image 2 rows tall (double dotted).
    """
    # First dotted line (1 pixel tall)
    line = Image.new("L", (width, 1), 255)
    draw = ImageDraw.Draw(line)

    x = 0
    while x < width:
        draw.rectangle([x, 0, x + dot_width - 2, 0], fill=0)
        x += dot_width + gap

    # Create the double-line (two stacked dotted lines with a 1px gap)
    double_line = Image.new("L", (width, 20), 255)
    double_line.paste(line, (0,0))
    double_line.paste(line, (0,2))

    return double_line

def bottom_dotted_line_2(width=470, dot_width=3, gap=3):
    """
    Generates a dotted line bitmap matching typical 80mm printer width (384px).
    Returns a Pillow image 2 rows tall (double dotted).
    """
    # First dotted line (1 pixel tall)
    line = Image.new("L", (width, 1), 255)
    draw = ImageDraw.Draw(line)

    x = 0
    while x < width:
        draw.rectangle([x, 0, x + dot_width - 2, 0], fill=0)
        x += dot_width + gap

    # Create the double-line (two stacked dotted lines with a 1px gap)
    double_line = Image.new("L", (width, 8), 255)
    double_line.paste(line, (0,0))
    double_line.paste(line, (0,1))

    return double_line



if __name__ == "__main__":
	p = configure_printer()
	p.image(top_dotted_line())
	p.image(top_dotted_line_2())
	p.textln("lorem ipsum or something")
	p.image(bottom_dotted_line_2())
	p.image(bottom_dotted_line())
	p.textln("BOTTOM TEXT")
	p.cut()

