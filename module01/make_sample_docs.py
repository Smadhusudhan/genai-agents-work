"""Generate synthetic KYC-style sample documents for vision experiments.
    uv run python module01/make_sample_docs.py
Everything here is invented: fictional people, fake numbers, a big SAMPLE watermark.
These are teaching images, not copies of any real identity document."""
from __future__ import annotations

import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = Path(__file__).with_name("sample_docs")
FONT_DIRS = ["/usr/share/fonts/truetype/liberation/", "/usr/share/fonts/truetype/dejavu/", "C:/Windows/Fonts/"]


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    names = ["LiberationSans-Bold.ttf", "DejaVuSans-Bold.ttf", "arialbd.ttf"] if bold else \
            ["LiberationSans-Regular.ttf", "DejaVuSans.ttf", "arial.ttf"]
    for d in FONT_DIRS:
        for n in names:
            p = Path(d) / n
            if p.exists():
                return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def card(title: str, rows: list[tuple[str, str]], accent: str, name: str, noisy: bool = False) -> None:
    w, h = 900, 560
    img = Image.new("RGB", (w, h), "#FFFFFF")
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, w, 90], fill=accent)
    d.text((30, 26), title, font=font(34, True), fill="white")
    y = 130
    for label, value in rows:
        d.text((40, y), label.upper(), font=font(18), fill="#5F6B7A")
        d.text((40, y + 24), value, font=font(30, True), fill="#14202E")
        y += 82
    d.text((470, 470), "SAMPLE - NOT A REAL DOCUMENT", font=font(20, True), fill="#C0392B")
    d.rectangle([2, 2, w - 3, h - 3], outline=accent, width=4)
    if noisy:
        rnd = random.Random(7)
        for _ in range(2500):
            x, yy = rnd.randrange(w), rnd.randrange(h)
            d.point((x, yy), fill=(rnd.randrange(90, 200),) * 3)
        img = img.rotate(3.5, expand=True, fillcolor="#EDEDED").filter(ImageFilter.GaussianBlur(1.6))
    img.save(OUT / name)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    card("SAMPLE IDENTITY CARD", [("Full name", "ANANYA RAO VEMULA"), ("Date of birth", "14/03/1994"),
                                  ("ID number", "ABCDE1234F")], "#0B3C5D", "doc1_id_card.png")
    card("SAMPLE UTILITY BILL", [("Customer name", "RAHUL KUMAR SHARMA"), ("Service address", "12-4-56, Lake View Colony, Hyderabad 500032"),
                                 ("Bill date", "02/09/2026")], "#0E8C8C", "doc2_utility_bill.png")
    card("SAMPLE IDENTITY CARD", [("Full name", "MEERA IYER"), ("Date of birth", "09/11/1988"),
                                  ("ID number", "PQRST5678Z")], "#9A6A00", "doc3_messy_scan.png", noisy=True)
    print("wrote", sorted(p.name for p in OUT.glob("*.png")))


if __name__ == "__main__":
    main()
