"""
Pack the Nova Run sprites (blender/game_sprites.py -> build/game_sprites/f_0001..0014.png)
into assets/game/nova-sheet.webp: 7 x 2 cells of 300 x 390, frames 0-11 run,
12 jump, 13 slide (row-major). Also cuts the band icon for the HUD from the
product photo -> assets/game/band.webp.

    python tools/make-game-sprites.py
"""
import os
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
J = lambda *p: os.path.join(ROOT, *p)
CW, CH, COLS = 300, 390, 7
os.makedirs(J("assets", "game"), exist_ok=True)

sheet = Image.new("RGBA", (CW * COLS, CH * 2), (0, 0, 0, 0))
for i in range(14):
    im = Image.open(J("build", "game_sprites", "f_%04d.png" % (i + 1))).convert("RGBA")
    sheet.paste(im.resize((CW, CH), Image.LANCZOS), ((i % COLS) * CW, (i // COLS) * CH))
sheet.save(J("assets", "game", "nova-sheet.webp"), "WEBP", quality=88, method=6)

band = Image.open(J("assets", "img", "product-front.webp")).convert("RGBA")
band = band.crop(band.getbbox())
band.thumbnail((128, 128), Image.LANCZOS)
icon = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
icon.paste(band, ((128 - band.width) // 2, (128 - band.height) // 2), band)
icon.save(J("assets", "game", "band.webp"), "WEBP", quality=90)
for f in ("nova-sheet.webp", "band.webp"):
    print(f, os.path.getsize(J("assets", "game", f)) // 1024, "KB")
