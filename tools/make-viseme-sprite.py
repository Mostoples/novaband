"""Pack Nova's talking-head renders into one web sprite for the AI Buddy.

    python blender/nova_visemes.py      # build/visemes/<viseme>_<eyes>.png
    python tools/make-viseme-sprite.py  # -> assets/img/nova-visemes.webp

Columns follow VISEMES (same order as js/nova-buddy.js), row 0 = eyes open,
row 1 = eyes closed. Each cell is a square crop around the head.
"""
import os
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "build", "visemes")
OUT = os.path.join(ROOT, "assets", "img", "nova-visemes.webp")
VISEMES = ["rest", "m", "e", "i", "o", "u", "a"]
CROP = (140, 0, 580, 440)   # head + collar in the 720 px render
CELL = 192                  # 2x of the largest on-screen size (96 px)

sheet = Image.new("RGBA", (CELL * len(VISEMES), CELL * 2), (0, 0, 0, 0))
for r, eyes in enumerate("oc"):
    for c, v in enumerate(VISEMES):
        im = Image.open(os.path.join(SRC, "%s_%s.png" % (v, eyes))).convert("RGBA")
        sheet.paste(im.crop(CROP).resize((CELL, CELL), Image.LANCZOS), (c * CELL, r * CELL))
sheet.save(OUT, "WEBP", quality=82, method=6)
print(OUT, sheet.size, os.path.getsize(OUT) // 1024, "KB")
