"""
"Kenalan dengan Nova-Band": Nova the mascot explains the band (~80 s).

    python tools/nova-voice.py                 # narration -> build/nova_vo/
    python blender/mascot_anim.py --anim all   # mascot clips -> build/mascot_anim/
    python tools/make-nova-explainer.py        # -> assets/nova-explainer.{mp4,webm} + poster
    python tools/make-nova-explainer.py --preview   # 960 px, every 4th frame, no audio

Nova stands on a holo pad on the left; each scene builds its panel on the
right (the band screens come from the firmware simulator, build/sim/),
with captions of the narration. Frames stream into ffmpeg.
"""
import glob
import importlib.util
import json
import math
import os
import re
import subprocess
import sys
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
J = lambda *p: os.path.join(ROOT, *p)
spec = importlib.util.spec_from_file_location("reel", J("tools", "make-showreel2.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
spec = importlib.util.spec_from_file_location("vo", J("tools", "nova-voice.py"))
VO = importlib.util.module_from_spec(spec)
spec.loader.exec_module(VO)

PREVIEW = "--preview" in sys.argv
W, H = (960, 540) if PREVIEW else (1920, 1080)
K = W / 1920
R.K = K
FPS = 24
XF = 10
LEAD, TAIL = 0.45, 0.75
NEON, ROSE, CREAM, CYAN, WHITE = (255, 79, 99), (230, 160, 172), (243, 227, 211), (95, 227, 255), (255, 255, 255)
BOLD, XB, SEMI, REG, SERIF = R.BOLD, R.XB, R.SEMI, R.REG, R.SERIF
clamp, ease = R.clamp, R.ease


def S(v):
    return int(round(v * K))


# ---------------------------------------------------------------- background
MARGIN = int(80 * K)
def build_bg():
    yy = np.linspace(0, 1, H)[:, None, None]
    top, bot = np.array([10, 4, 9]), np.array([24, 6, 14])
    base = (top + (bot - top) * yy) * np.ones((1, W, 1))
    rng = np.random.default_rng(3)
    im = Image.fromarray(base.astype(np.uint8)).convert("RGBA")
    d = ImageDraw.Draw(im)
    for _ in range(170):
        x, y = rng.uniform(0, W), rng.uniform(0, H * 0.64)
        r = rng.uniform(0.4, 1.6) * K + 0.3
        a = int(rng.uniform(60, 200))
        d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 215, 222, a))
    blobs = []
    for (cx, cy, rr, col) in ((0.12, 0.05, 0.42, (150, 16, 42)), (0.92, 0.25, 0.36, (85, 14, 70)),
                              (0.55, 1.0, 0.30, (40, 120, 150))):
        L = Image.new("RGBA", (W + 2 * MARGIN, H + 2 * MARGIN), (0, 0, 0, 0))   # bigger than the frame: it drifts
        ImageDraw.Draw(L).ellipse([MARGIN + (cx - rr) * W, MARGIN + cy * H - rr * W, MARGIN + (cx + rr) * W,
                                   MARGIN + cy * H + rr * W], fill=col + (150,))
        blobs.append(L.filter(ImageFilter.GaussianBlur(150 * K)))
    return im, blobs


def build_grid(phases=FPS):
    """A perspective grid floor that scrolls toward the camera (one loop per second)."""
    yh = int(H * 0.62)
    ys = np.arange(yh + 1, H)[:, None].astype(np.float64)
    xs = np.arange(W)[None, :].astype(np.float64)
    f, hc = 900 * K, 3.4
    z = f * hc / (ys - yh)
    xw = (xs - W / 2) * z / f
    dx = np.abs(xw - np.round(xw)) * f / z                         # distance to a line, px
    fade = np.clip((ys - yh) / (H * 0.30), 0, 1) ** 1.4 * np.clip((H - ys) / (H * 0.08) + 0.4, 0, 1)
    dzdy = f * hc / (ys - yh) ** 2
    out = []
    for p in range(phases):
        zz = z + p / phases
        dz = np.abs(zz - np.round(zz)) / dzdy
        a = np.maximum(np.clip(1.3 - dx / (1.1 * K + .3), 0, 1), np.clip(1.3 - dz / (1.1 * K + .3), 0, 1)) * fade
        rgba = np.zeros((H - yh - 1, W, 4), np.uint8)
        rgba[..., :3] = NEON
        rgba[..., 3] = (a * 120).astype(np.uint8)
        out.append(Image.fromarray(rgba, "RGBA"))
    return yh + 1, out


