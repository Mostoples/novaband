"""Review sheet: every rendered asset composited on white, labelled."""
import glob, os, sys
from PIL import Image, ImageDraw

src = sys.argv[1] if len(sys.argv) > 1 else "build/assets3d"
out = sys.argv[2] if len(sys.argv) > 2 else "build/assets3d-sheet.png"
T, cols = 300, 5
files = sorted(glob.glob(os.path.join(src, "*.png")))
rows = (len(files) + cols - 1) // cols
sheet = Image.new("RGB", (cols * T, rows * (T + 24)), (255, 255, 255))
d = ImageDraw.Draw(sheet)
for i, f in enumerate(files):
    im = Image.open(f).convert("RGBA")
    im.thumbnail((T - 10, T - 10))
    x, y = (i % cols) * T, (i // cols) * (T + 24)
    sheet.paste(im, (x + (T - im.width) // 2, y + (T - im.height) // 2), im)
    d.rectangle([x, y, x + T - 1, y + T + 23], outline=(235, 230, 230))
    d.text((x + 6, y + T + 5), os.path.basename(f)[:-4], fill=(90, 30, 35))
sheet.save(out)
print(out, len(files), "assets")
