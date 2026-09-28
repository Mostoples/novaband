"""
Images for the prototype slides of the deck -> deck/assets/proto/

    python tools/prep-deck-proto.py

  case-sketch.png   the LibreCAD drawing (hardware/casing/out/*.pdf), rasterised
  ui-*.png          the firmware UI (PC simulator frames), in a thin screen bezel
  app-phone.png     the web app (PWA) on a phone, drawn bezel like the other mockups
  gym-*.jpg         Cycles frames from the gym showreel (build/reel2), if rendered
  pod-*.png         product renders of the prototype pod (build/proto), if rendered
"""
import os

import fitz
from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
J = lambda *p: os.path.join(ROOT, *p)
OUT = J("deck", "assets", "proto")
os.makedirs(OUT, exist_ok=True)
SHADOW = (122, 88, 94)

# LibreCAD sheet
doc = fitz.open(J("hardware", "casing", "out", "novaband_case_sketch.pdf"))
pix = doc[0].get_pixmap(dpi=170)
im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
im.save(os.path.join(OUT, "case-sketch.png"), optimize=True)


def screen(frame, name):
    """A simulator frame, 3x, in a black rounded glass bezel with a soft warm shadow."""
    src = Image.open(J("build", "sim", "png", "f_%04d.png" % frame)).convert("RGB")
    s = src.resize((src.width * 3, src.height * 3), Image.LANCZOS)
    pad, bez, r = 40, 22, 42
    W, H = s.width + 2 * bez, s.height + 2 * bez
    cv = Image.new("RGBA", (W + 2 * pad, H + 2 * pad), (0, 0, 0, 0))
    sh = Image.new("L", cv.size, 0)
    ImageDraw.Draw(sh).rounded_rectangle([pad + 8, pad + 22, pad + W - 8, pad + H + 10], r, fill=110)
    sh = sh.filter(ImageFilter.GaussianBlur(18))
    tint = Image.new("RGBA", cv.size, SHADOW + (255,))
    tint.putalpha(sh)
    cv.alpha_composite(tint)
    body = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(body)
    d.rounded_rectangle([0, 0, W - 1, H - 1], r, fill=(12, 9, 11, 255))
    mask = Image.new("L", s.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, s.width - 1, s.height - 1], 10, fill=255)
    body.paste(s, (bez, bez), mask)
    # a faint diagonal glass sheen
    gl = Image.new("L", (W, H), 0)
    ImageDraw.Draw(gl).polygon([(0, 0), (W * .55, 0), (W * .25, H), (0, H)], fill=16)
    body.alpha_composite(Image.merge("RGBA", [Image.new("L", (W, H), 255)] * 3 + [gl]))
    cv.alpha_composite(body, (pad, pad))
    cv.save(os.path.join(OUT, name + ".png"), optimize=True)


# frames of the scripted simulator session (see firmware/sim/sim_main.cpp)
for fr, name in ((40, "ui-boot"), (640, "ui-live"), (602, "ui-run"), (368, "ui-ready"), (463, "ui-link")):
    screen(fr, name)

# phone mockup of the web app, reusing the deck's phone bezel
src = open(J("tools", "prep-deck-assets.py"), encoding="utf-8").read()
phone_src = src[src.index("def phone("):src.index("for n in (\"p-home\"")]
ns = {"Image": Image, "ImageDraw": ImageDraw, "ImageFilter": ImageFilter, "SHADOW": SHADOW, "J": J}
exec(phone_src, ns)
ns["phone"](J("build", "reel2", "app_phone.png"), os.path.join(OUT, "app-phone.png"))

# gym frames and pod renders, when present
for shot, fr, name in (("orbit", 70, "gym-orbit"), ("establish", 90, "gym-wide"), ("arm", 80, "gym-arm"),
                       ("bench", 60, "gym-bench"), ("exploded", 80, "gym-exploded"), ("hero", 60, "gym-hero")):
    p = next((q for q in (J("build", "reel2", shot, "f_%04d.%s" % (fr, e)) for e in ("jpg", "png")) if os.path.exists(q)), None)
    if p:
        Image.open(p).convert("RGB").resize((1600, 900), Image.LANCZOS).save(os.path.join(OUT, name + ".jpg"), quality=88)
def warm(im):
    """Shadow-catcher black -> the deck's warm shadow, then trim to content."""
    import numpy as np
    a = np.asarray(im.convert("RGBA")).astype(np.float32)
    sh = (a[..., 3] < 250) & (a[..., :3].max(axis=2) < 20)
    a[sh, 0], a[sh, 1], a[sh, 2] = SHADOW
    a[sh, 3] *= 0.8
    out = Image.fromarray(a.clip(0, 255).astype(np.uint8), "RGBA")
    return out.crop(out.getchannel("A").point(lambda v: 255 if v > 6 else 0).getbbox())


for f in ("pod-hero.png", "pod-top.png"):
    p = J("build", "proto", f)
    if os.path.exists(p):
        warm(Image.open(p)).save(os.path.join(OUT, f), optimize=True)
print(sorted(os.listdir(OUT)))

# 4:3 crop of the arm close-up for the "Upper-arm fit" card
p = next((q for q in (J("build", "reel2", "arm", "f_0080." + e) for e in ("jpg", "png")) if os.path.exists(q)), None)
if p:
    im = Image.open(p).convert("RGB")
    w = im.height * 4 // 3
    x0 = (im.width - w) // 2
    im.crop((x0, 0, x0 + w, im.height)).resize((1200, 900), Image.LANCZOS).save(os.path.join(OUT, "gym-arm-43.jpg"), quality=88)