BG, BLOBS = None, None
GRID_Y, GRID = None, None


def background(t):
    im = BG.copy()
    for k, b in enumerate(BLOBS):
        ox = int(math.sin(t * 0.21 + k * 2) * 60 * K)
        oy = int(math.cos(t * 0.17 + k) * 40 * K)
        im.alpha_composite(b.crop((MARGIN - ox, MARGIN - oy, MARGIN - ox + W, MARGIN - oy + H)))
    im.alpha_composite(GRID[int(t * FPS) % len(GRID)], (0, GRID_Y))
    return im


# ---------------------------------------------------------------- mascot
CLIP_CAM = {"idle": (1.0, 1.1), "wave": (1.08, 1.2), "run": (1.02, 1.12), "talk": (1.0, 1.1),
            "flex": (1.05, 1.15), "thumbs": (1.0, 1.1), "cheer": (1.2, 1.32), "alert": (1.02, 1.12)}
PX_PER_M = 820 / 2.2
FEET = (480, 1000)
_clip = {}


def clip_frames(name):
    if name not in _clip:
        _clip.clear()
        fs = sorted(glob.glob(J("build", "mascot_anim", name, "f_*.png")))
        tz, hh = CLIP_CAM[name]
        h = S(PX_PER_M * 2 * hh)
        frames = []
        for f in fs:
            im = Image.open(f).convert("RGBA")
            w = int(im.width * h / im.height)
            frames.append(im.resize((w, h), Image.BILINEAR if PREVIEW else Image.LANCZOS))
        ground = (tz + hh) / (2 * hh)                     # ground row, fraction from the top
        _clip[name] = (frames, ground)
    return _clip[name]


