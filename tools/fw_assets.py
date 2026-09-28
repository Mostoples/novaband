"""
Pack the screen assets into one flash image for the T-Display-S3 firmware.

    python tools/fw_assets.py

in:  build/screen/{splash,spin,bg}   (blender/screen_assets.py)
     build/assets3d/*.png            (3D icons, blender/novaband_assets.py)
     build/fonts/Poppins-*.ttf
out: build/fw/assets.bin             flashed to the "assets" partition (0x310000)
     firmware/novaband_display/src/asset_ids.h

Format (little-endian): "NBA1", count, total, 0; then `count` 48-byte entries
{name[24], type, offset, w:u16, h:u16, frames:u16, pad:u16, size, extra};
data 4-byte aligned. Types: 1 RGB565 image(s), 2 RGB565+A8 sprite(s),
3 font, 4 bytes (QR modules). RGB565 is ordered-dithered: the dark bokeh
gradients band badly at 16 bits without it.
"""
import glob
import os
import struct

import numpy as np
import qrcode
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
J = lambda *p: os.path.join(ROOT, *p)
OUT = J("build", "fw")
os.makedirs(OUT, exist_ok=True)
W, H = 320, 170
APP_URL = "https://novaband-id.web.app/app.html#device"

BAYER = (np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) + 0.5) / 16.0


