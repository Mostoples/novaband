"""
Tournament-style 3D opening for the documentation recap: the Blender render
of Nova (blender/intro_nova.py -> build/intro_nova/f_####.png, transparent)
over a night-stadium stage built here: sweeping light beams, a gold ring
emblem, bokeh sparks, an impact flash on the landing beat and a metallic
title.

    python blender/intro_nova.py        # ~1 h, resumable
    python tools/make-intro.py          # -> build/rekap/intro3d.mp4 (8 s, no audio)
    python tools/make-intro.py --still 150   # one composited frame -> build/rekap/intro_still.png

tools/make-rekap.py uses build/rekap/intro3d.mp4 as its first shot when present.
"""
import importlib.util
import math
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
J = lambda *p: os.path.join(ROOT, *p)
spec = importlib.util.spec_from_file_location("reel", J("tools", "make-showreel2.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
W, H, FPS = 1920, 1080, 25
N, LAND = 200, 119                     # must match blender/intro_nova.py
TL = (LAND - 1) / FPS                  # landing time, s
FF = R.find_ffmpeg()
SRC = J("build", "intro_nova")
OUT = J("build", "rekap", "intro3d.mp4")
GOLD, GOLD2, RED, WINE = (255, 214, 140), (214, 150, 60), (255, 70, 90), (90, 14, 28)
clamp = lambda x, a=0.0, b=1.0: max(a, min(b, x))
ease = lambda x: 1 - (1 - clamp(x)) ** 3
sm = lambda x: clamp(x) ** 2 * (3 - 2 * clamp(x))
Q = 4                                   # glow layers are drawn at 1/Q resolution, blurred, upscaled
rng = np.random.default_rng(7)


# ------------------------------------------------------------------ static pieces
def base_bg():
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.hypot((xx - W / 2) / W, (yy - H * 0.58) / H * 1.4)
    g = np.clip(1 - r * 1.5, 0, 1) ** 2
    img = np.zeros((H, W, 3), np.float32)
    img[...] = np.array([10, 3, 7], np.float32)
    img += g[..., None] * np.array([110, 18, 34], np.float32)
    return img


BASE = base_bg()
VIG = (np.clip(1 - (np.hypot((np.mgrid[0:H, 0:W][1] - W / 2) / W, (np.mgrid[0:H, 0:W][0] - H / 2) / H) - 0.3) * 1.3, 0.25, 1))[..., None]

# sparks: x, y, depth, speed, phase, colour
NP = 260
SP = np.column_stack([rng.uniform(0, W, NP), rng.uniform(0, H, NP), rng.uniform(0.2, 1, NP),
                      rng.uniform(20, 90, NP), rng.uniform(0, 6.3, NP), rng.integers(0, 3, NP)])
SPC = [GOLD, RED, (255, 240, 220)]


def glow(draw_fn, blur):
    """Draw on a small canvas, blur, return a full-size float RGB layer (additive)."""
    im = Image.new("RGB", (W // Q, H // Q))
    draw_fn(ImageDraw.Draw(im), Q)
    im = im.filter(ImageFilter.GaussianBlur(blur)).resize((W, H), Image.BILINEAR)
    return np.asarray(im, np.float32)


def beams(t, a):
    def fn(d, q):
        for k in range(6):
            side = -1 if k % 2 else 1
            ox = W / 2 + side * (W * 0.55)
            ang = math.radians(90 + side * (28 + 9 * k) + 14 * math.sin(t * 0.9 + k))
            L, w = H * 1.6, 0.06 + 0.02 * (k % 3)
            p0 = (ox / q, -40 / q)
            p1 = ((ox + L * math.cos(ang - w)) / q, (-40 + L * math.sin(ang - w)) / q)
            p2 = ((ox + L * math.cos(ang + w)) / q, (-40 + L * math.sin(ang + w)) / q)
            c = (GOLD if k % 3 else (255, 120, 140))
            d.polygon([p0, p1, p2], fill=tuple(int(v * 0.33 * a) for v in c))
    return glow(fn, 10)


def stage(t, a, pulse):
    """Glowing pitch disc under Nova with concentric gold rings."""
    def fn(d, q):
        cx, cy = W / 2 / q, H * 0.9 / q
        for k, (rx, col, wd) in enumerate(((820, GOLD, 3), (640, RED, 2), (470, GOLD, 2), (300, (255, 240, 220), 2))):
            s = 1 + 0.05 * pulse * (k + 1)
            box = (cx - rx * s / q, cy - rx * 0.16 * s / q, cx + rx * s / q, cy + rx * 0.16 * s / q)
            d.ellipse(box, outline=tuple(int(v * a) for v in col), width=wd)
        d.ellipse((cx - 420 / q, cy - 60 / q, cx + 420 / q, cy + 60 / q), fill=tuple(int(v * 0.35 * a) for v in WINE))
    return glow(fn, 2.2)


def emblem(t, a, scale, spin, cx_px=W / 2):
    """Rotating segmented ring behind Nova (the tournament-badge motif)."""
    def fn(d, q):
        cx, cy = cx_px / q, H * 0.44 / q
        for k in range(24):
            a0 = spin + k * math.tau / 24
            for r0, r1, col in ((318, 346, GOLD if k % 2 else GOLD2), (372, 382, RED if k % 3 == 0 else GOLD2)):
                r0, r1 = r0 * scale / q, r1 * scale / q
                pts = [(cx + r * math.cos(a0 + e), cy + r * math.sin(a0 + e)) for r, e in ((r0, 0.02), (r1, 0.02), (r1, 0.24), (r0, 0.24))]
                d.polygon(pts, fill=tuple(int(v * a) for v in col))
    return glow(fn, 0.8)


def shock(t, cx, cy):
    """Expanding ring + flash after the landing."""
    u = t - TL
    if not 0 <= u < 0.9:
        return None

    def fn(d, q):
        r = (60 + 1500 * ease(u / 0.9)) / q
        a = (1 - u / 0.9) ** 1.5
        d.ellipse((cx / q - r, cy / q - r * 0.28, cx / q + r, cy / q + r * 0.28), outline=tuple(int(v * a) for v in (255, 235, 200)), width=3)
        r2 = r * 0.7
        d.ellipse((cx / q - r2, cy / q - r2 * 0.6, cx / q + r2, cy / q + r2 * 0.6), outline=tuple(int(v * a * 0.6) for v in GOLD), width=2)
    return glow(fn, 1.5)


def speed_lines(t, a):
    def fn(d, q):
        r2 = np.random.default_rng(int(t * FPS))
        cx, cy = W / 2, H * 0.5
        for _ in range(60):
            ang = r2.uniform(0, math.tau)
            r0 = r2.uniform(420, 900)
            L = r2.uniform(120, 420)
            c = int(130 * a * r2.uniform(0.4, 1))
            d.line([((cx + r0 * math.cos(ang)) / q, (cy + r0 * math.sin(ang) * 0.6) / q),
                    ((cx + (r0 + L) * math.cos(ang)) / q, (cy + (r0 + L) * math.sin(ang) * 0.6) / q)], fill=(c, int(c * 0.8), int(c * 0.6)), width=1)
    return glow(fn, 0.6)


def sparks(t, boost):
    im = Image.new("RGB", (W // 2, H // 2))
    d = ImageDraw.Draw(im)
    for x, y, z, v, ph, c in SP:
        yy = (y - v * t * (1 + 2 * boost) * z) % (H + 40) - 20
        xx = x + 18 * math.sin(t * 1.3 + ph) * z
        r = (1 + 4 * z ** 2) / 2
        tw = 0.6 + 0.4 * math.sin(t * 5 + ph * 3)
        col = SPC[int(c)]
        d.ellipse((xx / 2 - r, yy / 2 - r, xx / 2 + r, yy / 2 + r), fill=tuple(int(k * tw * (0.35 + 0.65 * z)) for k in col))
    im = ImageChops.add(im, im.filter(ImageFilter.GaussianBlur(3)))
    return np.asarray(im.resize((W, H), Image.BILINEAR), np.float32)


def flare(t, a, y):
    """Anamorphic horizontal streak."""
    def fn(d, q):
        d.rectangle((0, (y - 3) / q, W / q, (y + 3) / q), fill=tuple(int(v * a) for v in (255, 200, 170)))
        d.ellipse(((W / 2 - 60) / q, (y - 40) / q, (W / 2 + 60) / q, (y + 40) / q), fill=tuple(int(v * a) for v in (255, 245, 230)))
    return glow(fn, 3)


# ------------------------------------------------------------------ title
def metal_text(text_parts, font, shine):
    """Gold-metal title with a moving shine band; returns RGBA."""
    tmp = ImageDraw.Draw(Image.new("L", (10, 10)))
    widths = [tmp.textlength(s, font=font) for s, _ in text_parts]
    tw, th = int(sum(widths)) + 40, int(font.size * 1.3)
    mask_gold, mask_red = Image.new("L", (tw, th)), Image.new("L", (tw, th))
    x = 20
    for (s, red), w in zip(text_parts, widths):
        ImageDraw.Draw(mask_red if red else mask_gold).text((x, th // 2), s, font=font, fill=255, anchor="lm")
        x += w
    yy, xx = np.mgrid[0:th, 0:tw].astype(np.float32)
    v = yy / th
    grad = np.stack([255 - 30 * v, 225 - 95 * v, 150 - 110 * v], -1)
    band = np.exp(-((xx - yy * 0.5 - shine * (tw + th)) / 40) ** 2)[..., None]
    gold = np.clip(grad + band * 120, 0, 255)
    red = np.clip(np.stack([255 - 40 * v, 70 - 30 * v, 90 - 40 * v], -1) + band * 90, 0, 255)
    mg, mr = np.asarray(mask_gold, np.float32)[..., None] / 255, np.asarray(mask_red, np.float32)[..., None] / 255
    rgb = gold * mg + red * mr
    a = np.clip(mg + mr, 0, 1)
    out = np.concatenate([rgb, a * 255], -1).astype(np.uint8)
    im = Image.fromarray(out, "RGBA")
    edge = im.split()[3].filter(ImageFilter.GaussianBlur(10))
    glow_l = Image.new("RGBA", im.size, (255, 90, 80, 0))
    glow_l.putalpha(edge.point(lambda p: int(p * 0.55)))
    return Image.alpha_composite(glow_l, im)


# ------------------------------------------------------------------ frame
def mascot(f):
    p = os.path.join(SRC, "f_%04d.png" % f)
    return Image.open(p).convert("RGBA") if os.path.exists(p) else None


def frame(f):
    t = (f - 1) / FPS
    u = t - TL
    img = BASE.copy()
    fade_in = ease(t / 0.8)
    img += beams(t, fade_in * (0.7 + 0.3 * (u > 0)))
    pulse = math.exp(-max(u, 0) * 3) if u > 0 else 0
    img += stage(t, fade_in * (0.6 + 0.4 * ease((t - 0.5) / 1.5)), pulse)
    if t > 2.6:
        sc = 0.4 + 0.75 * ease((t - 2.6) / 2.2) + 0.08 * pulse
        img += emblem(t, ease((t - 2.6) / 1.2) * (0.4 + 0.5 * pulse), sc, t * 0.35, W / 2 - 420 * ease((t - 5.2) / 1.0))
    if t < 3.6:
        img += speed_lines(t, ease(t / 0.5) * (1 - ease((t - 2.8) / 0.8)))
    img += sparks(t, pulse) * (0.5 + 0.5 * fade_in)
    s = shock(t, W / 2, H * 0.9)
    if s is not None:
        img += s
    img *= VIG
    canvas = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).convert("RGBA")

    # Nova: slides to the left third for the title
    m = mascot(f)
    slide = ease((t - 5.2) / 1.0)
    if m is not None:
        k = 1.0 - 0.08 * slide
        if k != 1:
            m = m.resize((int(W * k), int(H * k)), Image.LANCZOS)
        ox = int((W - m.width) / 2 - 420 * slide)
        oy = int((H - m.height) * 0.75)
        sh = int(14 * pulse * math.sin(u * 60)) if 0 < u < 0.35 else 0
        rim = Image.new("RGBA", m.size, (255, 80, 90, 0))
        rim.putalpha(m.split()[3].filter(ImageFilter.GaussianBlur(14)).point(lambda p: int(p * 0.45)))
        canvas.alpha_composite(rim, (ox + sh, oy))
        canvas.alpha_composite(m, (ox + sh, oy + sh // 2))

    canvas = canvas.convert("RGB")                          # RGBA drawing only blends on RGB
    d = ImageDraw.Draw(canvas, "RGBA")
    # title block
    if t > 5.5:
        a = ease((t - 5.5) / 0.6)
        ttl = metal_text([("NOVA", False), ("-", True), ("BAND", False)], R.XB(150 * W / 1920), ((t - 5.6) / 1.6) % 1.6)
        tx = int(W * 0.69 - ttl.width / 2 + (1 - a) * 120)
        ty = int(H * 0.36)
        tt = ttl.copy()
        tt.putalpha(tt.split()[3].point(lambda p: int(p * a)))
        canvas.paste(tt, (tx, ty), tt)
        b = ease((t - 6.0) / 0.6)
        cx = W * 0.69
        d.rectangle((cx - 260 * b, ty + ttl.height + 6, cx + 260 * b, ty + ttl.height + 9), fill=GOLD + (int(230 * b),))
        f1, f2 = R.SEMI(30), R.SERIF(46)
        d.text((cx, ty - 26), "REKAP DOKUMENTASI  ·  2026", font=f1, fill=(255, 225, 190, int(255 * ease((t - 5.9) / 0.6))), anchor="mm")
        d.text((cx, ty + ttl.height + 60), "Pengujian & Kemitraan", font=f2, fill=(255, 240, 225, int(255 * ease((t - 6.2) / 0.7))), anchor="mm")
        d.text((cx, ty + ttl.height + 118), "Tim Peneliti SMA Negeri 1 Surakarta", font=R.REG(26),
               fill=(230, 200, 205, int(255 * ease((t - 6.5) / 0.7))), anchor="mm")

    out = np.asarray(canvas.convert("RGB"), np.float32)
    # flares: opening streak, landing flash
    out += flare(t, clamp(1 - t / 0.9) * 1.2, H * 0.47)
    if 0 <= u < 0.3:
        out += 255 * 0.45 * (1 - u / 0.3) ** 2
    out *= ease(t / 0.35)                                   # fade from black
    grain = rng.normal(0, 4.5, (H // 2, W // 2, 1)).repeat(2, 0).repeat(2, 1)
    return np.clip(out + grain, 0, 255).astype(np.uint8)


def main():
    if "--still" in sys.argv:
        f = int(sys.argv[sys.argv.index("--still") + 1])
        Image.fromarray(frame(f)).save(J("build", "rekap", "intro_still.png"))
        return
    missing = [f for f in range(1, N + 1) if not os.path.exists(os.path.join(SRC, "f_%04d.png" % f))]
    if missing:
        raise SystemExit("%d Blender frames missing (first %d): run python blender/intro_nova.py" % (len(missing), missing[0]))
    enc = subprocess.Popen([FF, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H), "-r", str(FPS),
                            "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "14", "-pix_fmt", "yuv420p", OUT],
                           stdin=subprocess.PIPE)
    for f in range(1, N + 1):
        enc.stdin.write(frame(f).tobytes())
        if f % 25 == 0:
            print("frame", f, flush=True)
    enc.stdin.close()
    enc.wait()
    print(OUT)


if __name__ == "__main__":
    main()