def mascot(im, name, t):
    frames, ground = clip_frames(name)
    # holo pad
    cx, cy = S(FEET[0]), S(FEET[1])
    pad = Image.new("RGBA", (S(560), S(160)), (0, 0, 0, 0))
    pd = ImageDraw.Draw(pad)
    pw, ph = pad.size
    for k in range(10, 0, -1):
        a = int(18 + 10 * (10 - k))
        rx, ry = pw / 2 * k / 10, ph / 2 * k / 10 * 0.55
        pd.ellipse([pw / 2 - rx, ph / 2 - ry, pw / 2 + rx, ph / 2 + ry], fill=NEON + (int(a * 0.5),))
    for k in range(2):
        u = (t * 0.45 + k * 0.5) % 1
        rx, ry = pw / 2 * (0.45 + 0.55 * u), ph / 2 * 0.55 * (0.45 + 0.55 * u)
        pd.ellipse([pw / 2 - rx, ph / 2 - ry, pw / 2 + rx, ph / 2 + ry], outline=(255, 150, 165, int(220 * (1 - u))),
                   width=max(1, S(3)))
    im.alpha_composite(pad.filter(ImageFilter.GaussianBlur(2 * K)), (cx - pw // 2, cy - ph // 2))
    if not frames:
        return
    fr = frames[int(t * FPS) % len(frames)]
    im.alpha_composite(fr, (cx - fr.width // 2, int(cy - ground * fr.height)))


# ---------------------------------------------------------------- drawing helpers
_masks = {}


def rmask(size, r):
    key = (size, r)
    if key not in _masks:
        m = Image.new("L", size, 0)
        ImageDraw.Draw(m).rounded_rectangle([0, 0, size[0] - 1, size[1] - 1], r, fill=255)
        _masks[key] = m
    return _masks[key]


def glass(im, box, a, r=28, tint=(40, 12, 22), edge=(255, 140, 155)):
    if a <= 0:
        return
    x0, y0, x1, y1 = [int(v) for v in box]
    size = (x1 - x0, y1 - y0)
    crop = im.crop((x0, y0, x1, y1)).filter(ImageFilter.GaussianBlur(16 * K))
    fill = Image.new("RGBA", size, tint + (150,))
    crop.alpha_composite(fill)
    m = rmask(size, S(r))
    im.paste(crop, (x0, y0), m.point(lambda v: int(v * a)))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle(box, S(r), outline=edge + (int(110 * a),), width=max(1, S(2)))


def text(d, xy, s, f, fill, a=1.0, anchor="la"):
    if a > 0:
        d.text(xy, s, font=f, fill=fill + (int(255 * a),), anchor=anchor)


def spaced(d, xy, s, f, fill, a, sp=4):
    R.txt(d, xy, s, f, fill, a, spacing=S(sp))


def glow_text(im, xy, s, f, fill, a, radius=18):
    if a <= 0:
        return
    L = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(L).text(xy, s, font=f, fill=NEON + (int(200 * a),))
    im.alpha_composite(L.filter(ImageFilter.GaussianBlur(radius * K)))
    ImageDraw.Draw(im).text(xy, s, font=f, fill=fill + (int(255 * a),))


def paste(im, src, xy, a=1.0):
    if a <= 0:
        return
    if a < 1:
        src = src.copy()
        src.putalpha(src.getchannel("A").point(lambda v: int(v * a)))
    im.alpha_composite(src, (int(xy[0]), int(xy[1])))


_img = {}


def img(path, h=None, w=None):
    key = (path, h, w)
    if key not in _img:
        im = Image.open(J(*path.split("/"))).convert("RGBA")
        if h:
            im = im.resize((int(im.width * h / im.height), h), Image.LANCZOS)
        elif w:
            im = im.resize((w, int(im.height * w / im.width)), Image.LANCZOS)
        _img[key] = im
    return _img[key]


def appear(t, at, d=0.5):
    return ease((t - at) / d)


def header(im, d, tag, title, t, dur):
    a = appear(t, 0.15) * fade_out(t, dur)
    spaced(d, (S(900), S(150)), tag, SEMI(24), CYAN, a, 5)
    text(d, (S(898), S(178)), title, XB(64), WHITE, a)


def fade_out(t, dur):
    return 1 - clamp((t - (dur - 0.35)) / 0.35)


def chip(im, d, xy, s, a, f=None):
    f = f or SEMI(28)
    w = f.getlength(s) + S(44)
    x, y = xy
    glass(im, (x, y, x + w, y + S(58)), a, r=29)
    d = ImageDraw.Draw(im)
    d.ellipse([x + S(18), y + S(25), x + S(26), y + S(33)], fill=NEON + (int(255 * a),))
    text(d, (x + S(34), y + S(29)), s, f, WHITE, a, "lm")
    return w


def band_screen(im, scenario, t, box_xy, scale, a, alert=0.0):
    fs = sorted(glob.glob(J("build", "sim", scenario, "f_*.png")))
    if not fs or a <= 0:
        return
    k = min(int(t * 30), len(fs) - 1) if scenario == "alert" else int(t * 30) % len(fs)
    scr = Image.open(fs[k]).convert("RGBA")
    w, h = S(320 * scale), S(170 * scale)
    scr = scr.resize((w, h), Image.LANCZOS if not PREVIEW else Image.BILINEAR)
    x, y = box_xy
    pad = S(26)
    bez = Image.new("RGBA", (w + 2 * pad, h + 2 * pad), (0, 0, 0, 0))
    bd = ImageDraw.Draw(bez)
    bd.rounded_rectangle([0, 0, bez.width - 1, bez.height - 1], S(46), fill=(60, 12, 20, 255),
                         outline=(150, 40, 55, 255), width=S(3))
    bd.rounded_rectangle([pad - S(6), pad - S(6), pad + w + S(6), pad + h + S(6)], S(18), fill=(4, 2, 3, 255))
    bez.paste(scr, (pad, pad), rmask((w, h), S(12)))
    col = (255, 60, 70) if alert > 0 else NEON
    g = Image.new("RGBA", (bez.width + S(120), bez.height + S(120)), (0, 0, 0, 0))
    ImageDraw.Draw(g).rounded_rectangle([S(60), S(60), S(60) + bez.width, S(60) + bez.height], S(46),
                                        fill=col + (int((90 + 120 * alert) * a),))
    im.alpha_composite(g.filter(ImageFilter.GaussianBlur(30 * K)), (int(x - S(60)), int(y - S(60))))
    paste(im, bez, (x, y), a)


# ---------------------------------------------------------------- scenes (panel on the right)
def sc_intro(im, d, t, dur):
    a = fade_out(t, dur)
    spaced(d, (S(905), S(300)), "KENALAN DENGAN", SEMI(30), CYAN, appear(t, 0.2) * a, 8)
    glow_text(im, (S(895), S(330)), "Nova-Band", XB(150), WHITE, appear(t, 0.45, 0.7) * a, 26)
    d = ImageDraw.Draw(im)
    text(d, (S(905), S(555)), "Wearable AIoT di lengan atas untuk pelari", REG(40), CREAM, appear(t, 0.9) * a)
    x = S(905)
    for i, s in enumerate(("Detak jantung real-time", "Early warning", "Readiness AI")):
        x += chip(im, d, (x, S(650)), s, appear(t, 1.4 + i * 0.35) * a) + S(16)
    prod = img("assets/img/product-side.webp", h=S(250))
    bob = math.sin(t * 1.6) * S(10)
    paste(im, prod.rotate(-14, expand=True, resample=Image.BICUBIC), (S(1580), S(650) + bob), appear(t, 2.2, 0.8) * a)


PROBLEMS = [("assets/3d/flame.webp", "Overtraining", "Latihan terlalu keras tanpa tahu kondisi tubuh"),
            ("assets/3d/spring-tendon.webp", "Cedera otot & sendi", "Beban berlebih menumpuk tanpa terasa"),
            ("assets/3d/heart.webp", "Risiko gangguan jantung", "Detak jantung melewati batas aman")]


def sc_problem(im, d, t, dur):
    header(im, d, "MASALAHNYA", "Lari tanpa data tubuh", t, dur)
    for i, (icon, title, sub) in enumerate(PROBLEMS):
        a = appear(t, 1.0 + i * 1.5, 0.6) * fade_out(t, dur)
        if a <= 0:
            continue
        x = S(900) + int((1 - a) * S(160))
        y = S(330 + i * 200)
        glass(im, (x, y, x + S(900), y + S(170)), a)
        paste(im, img(icon, h=S(130)), (x + S(24), y + S(20)), a)
        d = ImageDraw.Draw(im)
        text(d, (x + S(180), y + S(42)), title, BOLD(42), WHITE, a)
        text(d, (x + S(180), y + S(102)), sub, REG(28), ROSE, a)
        d.rounded_rectangle([x + S(870), y + S(30), x + S(878), y + S(140)], S(4), fill=NEON + (int(220 * a),))


SPECS = ["Sensor PPG optik", "IMU (gerak & langkah)", "ESP32-S3 + AI di perangkat", "Layar sentuh 1,9\"",
         "Bluetooth LE + USB-C", "Baterai Li-Po"]


def sc_device(im, d, t, dur):
    header(im, d, "PERANGKAT", "Dipakai di lengan atas", t, dur)
    a = fade_out(t, dur)
    prod = img("assets/img/product-side.webp", h=S(600))
    paste(im, prod, (S(930), S(320) + math.sin(t * 1.5) * S(10)), appear(t, 0.5, 0.8) * a)
    for i, s in enumerate(SPECS):
        b = appear(t, 1.3 + i * 0.6) * a
        chip(im, d, (S(1400) + int((1 - b) * S(80)), S(330 + i * 92)), s, b, SEMI(26))


def metric_card(im, x, y, w, label, value, unit, a):
    glass(im, (x, y, x + w, y + S(150)), a)
    d = ImageDraw.Draw(im)
    spaced(d, (x + S(26), y + S(22)), label, SEMI(20), ROSE, a, 3)
    text(d, (x + S(24), y + S(58)), value, XB(56), WHITE, a)
    vw = XB(56).getlength(value)
    text(d, (x + S(34) + vw, y + S(84)), unit, REG(24), ROSE, a)


def sc_live(im, d, t, dur):
    header(im, d, "LIVE MONITORING", "Data real-time saat lari", t, dur)
    a = fade_out(t, dur)
    band_screen(im, "run", t, (S(960), S(290)), 2.45, appear(t, 0.5, 0.7) * a)
    hr = 150 + int(4 * math.sin(t * 0.9))
    cards = [("DETAK JANTUNG", str(hr), "bpm"), ("KADENSI", str(170 + int(2 * math.sin(t * 1.3))), "spm"),
             ("PACE", "5:21", "/km"), ("JARAK", ("%.2f" % (3.2 + t * 0.004)).replace(".", ","), "km")]
    for i, (lab, v, u) in enumerate(cards):
        b = appear(t, 2.0 + i * 0.5) * a
        metric_card(im, S(900 + i * 232), S(800) + int((1 - b) * S(40)), S(216), lab, v, u, b)


def sc_alert(im, d, t, dur):
    header(im, d, "EARLY WARNING", "Peringatan dini", t, dur)
    a = fade_out(t, dur)
    crossed = clamp((t - 2.6) / 0.3)
    pulse = crossed * (0.5 + 0.5 * math.sin(t * 9))
    band_screen(im, "alert", t, (S(960), S(290)), 2.45, appear(t, 0.4, 0.7) * a, alert=pulse)
    b = appear(t, 3.4, 0.6) * a
    if b > 0:
        x, y = S(1000) + int((1 - b) * S(200)), S(790)
        glass(im, (x, y, x + S(800), y + S(170)), b, tint=(70, 12, 22), edge=(255, 90, 100))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle([x + S(26), y + S(30), x + S(106), y + S(110)], S(22), fill=NEON + (int(255 * b),))
        text(d, (x + S(66), y + S(70)), "N", XB(46), WHITE, b, "mm")
        spaced(d, (x + S(130), y + S(28)), "NOVA-BAND · SEKARANG", SEMI(20), ROSE, b, 3)
        text(d, (x + S(128), y + S(58)), "Raka: 188 bpm, di atas batas 182", BOLD(34), WHITE, b)
        text(d, (x + S(128), y + S(110)), "Pelatih & grup lari sudah diberi tahu", REG(26), CREAM, b)


FACTORS = [("Variabilitas detak (HRV)", 72), ("Detak istirahat", 80), ("Beban latihan", 65), ("Pemulihan", 88)]


def sc_ready(im, d, t, dur):
    header(im, d, "READINESS SCORE", "Gas atau istirahat?", t, dur)
    a = fade_out(t, dur)
    b = appear(t, 0.5, 0.6) * a
    cx, cy, r = S(1110), S(560), S(185)
    p = ease((t - 0.8) / 1.8) * 0.82
    if b > 0:
        L = Image.new("RGBA", im.size, (0, 0, 0, 0))
        ld = ImageDraw.Draw(L)
        ld.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(255, 255, 255, int(40 * b)), width=S(26))
        if p > 0:
            ld.arc([cx - r, cy - r, cx + r, cy + r], -90, -90 + 360 * p, fill=NEON + (int(255 * b),), width=S(26))
        im.alpha_composite(L.filter(ImageFilter.GaussianBlur(14 * K)))
        im.alpha_composite(L)
        d = ImageDraw.Draw(im)
        text(d, (cx, cy - S(14)), str(int(round(p * 100))), XB(120), WHITE, b, "mm")
        text(d, (cx, cy + S(74)), "SIAP · SESI TEMPO", SEMI(24), ROSE, b, "mm")
    for i, (lab, v) in enumerate(FACTORS):
        c = appear(t, 2.6 + i * 0.7) * a
        if c <= 0:
            continue
        x, y = S(1380), S(370 + i * 120)
        d = ImageDraw.Draw(im)
        text(d, (x, y), lab, SEMI(28), WHITE, c)
        text(d, (x + S(440), y), str(v), BOLD(28), NEON, c, "ra")
        d.rounded_rectangle([x, y + S(52), x + S(440), y + S(66)], S(7), fill=(255, 255, 255, int(40 * c)))
        fw = S(440) * v / 100 * ease((t - 2.8 - i * 0.7) / 1.0)
        if fw > S(14):
            d.rounded_rectangle([x, y + S(52), x + fw, y + S(66)], S(7), fill=NEON + (int(255 * c),))


def sc_app(im, d, t, dur):
    header(im, d, "APLIKASI", "Semua data di satu app", t, dur)
    a = fade_out(t, dur)
    b = appear(t, 0.4, 0.8) * a
    desk = img("build/app_desk.png", w=S(840))
    desk = desk.crop((0, 0, desk.width, min(desk.height, S(560))))
    z = 1 + 0.03 * t / dur
    dz = desk.resize((int(desk.width * z), int(desk.height * z)), Image.BILINEAR)
    frame = Image.new("RGBA", (S(840), S(560)), (0, 0, 0, 0))
    frame.paste(dz, (-(dz.width - frame.width) // 2, 0))
    m = rmask(frame.size, S(22))
    fr = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    fr.paste(frame, (0, 0), m)
    g = Image.new("RGBA", (fr.width + S(100), fr.height + S(100)), (0, 0, 0, 0))
    ImageDraw.Draw(g).rounded_rectangle([S(50), S(50), S(50) + fr.width, S(50) + fr.height], S(22),
                                        fill=NEON + (int(110 * b),))
    im.alpha_composite(g.filter(ImageFilter.GaussianBlur(28 * K)), (S(900) - S(50), S(290) - S(50)))
    paste(im, fr, (S(900), S(290) + int((1 - b) * S(40))), b)
    c = appear(t, 1.3, 0.7) * a
    mob = img("build/app_mob.png")
    mh = S(600)
    mob = mob.resize((int(mob.width * mh / mob.height), mh), Image.LANCZOS)
    ph = Image.new("RGBA", (mob.width + S(24), mh + S(24)), (0, 0, 0, 0))
    ImageDraw.Draw(ph).rounded_rectangle([0, 0, ph.width - 1, ph.height - 1], S(44), fill=(20, 8, 12, 255),
                                         outline=(150, 50, 65, 255), width=S(3))
    ph.paste(mob, (S(12), S(12)), rmask(mob.size, S(34)))
    paste(im, ph, (S(1560), S(330) + int((1 - c) * S(80))), c)
    x = S(900)
    for i, s in enumerate(("novaband-id.web.app", "PWA · bisa dipasang di HP", "Bluetooth & USB")):
        x += chip(im, d, (x, S(900)), s, appear(t, 2.4 + i * 0.4) * a, SEMI(24)) + S(14)


TEAM = "Maheswara · Almira · Azra · Dela · Rizkyta · Satriya"


def sc_outro(im, d, t, dur):
    a = clamp((dur - t) / 0.6) if t > dur - 0.6 else 1.0
    glow_text(im, (S(895), S(250)), "Nova-Band", XB(140), WHITE, appear(t, 0.2, 0.7) * a, 26)
    d = ImageDraw.Draw(im)
    text(d, (S(905), S(445)), "Monitor. Analyze. Improve.", SERIF(56), CREAM, appear(t, 0.8) * a)
    spaced(d, (S(905), S(545)), "FASTER · HEALTHIER · STRONGER · TOGETHER", SEMI(26), CYAN, appear(t, 1.6) * a, 6)
    chip(im, d, (S(905), S(620)), "novaband-id.web.app", appear(t, 2.4) * a)
    d = ImageDraw.Draw(im)
    text(d, (S(905), S(760)), TEAM, REG(28), ROSE, appear(t, 3.2) * a)
    text(d, (S(905), S(808)), "SMA Negeri 1 Surakarta  ·  ISIF 2026", SEMI(28), WHITE, appear(t, 3.6) * a)


SCENES = {"intro": sc_intro, "problem": sc_problem, "device": sc_device, "live": sc_live, "alert": sc_alert,
          "ready": sc_ready, "app": sc_app, "outro": sc_outro}


# ---------------------------------------------------------------- captions + chrome
def chunks(text_):
    parts = [p.strip() for p in re.split(r"(?<=[,.!?])\s+", text_) if p.strip()]
    out = []
    for p in parts:
        if out and len(out[-1]) + len(p) < 46:
            out[-1] += " " + p
        else:
            out.append(p)
    return out


def caption(im, text_, t, vo_dur):
    cs = chunks(text_)
    total = sum(len(c) for c in cs)
    u = t - LEAD
    if u < 0 or u > vo_dur + 0.25:
        return
    acc = 0
    cur = cs[-1]
    for c in cs:
        acc += len(c) / total * vo_dur
        if u <= acc:
            cur = c
            break
    f = SEMI(32)
    w = f.getlength(cur) + S(60)
    cx = S(1360)
    x0, y0 = int(cx - w / 2), S(965)
    glass(im, (x0, y0, x0 + w, y0 + S(70)), 1.0, r=35, tint=(14, 6, 10))
    text(ImageDraw.Draw(im), (cx, y0 + S(36)), cur, f, WHITE, 1.0, "mm")


def chrome(im, idx, n, t_total, total):
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([S(60), S(48), S(112), S(100)], S(14), fill=NEON + (255,))
    text(d, (S(86), S(74)), "N", XB(32), WHITE, 1, "mm")
    text(d, (S(128), S(74)), "Nova-Band", XB(32), WHITE, 1, "lm")
    spaced(d, (S(1700), S(62)), "%02d / %02d" % (idx + 1, n), SEMI(22), ROSE, 1, 4)
    d.rounded_rectangle([S(1700), S(98), S(1860), S(102)], S(2), fill=(255, 255, 255, 40))
    d.rounded_rectangle([S(1700), S(98), S(1700) + S(160) * t_total / total, S(102)], S(2), fill=NEON + (255,))


# ---------------------------------------------------------------- audio
def pad_music(seconds, path, sr=44100):
    """A soft synth pad (Am - F - C - G), low in the mix under the voice."""
    n = int(seconds * sr)
    t = np.arange(n) / sr
    chords = [(220.0, 261.63, 329.63), (174.61, 220.0, 261.63), (130.81, 196.0, 261.63), (196.0, 246.94, 293.66)]
    out = np.zeros(n)
    bar = 4.0
    for k in range(int(seconds / bar) + 1):
        s0 = int(k * bar * sr)
        s1 = min(n, int((k + 1) * bar * sr + 1.5 * sr))
        if s0 >= n:
            break
        tt = t[s0:s1] - k * bar
        env = np.minimum(tt / 1.2, 1) * np.exp(-np.maximum(tt - bar, 0) / 0.6)
        for f in chords[k % 4]:
            for h, g in ((1, 1.0), (2, 0.35), (3, 0.12)):
                out[s0:s1] += g * env * np.sin(2 * np.pi * f * h * tt + h) * (1 + 0.003 * np.sin(2 * np.pi * 0.3 * tt))
        out[s0:s1] += 0.5 * env * np.sin(2 * np.pi * chords[k % 4][0] / 2 * tt)
    out *= np.minimum(1, t / 2.0) * np.minimum(1, (seconds - t) / 2.5)
    out = out / np.abs(out).max() * 0.22
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((out * 32767).astype(np.int16).tobytes())


# ---------------------------------------------------------------- main
def main():
    global BG, BLOBS, GRID_Y, GRID
    durs = json.load(open(J("build", "nova_vo", "durations.json")))
    plan = []
    start = 0.0
    for key, clip, line in VO.SCRIPT:
        dur = durs[key] + LEAD + TAIL
        plan.append((key, clip, line, start, dur))
        start += dur - XF / FPS
    total = plan[-1][3] + plan[-1][4]
    BG, BLOBS = build_bg()
    GRID_Y, GRID = build_grid()
    ff = R.find_ffmpeg()
    silent = J("build", "nova_explainer_preview.mp4" if PREVIEW else "nova_explainer_video.mp4")
    step = 4 if PREVIEW else 1
    mux_only = "--mux-only" in sys.argv
    p = subprocess.Popen([ff, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H),
                          "-r", str(FPS / step), "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "19",
                          "-pix_fmt", "yuv420p", J("build", "nova_tmp.mp4") if mux_only else silent],
                         stdin=subprocess.PIPE)

    def frame(si, t):
        key, clip, line, st, dur = plan[si]
        im = background(st + t)
        mascot(im, clip, t)
        d = ImageDraw.Draw(im)
        SCENES[key](im, d, t, dur)
        caption(im, line, t, durs[key])
        chrome(im, si, len(plan), st + t, total)
        return im

    nframes = int(round(total * FPS))
    poster = None
    if "--mux-only" in sys.argv:                     # reuse the silent video, redo audio + poster
        p.stdin.close()
        p.wait()
        nframes = 0
        k = next(k for k, (_, _, _, st, dur) in enumerate(plan) if st <= plan[0][3] + 3.2 < st + dur)
        poster = frame(k, 3.2).convert("RGB")
    for i in range(0, nframes, step):
        gt = i / FPS
        act = [k for k, (_, _, _, st, dur) in enumerate(plan) if st <= gt < st + dur]
        if len(act) == 2:
            a0, a1 = act
            u = (gt - plan[a1][3]) / (XF / FPS)
            im = Image.blend(frame(a0, gt - plan[a0][3]).convert("RGB"), frame(a1, gt - plan[a1][3]).convert("RGB"), u)
        else:
            k = act[0] if act else len(plan) - 1
            im = frame(k, gt - plan[k][3]).convert("RGB")
        if poster is None and gt >= plan[0][3] + 3.2:
            poster = im
        p.stdin.write(im.tobytes())
        if i % (FPS * 10) < step:
            print("  %5.1f / %.1f s" % (gt, total), flush=True)
    p.stdin.close()
    p.wait()
    if PREVIEW:
        print("wrote", silent)
        return

    # audio: pad + each narration clip at its scene start + LEAD
    pad = J("build", "nova_vo", "pad.wav")
    pad_music(total, pad)
    inputs, filt = ["-i", pad], []
    for k, (key, *_r, st, dur) in enumerate(plan):
        inputs += ["-i", J("build", "nova_vo", key + ".mp3")]
        ms = int((st + LEAD) * 1000)
        filt.append("[%d:a]aresample=44100,adelay=%d|%d,volume=1.6[v%d]" % (k + 2, ms, ms, k))   # 0 video, 1 pad
    filt.append("[1:a]volume=0.55[pad]")
    filt.append("[pad]" + "".join("[v%d]" % k for k in range(len(plan))) +
                "amix=inputs=%d:normalize=0:duration=first,alimiter=limit=0.95[a]" % (len(plan) + 1))
    out = J("assets", "nova-explainer.mp4")
    subprocess.run([ff, "-y", "-loglevel", "warning", "-i", silent] + inputs +
                   ["-filter_complex", ";".join(filt), "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac",
                    "-b:a", "160k", "-shortest", "-movflags", "+faststart", out], check=True)
    poster.save(J("assets", "nova-explainer-poster.jpg"), quality=86)
    subprocess.run([ff, "-y", "-loglevel", "error", "-i", out, "-c:v", "libvpx-vp9", "-b:v", "0", "-crf", "34",
                    "-row-mt", "1", "-deadline", "good", "-cpu-used", "2", "-c:a", "libopus", "-b:a", "96k",
                    J("assets", "nova-explainer.webm")], check=True)
    print("wrote", out, "%.1f s" % total)


if __name__ == "__main__":
    main()
