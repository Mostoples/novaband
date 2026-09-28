"""
Static assets for the Nova-Band deck -> deck/assets/{img,static,phones}/

    python tools/prep-deck-assets.py

  img/     photos, app mockup, logos and illustrations from the ISIF deck
           (extracted originals in build/ppt/img), as PNG/JPG — PowerPoint's
           WebP support varies by version, PNG/JPG never fails
  static/  Blender device renders + icons with the deck's warm, feathered
           shadow (transparent, so they sit on the light AND the wine slides)
  phones/  real screens of the live Nova-Band app in a drawn phone bezel
"""
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
J = lambda *p: os.path.join(ROOT, *p)
OUT = J("deck", "assets")
for d in ("img", "static", "phones"):
    os.makedirs(os.path.join(OUT, d), exist_ok=True)

SHADOW = (122, 88, 94)


def trim(im, thr=6, pad=0.02):
    box = im.getchannel("A").point(lambda a: 255 if a > thr else 0).getbbox()
    if not box:
        return im
    p = int(max(im.size) * pad)
    return im.crop((max(box[0] - p, 0), max(box[1] - p, 0),
                    min(box[2] + p, im.width), min(box[3] + p, im.height)))


def fit(im, side):
    if max(im.size) > side:
        k = side / max(im.size)
        im = im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)
    return im


# ---------------------------------------------------------------- 1. deck photos
PHOTOS = {
    "product-side": ("p01_x39_649x852.png", 1000, "png"),
    "product-front": ("p02_x56_371x487.png", 800, "png"),
    "app-phone": ("p01_x40_1068x1968.png", 1000, "png"),
    "team": ("p01_x41_1416x942.png", 1600, "png"),
    "testing": ("p15_x391_1383x922.png", 1300, "jpg"),
    "logo-sman1": ("p01_x42_450x319.png", 500, "png"),
    "logo-reka": ("p01_x44_320x125.png", 400, "png"),
    "logo-uns": ("p01_x45_221x104.png", 300, "png"),
    "logo-mersif-enuma": ("p01_x43_944x156.png", 900, "png"),
    "ill-anxiety": ("p02_x68_1024x974.png", 600, "png"),
    "ill-harm": ("p02_x66_634x584.png", 600, "png"),
    "ill-overtraining": ("p02_x67_272x390.png", 500, "png"),
    "ill-data": ("p02_x65_476x452.png", 600, "png"),
}
for name, (src, side, fmt) in PHOTOS.items():
    im = Image.open(J("build", "ppt", "img", src))
    if fmt == "png":
        im = fit(trim(im.convert("RGBA"), pad=0.0), side)
        im.save(os.path.join(OUT, "img", name + ".png"), optimize=True)
    else:
        fit(im.convert("RGB"), side).save(os.path.join(OUT, "img", name + ".jpg"), quality=88)

# the SMA N 1 logo is a crest + wordmark; keep a crest-only crop for round badges
logo = Image.open(os.path.join(OUT, "img", "logo-sman1.png"))
crest = trim(logo.crop((0, 0, int(logo.height * 0.80), logo.height)))
crest.save(os.path.join(OUT, "img", "crest-sman1.png"))


# The Mersif/Enuma lockup was drawn for a dark slide: its "ENUMA TECHNOLOGY"
# wordmark is white. Recolour only the white pixels to the RIGHT of the blue
# "E" roundel, so the roundel (and its white E) stays exactly as designed.
lock = np.asarray(Image.open(os.path.join(OUT, "img", "logo-mersif-enuma.png")).convert("RGBA")).copy()
r, g, b, a = [lock[..., i].astype(int) for i in range(4)]
blue = (b > r + 40) & (b > 90) & (a > 128)
roundel_right = np.where(blue.any(axis=0))[0].max()
white = (r > 170) & (g > 170) & (b > 170) & (a > 20)
cols = np.arange(lock.shape[1])[None, :] > roundel_right + 2
m = white & cols
lock[m, 0], lock[m, 1], lock[m, 2] = 28, 18, 21
Image.fromarray(lock, "RGBA").save(os.path.join(OUT, "img", "logo-mersif-enuma-light.png"))


# ---------------------------------------------------------------- 2. renders
def warm_shadow(im):
    """Recolour the shadow catcher's black to the deck's warm shadow; feather clipped edges."""
    a = np.asarray(im.convert("RGBA")).astype(np.float32)
    h, w = a.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    r = np.sqrt(((xx - (w - 1) / 2) / (w / 2)) ** 2 + ((yy - (h - 1) / 2) / (h / 2)) ** 2)
    ramp = np.clip((1.0 - r) / 0.30, 0, 1)          # elliptical: no boxy contours
    ramp = ramp * ramp * (3 - 2 * ramp)
    alpha = a[..., 3]
    shadow = (alpha < 250) & (a[..., :3].max(axis=2) < 20)
    a[shadow, 0], a[shadow, 1], a[shadow, 2] = SHADOW
    alpha[shadow] *= ramp[shadow] * 0.85
    a[..., 3] = alpha
    return Image.fromarray(a.clip(0, 255).astype(np.uint8), "RGBA")