def to565(rgb):
    """float/uint8 HxWx3 -> uint16 RGB565 with 4x4 ordered dither."""
    a = rgb.astype(np.float32)
    h, w = a.shape[:2]
    d = np.tile(BAYER, (h // 4 + 1, w // 4 + 1))[:h, :w]
    r = np.clip(np.floor(a[..., 0] / 255 * 31 + d), 0, 31).astype(np.uint16)
    g = np.clip(np.floor(a[..., 1] / 255 * 63 + d), 0, 63).astype(np.uint16)
    b = np.clip(np.floor(a[..., 2] / 255 * 31 + d), 0, 31).astype(np.uint16)
    return (r << 11) | (g << 5) | b


entries = []   # (name, type, w, h, frames, extra, bytes)


def add(name, typ, w, h, frames, data, extra=0):
    entries.append((name, typ, w, h, frames, extra, data))


# ---------------------------------------------------------------- splash
fr = sorted(glob.glob(J("build", "screen", "splash", "f_*.png")))
blob = bytearray()
xs = np.linspace(0, 1, W)[None, :, None]
left = 0.45 + 0.55 * np.clip(xs / 0.55, 0, 1) ** 1.4          # darken the left for the wordmark
for i, f in enumerate(fr):
    im = np.asarray(Image.open(f).convert("RGB").resize((W, H), Image.LANCZOS)).astype(np.float32)
    fade = min(1.0, (i + 1) / 10.0) ** 1.6                       # fade up from black
    im = im * left * fade
    blob += to565(im).tobytes()
add("splash", 1, W, H, len(fr), bytes(blob))

# ---------------------------------------------------------------- gym bokeh background (parallax, 480 wide)
bg = np.asarray(Image.open(J("build", "screen", "bg", "gym.png")).convert("RGB").resize((480, H), Image.LANCZOS)).astype(np.float32)
lum = bg.mean(axis=2, keepdims=True)
wine = np.array([70, 14, 24], np.float32)
bg = (bg * 0.35 + lum * 0.15) * 0.62 + wine * 0.18                # desaturate, dim, warm-wine grade
yy, xx = np.mgrid[0:H, 0:480]
vig = 1 - 0.55 * (((xx - 240) / 260) ** 2 + ((yy - 85) / 120) ** 2)
bg = bg * np.clip(vig, 0.25, 1)[..., None]
# stored at HALF resolution: it is pure bokeh, so nothing is lost, and at
# 240 x 85 (40 KB) it fits in internal RAM; the firmware upscales it 2x
# bilinearly every frame, which is far cheaper than streaming 108 KB from flash
bgh = np.asarray(Image.fromarray(np.clip(bg, 0, 255).astype(np.uint8)).resize((240, H // 2), Image.LANCZOS))
add("bg", 1, 240, H // 2, 1, to565(bgh).tobytes())


# ---------------------------------------------------------------- sprites
def sprite_bytes(img, size):
    img = img.convert("RGBA")
    # the icon renders carry a shadow-catcher shadow (dark, translucent): drop it,
    # a floating sprite on the glass cards should cast nothing
    a = np.asarray(img).copy()
    shadow = (a[..., 3] < 250) & (a[..., :3].max(axis=2) < 40)
    a[shadow, 3] = 0
    img = Image.fromarray(a, "RGBA")
    box = img.getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox()
    if box:
        img = img.crop(box)
    k = size / max(img.size)
    img = img.resize((max(1, round(img.width * k)), max(1, round(img.height * k))), Image.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.alpha_composite(img, ((size - img.width) // 2, (size - img.height) // 2))
    a = np.asarray(canvas)
    return to565(a[..., :3]).tobytes() + a[..., 3].astype(np.uint8).tobytes()


spin = sorted(glob.glob(J("build", "screen", "spin", "f_*.png")))
# one crop box for all frames, so the band does not jitter as it turns
boxes = [Image.open(f).getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox() for f in spin]
ub = (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))
side = max(ub[2] - ub[0], ub[3] - ub[1])
cx, cy = (ub[0] + ub[2]) // 2, (ub[1] + ub[3]) // 2
SP = 104
blob = bytearray()
for f in spin:
    im = Image.open(f).convert("RGBA").crop((cx - side // 2, cy - side // 2, cx + side // 2, cy + side // 2))
    im = im.resize((SP, SP), Image.LANCZOS)
    a = np.asarray(im)
    blob += to565(a[..., :3]).tobytes() + a[..., 3].tobytes()
add("spin", 2, SP, SP, len(spin), bytes(blob))

# the beating heart: 8 pre-scaled frames (74 % .. 86 %) instead of resampling
# on the device every frame
HEART_N, HEART_BOX = 8, 54
src = Image.open(J("build", "assets3d", "heart.png")).convert("RGBA")
a = np.asarray(src).copy()
a[(a[..., 3] < 250) & (a[..., :3].max(axis=2) < 40), 3] = 0
src = Image.fromarray(a, "RGBA")
src = src.crop(src.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox())
blob = bytearray()
for i in range(HEART_N):
    k = (0.74 + 0.12 * i / (HEART_N - 1)) * 60 / max(src.size)
    im = src.resize((round(src.width * k), round(src.height * k)), Image.LANCZOS)
    cv = Image.new("RGBA", (HEART_BOX, HEART_BOX), (0, 0, 0, 0))
    cv.alpha_composite(im, ((HEART_BOX - im.width) // 2, (HEART_BOX - im.height) // 2))
    q = np.asarray(cv)
    blob += to565(q[..., :3]).tobytes() + q[..., 3].tobytes()
add("heart", 2, HEART_BOX, HEART_BOX, HEART_N, bytes(blob))

ICONS = {"footsteps": 22, "flame": 22, "bluetooth": 22, "battery": 22, "stopwatch": 22,
         "moon": 22, "gauge": 22, "map-pin": 22, "smartphone": 30, "shield": 22}
for name, size in ICONS.items():
    add("ic_" + name.replace("-", "_"), 2, size, size, 1,
        sprite_bytes(Image.open(J("build", "assets3d", name + ".png")), size))


# ---------------------------------------------------------------- fonts
def font(name, ttf, px, first=32, last=126):
    f = ImageFont.truetype(J("build", "fonts", ttf), px)
    asc, desc = f.getmetrics()
    glyphs, alpha = [], bytearray()
    for code in range(first, last + 1):
        ch = chr(code)
        x0, y0, x1, y1 = f.getbbox(ch, anchor="ls")
        w, h = max(0, x1 - x0), max(0, y1 - y0)
        adv = round(f.getlength(ch))
        off = len(alpha)
        if w and h:
            m = Image.new("L", (w, h), 0)
            ImageDraw.Draw(m).text((-x0, -y0), ch, font=f, fill=255, anchor="ls")
            alpha += m.tobytes()
        glyphs.append(struct.pack("<HHhhHHI", w, h, x0, y0, adv, 0, off))
    head = struct.pack("<HHHH", first, last - first + 1, asc + desc, asc)
    add(name, 3, px, 0, 1, head + b"".join(glyphs) + bytes(alpha))


font("f_label", "Poppins-SemiBold.ttf", 10)
font("f_small", "Poppins-Medium.ttf", 12)
font("f_body", "Poppins-SemiBold.ttf", 15)
font("f_title", "Poppins-Bold.ttf", 22)
font("f_brand", "Poppins-ExtraBold.ttf", 30)
font("f_big", "Poppins-Bold.ttf", 46, 32, 63)        # digits, : . - % and space

# ---------------------------------------------------------------- QR to the web app
qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, border=0)
qr.add_data(APP_URL)
qr.make(fit=True)
mods = np.array(qr.get_matrix(), np.uint8)
add("qr", 4, mods.shape[1], mods.shape[0], 1, mods.tobytes())

# ---------------------------------------------------------------- write
HEAD, ENT = 16, 48
off = HEAD + ENT * len(entries)
table, data = bytearray(), bytearray()
for name, typ, w, h, frames, extra, raw in entries:
    pad = (-off) % 4
    data += b"\0" * pad
    off += pad
    table += struct.pack("<24sIIHHHHII", name.encode(), typ, off, w, h, frames, 0, len(raw), extra)
    data += raw
    off += len(raw)
out = struct.pack("<4sIII", b"NBA1", len(entries), off, 0) + table + data
open(os.path.join(OUT, "assets.bin"), "wb").write(out)

hdr = ["// generated by tools/fw_assets.py — do not edit", "#pragma once", "namespace A {"]
for i, e in enumerate(entries):
    hdr.append("constexpr int %s = %d;" % (e[0].upper(), i))
hdr += ["constexpr int COUNT = %d;" % len(entries), "}  // namespace A", ""]
open(J("firmware", "novaband_display", "src", "asset_ids.h"), "w").write("\n".join(hdr))

for name, typ, w, h, frames, extra, raw in entries:
    print("%-14s type %d  %4dx%-4d x%-3d %8.1f KB" % (name, typ, w, h, frames, len(raw) / 1024))
print("assets.bin %.2f MB (partition 12 MB)" % (len(out) / 1048576))
assert len(out) < 0xC00000
