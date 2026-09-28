"""
Pack the Blender masters (build/assets3d/*.png) into web assets (assets/3d/*.webp).

    python tools/pack-assets.py

Trims the transparent margin (keeping a little breathing room so the
contact shadow isn't clipped), caps the size per asset kind, and writes
lossy WebP with alpha. Also writes assets/3d/manifest.json so the pages
and the showreel compositor can discover what exists.
"""
import glob
import json
import os
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "build", "assets3d")
OUT = os.path.join(ROOT, "assets", "3d")
os.makedirs(OUT, exist_ok=True)

DEVICE = {"device-hero", "device-front", "device-side", "device-exploded", "device-on-arm"}
DECO = {"dots-wave", "pills", "ring-glossy"}


def cap_for(name):
    if name in DEVICE:
        return 1100
    if name in DECO:
        return 1400
    return 480          # icons display at <= 170 CSS px; 480 covers 2.8x screens


def feather_shadow(im, band=0.16):
    """
    The shadow catcher's shadow can run past the camera frame and end in a
    hard, boxy edge. Object pixels are (almost) opaque; shadow pixels are
    translucent. Fade only the translucent ones toward the frame border so
    the shadow dissolves and the object itself is never touched.
    """
    import numpy as np
    a = np.asarray(im).astype(np.float32)
    h, w = a.shape[:2]
    x = np.minimum(np.arange(w), np.arange(w)[::-1]) / (w * band)
    y = np.minimum(np.arange(h), np.arange(h)[::-1]) / (h * band)
    ramp = np.clip(np.minimum.outer(y, x), 0, 1)
    ramp = ramp * ramp * (3 - 2 * ramp)                  # smoothstep
    alpha = a[..., 3]
    shadowish = alpha < 200
    alpha[shadowish] *= ramp[shadowish]
    a[..., 3] = alpha
    return Image.fromarray(a.astype(np.uint8), "RGBA")


manifest = {}
total = 0
for path in sorted(glob.glob(os.path.join(SRC, "*.png"))):
    name = os.path.splitext(os.path.basename(path))[0]
    im = Image.open(path).convert("RGBA")
    im = feather_shadow(im)
    # ignore the faintest shadow fringe when finding the content box
    alpha = im.getchannel("A").point(lambda a: 255 if a > 6 else 0)
    box = alpha.getbbox() or (0, 0, im.width, im.height)
    pad = int(max(im.size) * 0.02)
    box = (max(box[0] - pad, 0), max(box[1] - pad, 0),
           min(box[2] + pad, im.width), min(box[3] + pad, im.height))
    im = im.crop(box)
    cap = cap_for(name)
    if max(im.size) > cap:
        s = cap / max(im.size)
        im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    dst = os.path.join(OUT, name + ".webp")
    im.save(dst, "WEBP", quality=88, method=6, alpha_quality=90)
    kb = os.path.getsize(dst) / 1024
    total += kb
    manifest[name] = {"w": im.width, "h": im.height,
                      "kind": "device" if name in DEVICE else "deco" if name in DECO else "icon"}
    print("%-18s %4dx%-4d %6.1f KB" % (name, im.width, im.height, kb))

with open(os.path.join(OUT, "manifest.json"), "w") as f:
    json.dump(manifest, f, indent=1)
print("\n%d assets, %.0f KB total" % (len(manifest), total))