RENDERS = {"device-hero": 1100, "device-front": 900, "device-side": 700, "device-exploded": 1000,
           "device-on-arm": 1200, "dots-wave": 1600, "pills": 800, "ring-glossy": 500}
src = J("build", "assets3d")
for f in sorted(os.listdir(src)):
    name = f[:-4]
    side = RENDERS.get(name, 420)
    im = trim(warm_shadow(Image.open(os.path.join(src, f))))
    if name == "device-on-arm":
        # the arm is a cut cylinder: fade its ends so it dissolves instead of stopping
        a = np.asarray(im).astype(np.float32)
        t = np.linspace(0, 1, a.shape[0])[:, None]
        edge = np.clip(np.minimum(t, 1 - t) / 0.22, 0, 1)
        a[..., 3] *= edge * edge * (3 - 2 * edge)
        im = Image.fromarray(a.astype(np.uint8), "RGBA")
    im = fit(im, side)
    im.save(os.path.join(OUT, "static", name + ".png"), optimize=True)


# ---------------------------------------------------------------- 3. phone mockups
def phone(screen_path, out_path, width=560):
    scr = Image.open(screen_path).convert("RGB")
    k = width / scr.width
    scr = scr.resize((width, round(scr.height * k)), Image.LANCZOS)
    # the capture has no status bar: add one, so the island sits above the app
    bar_h = 46
    full = Image.new("RGB", (scr.width, scr.height + bar_h), scr.getpixel((scr.width // 2, 4)))
    full.paste(scr, (0, bar_h))
    bd = ImageDraw.Draw(full)
    try:
        from PIL import ImageFont
        f = ImageFont.truetype(J("build", "fonts", "Poppins-SemiBold.ttf"), 17)
    except Exception:
        f = None
    bd.text((52, bar_h // 2 + 4), "9:41", fill=(28, 18, 21), font=f, anchor="lm")
    x = scr.width - 58
    for i, hgt in enumerate((5, 8, 11, 14)):                     # signal
        bd.rounded_rectangle([x - 56 + i * 6, 30 - hgt, x - 52 + i * 6, 30], 1, fill=(28, 18, 21))
    bd.rounded_rectangle([x - 18, 17, x + 14, 31], 4, outline=(28, 18, 21), width=2)   # battery
    bd.rounded_rectangle([x - 15, 20, x + 7, 28], 2, fill=(28, 18, 21))
    bd.rounded_rectangle([x + 15, 21, x + 18, 27], 1, fill=(28, 18, 21))
    scr = full.crop((0, 0, full.width, full.height - bar_h))    # keep the phone's aspect
    bez, r_out = 22, 86
    r_in = r_out - bez
    W, H = scr.width + 2 * bez, scr.height + 2 * bez
    pad = 70
    canvas = Image.new("RGBA", (W + 2 * pad, H + 2 * pad), (0, 0, 0, 0))

    # soft warm drop shadow
    sh = Image.new("L", canvas.size, 0)
    ImageDraw.Draw(sh).rounded_rectangle([pad + 10, pad + 34, pad + W - 10, pad + H + 18], r_out, fill=120)
    sh = sh.filter(ImageFilter.GaussianBlur(28))
    tint = Image.new("RGBA", canvas.size, SHADOW + (255,))
    tint.putalpha(sh)
    canvas.alpha_composite(tint)

    body = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(body)
    d.rounded_rectangle([0, 0, W - 1, H - 1], r_out, fill=(46, 36, 40, 255))          # titanium edge
    d.rounded_rectangle([3, 3, W - 4, H - 4], r_out - 3, fill=(22, 16, 19, 255))      # bezel
    mask = Image.new("L", scr.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, scr.width - 1, scr.height - 1], r_in, fill=255)
    body.paste(scr, (bez, bez), mask)
    iw, ih = int(W * 0.27), 30
    d.rounded_rectangle([(W - iw) // 2, bez + 9, (W + iw) // 2, bez + 9 + ih], ih // 2, fill=(8, 6, 7, 255))
    canvas.alpha_composite(body, (pad, pad))
    canvas.save(out_path, optimize=True)


for n in ("p-home", "p-live", "p-ready", "p-comm"):
    phone(J("build", "deck", "screens", n + ".png"), os.path.join(OUT, "phones", n + ".png"))

for d in ("img", "static", "phones"):
    files = os.listdir(os.path.join(OUT, d))
    kb = sum(os.path.getsize(os.path.join(OUT, d, f)) for f in files) / 1024
    print("%-7s %3d files %6.0f KB" % (d, len(files), kb))
