from escpos.printer import Usb

def configure_printer():
	return Usb(0x04b8, 0x0202, 0, profile="TM-T88V", encoding="UTF-8")

def print_photo(printer, filename):
	printer.image(filename)


if __name__ == "__main__":
	p = configure_printer()
	p.text("Hello World\n")
	p.image("images/test.png")
	p.barcode('4006381333931', 'EAN13', 64, 2, '', '')
	p.cut()
