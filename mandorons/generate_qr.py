"""
Generate a print-ready QR code that points to the ManDorons landing page.

Install once:    pip install qrcode[pil]
Run:             python generate_qr.py
Output:          mandorons_qr.png  (1200x1200, suitable for A5 print)

Customers scan the QR -> land on the page -> page reads locations.json,
which Doron updates each week. The QR itself never needs reprinting.
"""
import qrcode
from qrcode.constants import ERROR_CORRECT_H

URL = "https://mandorons.com.au"
OUT = "mandorons_qr.png"

qr = qrcode.QRCode(
    version=None,
    error_correction=ERROR_CORRECT_H,
    box_size=24,
    border=4,
)
qr.add_data(URL)
qr.make(fit=True)

img = qr.make_image(fill_color="#1e7a3a", back_color="#fff8ec")
img.save(OUT)
print(f"Saved {OUT} -> {URL}")
