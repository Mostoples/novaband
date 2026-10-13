"""
Nova-Band portrait reel (1080 x 1920, 2:30, loops seamlessly), all in English.

  00 The problem   real community footage + animated pseudo-3D charts (sources on screen)
  01 Use cases     Blender use-case renders (build/usecases)
  02 Partners      documentation footage (dokumentasi/)
  03 The app       full-screen phone, English app tour (tools/record-app-en.py)
  04 Profile       field footage (dokumentasi/ADEGAN), team, end card

Nova (Blender clips in build/mascot_anim) presents every part; his lines come
from tools/portrait-vo.py (edge-tts, word timings) and appear word by word in a
speech bubble. Calm-but-upbeat corporate music is synthesised here and is
exactly periodic, ducked under the voice.

    python tools/portrait-vo.py          # narration
    python tools/record-app-en.py        # app tour
    python tools/make-portrait-reel.py   # -> build/portrait/NovaBand_Portrait_Reel.mp4   (--preview: every 2nd frame, half size)
"""
import glob
import importlib.util
import json
import math
import os
import subprocess
import sys
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
J = lambda *p: os.path.join(ROOT, *p)
spec = importlib.util.spec_from_file_location("reel", J("tools", "make-showreel2.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
FF = R.find_ffmpeg()
PREVIEW = "--preview" in sys.argv
W, H, FPS, SR = 1080, 1920, 25, 44100
TOTAL = 150.0
N = int(TOTAL * FPS)
XF = 10                                            # media cross-fade, frames
from PIL import ImageFont  # noqa: E402
FONT = lambda name, size: ImageFont.truetype(J("build", "fonts", name), int(size))
XB = lambda s: FONT("Poppins-ExtraBold.ttf", s)
BOLD = lambda s: FONT("Poppins-Bold.ttf", s)
SEMI = lambda s: FONT("Poppins-SemiBold.ttf", s)
REG = lambda s: FONT("Poppins-Regular.ttf", s)
SERIF = lambda s: FONT("Fraunces-Italic.ttf", s)
WINE, RED, CREAM, MUTED, WHITE, GOLD = (109, 15, 34), (255, 79, 99), (243, 227, 211), (215, 200, 205), (255, 255, 255), (255, 200, 90)
# white theme: dark ink on light surfaces (charts, header, bubble, end card)
INK, INK2, GREY, REDD = (34, 12, 20), (92, 58, 68), (128, 108, 114), (196, 30, 58)
clamp = lambda x, a=0.0, b=1.0: max(a, min(b, x))
ease = lambda x: 1 - (1 - clamp(x)) ** 3
sm = lambda x: clamp(x) ** 2 * (3 - 2 * clamp(x))

DOC = J("dokumentasi")
KL = lambda n: os.path.join(DOC, "KOMUNITAS LARI SURAKARTA", n)
AD = lambda s: os.path.join(DOC, "ADEGAN", "WhatsApp Video 2026-10-10 at %s.mp4" % s)
BX, BY, BW, BH = 40, 190, 1000, 1200              # media box

SEGS = [(0.0, "00", "THE PROBLEM"), (34.0, "01", "USE CASES"), (62.0, "02", "PARTNERS"), (88.0, "03", "THE APP"), (122.0, "04", "PROFILE")]
VO = json.load(open(J("build", "portrait_vo", "words.json")))


# ------------------------------------------------------------------ narration schedule
def schedule():
    out, t = [], None
    for key, m in VO.items():
        seg = m["seg"]
        s0 = SEGS[seg][0]
        if t is None or t < s0:
            t = s0 + (2.0 if seg == 3 else 0.8)
        if key == "s3c":
            t = max(t, 88.0 + 2.0 + 361 / 25 - 0.4)        # start on the app's alert screen
        out.append({"key": key, "t0": t, "t1": t + m["dur"], **m})
        t += m["dur"] + 0.6
    return out


LINES = schedule()


# ------------------------------------------------------------------ media sources
def cover_vf(rot=False, w=BW, h=BH, sharpen=False):
    r = "transpose=2," if rot else ""
    us = ",unsharp=5:5:0.6:5:5:0" if sharpen else ""
    return "%sscale=%d:%d:flags=lanczos:force_original_aspect_ratio=increase,crop=%d:%d%s,eq=contrast=1.06:saturation=1.08,setsar=1,fps=%d" % (
        r, w, h, w, h, us, FPS)


def video(path, start, dur, vf=None, grade=None):
    n = int(round(dur * FPS))
    vf = vf or cover_vf(sharpen="ADEGAN" in path)
    p = subprocess.Popen([FF, "-v", "error", "-ss", "%.3f" % start, "-i", path, "-t", "%.3f" % (dur + 0.6), "-vf", vf,
                          "-an", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    last = None
    for _ in range(n):
        b = p.stdout.read(BW * BH * 3)
        if len(b) == BW * BH * 3:
            last = np.frombuffer(b, np.uint8).reshape(BH, BW, 3)
        yield grade(last) if grade else last
    p.stdout.close(); p.kill()


def photo(path, dur, zoom_in=True, grade=None):
    im = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    base = ImageOps.fit(im, (int(BW * 1.12), int(BH * 1.12)), Image.LANCZOS)
    n = int(round(dur * FPS))
    for f in range(n):
        p = f / max(1, n - 1)
        z = 1 + 0.1 * p if zoom_in else 1.1 - 0.1 * p
        cw, ch = base.width / z, base.height / z
        x, y = (base.width - cw) / 2, (base.height - ch) * 0.45
        a = np.asarray(base.resize((BW, BH), Image.BILINEAR, box=(x, y, x + cw, y + ch)))
        yield grade(a) if grade else a


def frames(folder, start, n, step=1.0):
    fs = sorted(glob.glob(os.path.join(folder, "f_*.jpg")))
    for i in range(n):
        k = min(len(fs) - 1, int(start + i * step))
        im = Image.open(fs[k]).convert("RGB")
        yield np.asarray(ImageOps.fit(im, (BW, BH), Image.LANCZOS, centering=(0.5, 0.5)))


def dark_red(a):                                    # urgency grade: desaturated, red-tinted, darker
    g = a.astype(np.float32).mean(axis=2, keepdims=True)
    o = g * np.array([1.05, 0.55, 0.6]) * 0.62 + a * 0.18
    return np.clip(o, 0, 255).astype(np.uint8)


# ------------------------------------------------------------------ chart scenes (pseudo-3D)
_STAGE = None
def stage_bg(t):
    """Dark wine stage with a receding perspective grid floor."""
    global _STAGE
    if _STAGE is None:
        _STAGE = Image.new("RGB", (BW, BH), (255, 255, 255))
        d0 = ImageDraw.Draw(_STAGE)
        for y in range(BH):
            k = y / BH
            g = max(0, 1 - abs(k - 0.45) * 1.6)
            d0.line([(0, y), (BW, y)], fill=(255, int(250 - 14 * g), int(251 - 12 * g)))
    im = _STAGE.copy()
    d = ImageDraw.Draw(im, "RGBA")
    hz = BH * 0.62
    for i in range(-12, 13):
        d.line([(BW / 2 + i * 26, hz), (BW / 2 + i * 260, BH)], fill=(255, 79, 99, 45), width=2)
    off = (t * 60) % 60
    for k in range(14):
        yy = hz + (BH - hz) * ((k * 60 + off) / 840) ** 1.8
        d.line([(0, yy), (BW, yy)], fill=(255, 79, 99, 38), width=2)
    return im


def label(d, xy, s, f, fill, a=1.0, anchor="la"):
    if a > 0:
        d.text(xy, s, font=f, fill=tuple(fill) + (int(255 * clamp(a)),), anchor=anchor)


def source(d, s, a):
    label(d, (30, BH - 34), "Source: " + s, REG(24), GREY, a * 0.9, "lm")


def scene_pie(t, dur):
    """19.8 M CVD deaths = about 1 in 3 deaths worldwide (WHO)."""
    im = stage_bg(t); d = ImageDraw.Draw(im, "RGBA")
    cx, cy, rx, ry, th = BW / 2, 640, 330, 150, 70
    frac = 0.32 * ease((t - 0.6) / 1.8)
    lift = 28 * ease((t - 2.4) / 0.6)
    for k in range(th, -1, -3):                     # extruded disc
        d.ellipse((cx - rx, cy - ry + k, cx + rx, cy + ry + k), fill=(196, 184, 188, 255) if k else (222, 212, 215, 255))
    d.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=(236, 228, 230, 255))
    if frac > 0:
        a0, a1 = -90, -90 + 360 * frac
        mid = math.radians((a0 + a1) / 2)
        ox, oy = math.cos(mid) * lift, math.sin(mid) * lift * 0.45 - lift * 0.3
        for k in range(th, -1, -3):
            d.pieslice((cx - rx + ox, cy - ry + k + oy, cx + rx + ox, cy + ry + k + oy), a0, a1, fill=(150, 18, 40, 255) if k else (255, 79, 99, 255))
        d.pieslice((cx - rx + ox, cy - ry + oy, cx + rx + ox, cy + ry + oy), a0, a1, fill=(255, 79, 99, 255))
    n = 19.8 * ease((t - 0.3) / 2.2)
    label(d, (BW / 2, 170), "%.1f million" % n, XB(104), INK, ease(t / 0.6), "mm")
    label(d, (BW / 2, 270), "deaths from cardiovascular disease in 2022", SEMI(34), INK2, ease((t - 0.4) / 0.6), "mm")
    label(d, (BW / 2, 960), "~1 in 3 deaths worldwide", XB(58), REDD, ease((t - 2.6) / 0.6), "mm")
    label(d, (BW / 2, 1040), "The world's No. 1 cause of death", SEMI(34), INK, ease((t - 3.0) / 0.6), "mm")
    source(d, "World Health Organization, CVD fact sheet", ease((t - 1) / 0.6))
    return np.asarray(im)


def prism(d, x, base, w, hgt, depth, col):
    """Isometric bar: front, side and top faces."""
    dx, dy = depth * 0.8, -depth * 0.5
    top = base - hgt
    dark = tuple(int(c * 0.62) for c in col); light = tuple(min(255, int(c * 1.25)) for c in col)
    d.polygon([(x, top), (x + w, top), (x + w, base), (x, base)], fill=col + (255,))
    d.polygon([(x + w, top), (x + w + dx, top + dy), (x + w + dx, base + dy), (x + w, base)], fill=dark + (255,))
    d.polygon([(x, top), (x + dx, top + dy), (x + w + dx, top + dy), (x + w, top)], fill=light + (255,))


def scene_bars_id(t, dur):
    """Indonesia CVD deaths 292k (1990) -> 659k (2019), GBD."""
    im = stage_bg(t); d = ImageDraw.Draw(im, "RGBA")
    base, scale = 1000, 0.72
    vals = [(1990, 292, (190, 150, 160)), (2019, 659, (255, 79, 99))]
    for i, (yr, v, col) in enumerate(vals):
        g = ease((t - 0.4 - 0.7 * i) / 1.4)
        hgt = v * scale * g
        x = 230 + i * 330
        prism(d, x, base, 200, hgt, 90, col)
        label(d, (x + 100, base + 50), str(yr), BOLD(40), INK, ease((t - 0.3) / 0.5), "mm")
        label(d, (x + 100, base - hgt - 100), "%dk" % round(v * g), XB(56), INK, g, "mm")
    label(d, (BW / 2, 150), "INDONESIA", SEMI(32), GREY, ease(t / 0.5), "mm")
    label(d, (BW / 2, 225), "Cardiovascular deaths per year", BOLD(46), INK, ease((t - 0.2) / 0.5), "mm")
    a = ease((t - 2.4) / 0.5)
    d.rounded_rectangle((BW / 2 - 170, 290, BW / 2 + 170, 380), 45, fill=(255, 79, 99, int(230 * a)))
    label(d, (BW / 2, 335), "× 2.3 in 30 years", XB(40), INK, a, "mm")
    source(d, "Global Burden of Disease (IHME), via PMC10723707", ease((t - 1) / 0.6))
    return np.asarray(im)


def scene_overtrain(t, dur):
    """Overtraining / non-functional overreaching: ~60 % elite, ~1 in 3 recreational (Morgan 1987)."""
    im = stage_bg(t); d = ImageDraw.Draw(im, "RGBA")
    label(d, (BW / 2, 160), "Pushing too hard", XB(64), INK, ease(t / 0.5), "mm")
    label(d, (BW / 2, 240), "runners who overtrain at some point", SEMI(34), INK2, ease((t - 0.3) / 0.5), "mm")
    rows = [("Elite runners", 60, (255, 79, 99)), ("Recreational runners", 33, (255, 170, 120))]
    for i, (name, pct, col) in enumerate(rows):
        y = 520 + i * 330
        g = ease((t - 0.6 - 0.5 * i) / 1.3)
        label(d, (90, y - 150), name, BOLD(42), INK, ease((t - 0.4 - 0.5 * i) / 0.5))
        prism(d, 90, y + 70, 760 * pct / 100 * g + 2, 110, 60, col)        # lying bar: hgt = thickness
        label(d, (110 + 760 * pct / 100 * g + 70, y + 15), "~%d%%" % round(pct * g), XB(60), INK, g, "lm")
    source(d, "Morgan et al., Int J Sports Med 1987", ease((t - 1) / 0.6))
    return np.asarray(im)


def ecg(d, t, x0, y0, w, h, stress):
    """Scrolling ECG trace; beats get faster and irregular with stress (0..1)."""
    pts = []
    for i in range(0, int(w), 3):
        xx = (i / w) * 6 + t * (1.2 + 2.2 * stress)
        ph = xx % 1.0
        jitter = math.sin(xx * 37) * 0.15 * stress
        v = 0
        if 0.40 < ph < 0.44: v = -0.15
        elif 0.44 < ph < 0.47: v = 1.0 + 0.6 * stress * (1 + math.sin(xx * 13))
        elif 0.47 < ph < 0.50: v = -0.45
        elif 0.62 < ph < 0.72: v = 0.22 * math.sin((ph - 0.62) / 0.1 * math.pi)
        pts.append((x0 + i, y0 - (v + jitter) * h))
    col = (int(120 + 135 * stress), int(255 - 180 * stress), int(170 - 90 * stress), 255)
    d.line(pts, fill=col, width=7, joint="curve")


def scene_race(t, dur, bg):
    """Race footage + ECG going wild + NEJM figures."""
    im = Image.fromarray(bg).convert("RGB"); d = ImageDraw.Draw(im, "RGBA")
    stress = clamp((t - 1.0) / 4.5)
    d.rectangle((0, 380, BW, 700), fill=(0, 0, 0, 120))
    ecg(d, t, 0, 560, BW, 120, stress)
    label(d, (BW / 2, 120), "Sudden cardiac arrest in races", BOLD(48), WHITE, ease(t / 0.5), "mm")
    a = ease((t - 2.2) / 0.6)
    d.rounded_rectangle((60, 780, BW - 60, 1110), 36, fill=(20, 4, 10, int(215 * a)))
    label(d, (BW / 2, 860), "59 cardiac arrests", XB(70), RED, a, "mm")
    label(d, (BW / 2, 945), "among 10.9 million marathon & half-marathon runners", SEMI(30), WHITE, a, "mm")
    label(d, (BW / 2, 1010), "mostly hidden heart disease · mostly men", REG(30), CREAM, ease((t - 3.0) / 0.6), "mm")
    label(d, (BW / 2, 1065), "rare — but often preventable with monitoring", BOLD(32), GOLD, ease((t - 3.8) / 0.6), "mm")
    source(d, "Kim et al., New England Journal of Medicine 2012 (RACER)", ease((t - 2.4) / 0.6))
    return np.asarray(im)


def scene_fomo(t, dur, bg):
    """Crowd footage with FOMO chips floating up."""
    im = Image.fromarray(bg).convert("RGB"); d = ImageDraw.Draw(im, "RGBA")
    chips = ["Finisher medal!", "#RunChallenge", "New PR or bust", "3 races this month", "Don't miss out!"]
    for i, s in enumerate(chips):
        k = (t - 0.4 - i * 0.7)
        if k < 0: continue
        y = BH - 160 - k * 120 - i * 10
        if y < 120: continue
        a = ease(k / 0.4) * clamp((y - 120) / 160)
        x = 80 + (i % 2) * 380 + 40 * math.sin(k * 1.3 + i)
        f = BOLD(38)
        tw = d.textlength(s, font=f) if hasattr(d, "textlength") else 380
        d.rounded_rectangle((x, y, x + tw + 50, y + 74), 37, fill=(255, 255, 255, int(220 * a)))
        d.text((x + 25, y + 37), s, font=f, fill=(40, 8, 18, int(255 * a)), anchor="lm")
    label(d, (BW / 2, 110), "FOMO", XB(110), RED, ease(t / 0.4) * clamp((dur - t) / 0.4), "mm")
    return np.asarray(im)


def scene_product(t, dur):
    im = stage_bg(t); d = ImageDraw.Draw(im, "RGBA")
    p = Image.open(J("assets", "3d", "device-hero.webp")).convert("RGBA") if os.path.exists(J("assets", "3d", "device-hero.webp")) \
        else Image.open(J("assets", "img", "product-front.webp")).convert("RGBA")
    s = 0.85 + 0.15 * ease(t / 1.2)
    p.thumbnail((int(820 * s), int(820 * s)))
    glow = Image.new("RGBA", (BW, BH), (0, 0, 0, 0)); gd = ImageDraw.Draw(glow)
    gd.ellipse((BW / 2 - 380, 260, BW / 2 + 380, 1020), fill=(255, 79, 99, int(70 * ease(t / 0.8))))
    im.paste(glow.filter(ImageFilter.GaussianBlur(80)), (0, 0), glow.filter(ImageFilter.GaussianBlur(80)))
    a = ease(t / 0.8)
    pa = p.copy(); pa.putalpha(pa.split()[3].point(lambda v: int(v * a)))
    im.paste(pa, (int(BW / 2 - p.width / 2), int(640 - p.height / 2)), pa)
    label(d, (BW / 2, 1100), "Nova-Band", XB(78), INK, ease((t - 0.6) / 0.6), "mm")
    return np.asarray(im)


def chart(fn, dur):
    n = int(round(dur * FPS))
    for f in range(n):
        yield fn(f / FPS, dur)


def over(fn, gen, dur):
    for f, bg in enumerate(gen):
        yield fn(f / FPS, dur, bg)


# ------------------------------------------------------------------ shot list (media box)
def L(key):
    return next(l for l in LINES if l["key"] == key)


def shots():
    u = {k: L(k) for k in ("u1", "u2", "u3", "u4", "u5")}
    seg = lambda a, b: b - a
    s = []
    # 00 problem: cut points follow the narration
    t1 = u["u1"]["t0"] + 4.2
    s += [("fomo", t1, lambda d: over(scene_fomo, video(KL("WhatsApp Video 2026-10-08 at 06.57.04.mp4"), 0, d, grade=dark_red), d)),
          ("overtrain", u["u2"]["t0"] - 0.3 - t1, lambda d: chart(scene_overtrain, d)),
          ("pie", u["u3"]["t0"] - (u["u2"]["t0"] - 0.3), lambda d: chart(scene_pie, d)),
          ("bars", u["u4"]["t0"] - u["u3"]["t0"], lambda d: chart(scene_bars_id, d)),
          ("race", u["u5"]["t0"] - u["u4"]["t0"], lambda d: over(scene_race, video(KL("WhatsApp Video 2026-09-30 at 20.33.42.mp4"), 1.0, d, grade=dark_red), d)),
          ("product", 34.0 - u["u5"]["t0"], lambda d: chart(scene_product, d))]
    # 01 use cases: six Blender scenes
    names = [("park_run", "Morning run"), ("treadmill", "Treadmill"), ("pushups", "Strength training"),
             ("coach", "Early warning"), ("recovery", "Recovery"), ("walk", "Everyday activity")]
    for k, (f, lab) in enumerate(names):
        s.append(("uc:" + lab, 28.0 / 6, lambda d, f=f: frames(J("build", "usecases", f), 0, int(round(d * FPS)), 0.9)))
    # 02 partners
    P = [(KL("WhatsApp Video 2026-09-30 at 20.33.42.mp4"), 0.8, "video", "Field test · Surakarta running community"),
         (KL("WhatsApp Video 2026-09-30 at 20.33.41.mp4"), 0.5, "video", "Coaches monitor runners from afar"),
         (os.path.join(DOC, "PROFESOR PRINGGO UNS", "IMG_20261007_080939675_HDR.jpg"), 0, "photo", "Prof. Pringgo · Universitas Sebelas Maret"),
         (os.path.join(DOC, "PROFESSOR NURYANI UNS FISIKA", "WhatsApp Image 2026-10-09 at 15.51.48.jpeg"), 0, "photo", "Prof. Nuryani · Physics, UNS"),
         (os.path.join(DOC, "Dokter Yasa Moewardi", "WhatsApp Image 2026-10-09 at 04.24.32 (1).jpeg"), 0, "photo", "dr. Yasa · Dr. Moewardi Hospital"),
         (os.path.join(DOC, "DINAS KESEHATAN SURAKARTA", "WhatsApp Image 2026-10-08 at 19.16.18.jpeg"), 0, "photo", "Surakarta Health Office"),
         (os.path.join(DOC, "KLINIK UTAMA HAUNAA", "WhatsApp Image 2026-10-09 at 04.38.22.jpeg"), 0, "photo", "Haunaa Clinic")]
    d2 = 26.0 / len(P)
    for k, (p, st, kind, lab) in enumerate(P):
        s.append(("pt:" + lab, d2, (lambda d, p=p, st=st: video(p, st, d)) if kind == "video" else (lambda d, p=p, k=k: photo(p, d, k % 2 == 0))))
    # 03 app: handled by the phone layer; the media box shows a calm backdrop
    s.append(("app", 34.0, lambda d: chart(lambda t, dd: np.asarray(stage_bg(t)), d)))
    # 04 profile
    Q = [(AD("12.26.24"), 0.2, False, "Built for runners"), (AD("12.25.34 (2)"), 3.8, False, "Worn on the upper arm"),
         (AD("12.26.23"), 0.3, False, "A live screen on the band"), (AD("12.25.34"), 4.5, False, "Stable while you move"),
         (AD("12.25.33"), 5.0, True, "Heart rate, pace, cadence")]
    for p, st, rot, lab in Q:
        s.append(("pf:" + lab, 3.6, lambda d, p=p, st=st, rot=rot: video(p, st, d, vf=cover_vf(rot, sharpen=True))))
    s.append(("pf:Team", 4.0, lambda d: photo(os.path.join(DOC, "SMA Negeri 1 Surakarta", "WhatsApp Image 2026-10-09 at 04.36.23.jpeg"), d)))
    s.append(("end", 28.0 - 3.6 * 5 - 4.0, lambda d: chart(scene_end, d)))
    return s


def scene_end(t, dur):
    im = stage_bg(t); d = ImageDraw.Draw(im, "RGBA")
    a = ease(t / 0.6)
    f = XB(118); tw = d.textlength("Nova-Band", font=f); x = BW / 2 - tw / 2
    label(d, (x, 420), "Nova", f, INK, a, "lm")
    label(d, (x + d.textlength("Nova", font=f), 420), "-", f, RED, a, "lm")
    label(d, (x + d.textlength("Nova-", font=f), 420), "Band", f, INK, a, "lm")
    label(d, (BW / 2, 540), "Monitor. Analyze. Improve.", SERIF(56), INK2, ease((t - 0.5) / 0.6), "mm")
    label(d, (BW / 2, 690), "Student research team · SMA Negeri 1 Surakarta", SEMI(32), INK, ease((t - 1.0) / 0.6), "mm")
    label(d, (BW / 2, 740), "ISIF 2026", SEMI(30), GREY, ease((t - 1.2) / 0.6), "mm")
    b = ease((t - 1.5) / 0.6)
    d.rounded_rectangle((BW / 2 - 300, 820, BW / 2 + 300, 920), 50, fill=(255, 79, 99, int(255 * b)))
    label(d, (BW / 2, 870), "novaband-id.web.app", BOLD(42), INK, b, "mm")
    return np.asarray(im)


# ------------------------------------------------------------------ persistent layers
def rounded_mask(w, h, r):
    m = Image.new("L", (w, h), 0); ImageDraw.Draw(m).rounded_rectangle((0, 0, w - 1, h - 1), r, fill=255); return m


BOXMASK = rounded_mask(BW, BH, 44)


def background():
    g = np.zeros((H, W, 3), np.float32)
    yy = np.linspace(0, 1, H)[:, None]
    xx = np.linspace(0, 1, W)[None, :]
    r = np.sqrt((xx - 0.5) ** 2 + (yy - 0.35) ** 2)
    aura = np.clip(1 - r * 1.5, 0, 1)
    g[..., 0] = 252 + 3 * aura
    g[..., 1] = 249 - 22 * aura
    g[..., 2] = 250 - 18 * aura
    return Image.fromarray(g.astype(np.uint8))


BG = background()
SHADOW = Image.new("RGBA", (BW + 120, BH + 120), (0, 0, 0, 0))
ImageDraw.Draw(SHADOW).rounded_rectangle((60, 70, BW + 60, BH + 70), 44, fill=(90, 20, 40, 70))
SHADOW = SHADOW.filter(ImageFilter.GaussianBlur(24))

CLIPS = {}
def clip(name):
    if name not in CLIPS:
        fs = sorted(glob.glob(J("build", "mascot_anim", name, "f_*.png")))
        CLIPS[name] = fs
    return CLIPS[name]


NOVA_CACHE = {}
def nova_frame(name, i, h):
    fs = clip(name)
    path = fs[i % len(fs)]
    key = (path, h)
    if key not in NOVA_CACHE:
        if len(NOVA_CACHE) > 600: NOVA_CACHE.clear()
        im = Image.open(path).convert("RGBA")
        bb = im.getbbox() or (0, 0, im.width, im.height)
        im = im.resize((int(im.width * h / im.height), h), Image.LANCZOS)
        NOVA_CACHE[key] = im
    return NOVA_CACHE[key]


def line_at(t):
    hit = None
    for l in LINES:                                    # the latest line that has started and is still on screen
        if l["t0"] - 0.05 <= t <= l["t1"] + 1.2:
            hit = l
    return hit


def wrap(d, words, f, maxw):
    lines, cur = [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if d.textlength(test, font=f) > maxw and cur:
            lines.append(cur); cur = w
        else:
            cur = test
    if cur: lines.append(cur)
    return lines


def seg_at(t):
    k = 0
    for i, (s0, _, _) in enumerate(SEGS):
        if t >= s0: k = i
    return k


def overlay(im, t):
    d = ImageDraw.Draw(im, "RGBA")
    seg = seg_at(t)
    # header
    f = XB(40); x = 50
    d.text((x, 100), "Nova", font=f, fill=INK, anchor="lm")
    d.text((x + d.textlength("Nova", font=f), 100), "-", font=f, fill=RED, anchor="lm")
    d.text((x + d.textlength("Nova-", font=f), 100), "Band", font=f, fill=INK, anchor="lm")
    num, name = SEGS[seg][1], SEGS[seg][2]
    tag = num + "  " + name
    tf = SEMI(28); tw = d.textlength(tag, font=tf)
    d.rounded_rectangle((W - 50 - tw - 44, 72, W - 50, 128), 28, fill=(255, 79, 99, 235))
    d.text((W - 50 - tw / 2 - 22, 100), tag, font=tf, fill=WHITE, anchor="mm")
    for i in range(5):                                  # progress
        x0 = 50 + i * (W - 100 + 12) / 5
        x1 = x0 + (W - 100 + 12) / 5 - 12
        d.rounded_rectangle((x0, 150, x1, 157), 4, fill=(109, 15, 34, 40))
        s0 = SEGS[i][0]; s1 = SEGS[i + 1][0] if i < 4 else TOTAL
        k = clamp((t - s0) / (s1 - s0))
        if k > 0: d.rounded_rectangle((x0, 150, x0 + (x1 - x0) * k, 157), 4, fill=RED + (255,))
    # Nova presenter + speech bubble
    l = line_at(t)
    name_clip = l["clip"] if l and t <= l["t1"] else "idle"
    fi = int(t * 24)
    nh = 470 if seg == 3 else 560
    nv = nova_frame(name_clip, fi, nh)
    bob = int(6 * math.sin(t * 3.1))
    nx, ny = -40, H - nh + 30 + bob
    im.paste(nv, (nx, ny), nv)
    if l:
        k_in = ease((t - l["t0"] + 0.05) / 0.25)
        k_out = clamp((l["t1"] + 1.2 - t) / 0.3)
        a = k_in * k_out
        spoken = sum(1 for w in l["words"] if l["t0"] + w[0] <= t) if l["words"] else 99
        cap = l["caption"].split()
        total_spoken = max(1, len(l["words"]))
        show = len(cap) if t > l["t1"] - 0.2 else max(1, int(round(len(cap) * spoken / total_spoken)))
        f = SEMI(42)
        bx0, bx1 = 400, W - 36
        lines = wrap(d, cap, f, bx1 - bx0 - 70)
        bh = 70 + len(lines) * 56
        by1 = H - 60; by0 = by1 - bh
        if a > 0:
            sh = Image.new("RGBA", (bx1 - bx0 + 80, by1 - by0 + 80), (0, 0, 0, 0))
            ImageDraw.Draw(sh).rounded_rectangle((40, 50, bx1 - bx0 + 40, by1 - by0 + 50), 38, fill=(110, 20, 40, int(70 * a)))
            sh = sh.filter(ImageFilter.GaussianBlur(16)); im.paste(sh, (bx0 - 40, by0 - 40), sh)
            d.rounded_rectangle((bx0, by0, bx1, by1), 38, fill=(255, 255, 255, int(250 * a)), outline=(255, 79, 99, int(200 * a)), width=3)
            d.polygon([(bx0 + 4, by1 - 90), (bx0 - 38, by1 - 50), (bx0 + 4, by1 - 50)], fill=(255, 255, 255, int(245 * a)))
            shown = 0
            for li, ln in enumerate(lines):
                ws = ln.split()
                for wi, w in enumerate(ws):
                    pre = " ".join(ws[:wi]) + (" " if wi else "")
                    xx = bx0 + 35 + d.textlength(pre, font=f)
                    vis = shown < show
                    col = (40, 8, 18) if vis else (40, 8, 18)
                    d.text((xx, by0 + 40 + li * 56), w, font=f, fill=col + (int(255 * a * (1 if vis else 0.18)),), anchor="la")
                    shown += 1
    return im


# ------------------------------------------------------------------ the phone (segment 03)
APP = J("build", "app_rec_en")
TAPS = json.load(open(os.path.join(APP, "taps.json")))
APP_T0 = 88.0 + 2.0
PH_H = 1560
PH_W = int(PH_H * 1080 / 2338)
PH_X, PH_Y = (W - PH_W) // 2 + 70, 190
PHMASK = rounded_mask(PH_W, PH_H, 70)


def phone(im, t):
    if not (88.0 <= t < 122.0):
        return
    k_in = ease((t - 88.0) / 0.9); k_out = clamp((122.0 - t) / 0.5)
    i = int(clamp((t - APP_T0) * FPS, 0, TAPS["frames"] - 1))
    scr = Image.open(os.path.join(APP, "v_%05d.jpg" % i)).convert("RGB").resize((PH_W, PH_H), Image.BILINEAR)
    d = ImageDraw.Draw(scr, "RGBA")
    for tp in TAPS["taps"]:                              # finger ripples / swipe dots
        dt = i - tp["f"]
        if tp["type"] == "tap" and 0 <= dt < 14:
            r = 20 + dt * 4
            cx, cy = tp["x"] * PH_W, tp["y"] * PH_H
            d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(255, 255, 255, int(220 * (1 - dt / 14))), width=5)
            d.ellipse((cx - 18, cy - 18, cx + 18, cy + 18), fill=(255, 255, 255, int(160 * (1 - dt / 14))))
        if tp["type"] == "swipe" and 0 <= dt < tp["len"]:
            k = dt / tp["len"]
            cy = PH_H * (0.72 - 0.4 * k) if tp["dir"] > 0 else PH_H * (0.32 + 0.4 * k)
            d.ellipse((PH_W * 0.62 - 26, cy - 26, PH_W * 0.62 + 26, cy + 26), fill=(255, 255, 255, 150))
    y = PH_Y + int((1 - k_in) * 300)
    bez = Image.new("RGBA", (PH_W + 36, PH_H + 36), (0, 0, 0, 0))
    ImageDraw.Draw(bez).rounded_rectangle((0, 0, PH_W + 35, PH_H + 35), 86, fill=(18, 18, 22, 255), outline=(90, 90, 100, 255), width=3)
    sh = Image.new("RGBA", (PH_W + 160, PH_H + 160), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((60, 80, PH_W + 100, PH_H + 110), 90, fill=(0, 0, 0, 170))
    sh = sh.filter(ImageFilter.GaussianBlur(30))
    a = k_in * k_out
    for lay, pos in ((sh, (PH_X - 80, y - 60)), (bez, (PH_X - 18, y - 18))):
        L2 = lay.copy(); L2.putalpha(L2.split()[3].point(lambda v: int(v * a)))
        im.paste(L2, pos, L2)
    m = PHMASK.point(lambda v: int(v * a))
    im.paste(scr, (PH_X, y), m)


# ------------------------------------------------------------------ music (exactly periodic over TOTAL)
def music():
    n = int(TOTAL * SR)
    pad = int(6 * SR)
    out = np.zeros(n + pad)
    t = np.arange(n + pad) / SR
    bpm = 96; beat = 60 / bpm; bar = 4 * beat                      # 60 bars = 150 s
    prog = [(146.83, (293.66, 369.99, 440.00, 587.33)),            # D
            (110.00, (277.18, 329.63, 440.00, 554.37)),            # A
            (123.47, (293.66, 369.99, 493.88, 587.33)),            # Bm
            (98.00, (293.66, 392.00, 493.88, 587.33))]             # G
    rng = np.random.default_rng(5)
    nb = int(round(TOTAL / bar))
    def add(t0, sig):
        i0 = int(t0 * SR); m = min(len(sig), len(out) - i0)
        if m > 0: out[i0:i0 + m] += sig[:m]
    for b in range(nb):
        root, ch = prog[b % 4]
        t0 = b * bar
        u = np.arange(int((bar + 1.5) * SR)) / SR
        env = np.clip(u / 0.6, 0, 1) * np.exp(-np.clip(u - bar, 0, None) / 0.5)
        pad_sig = sum((0.11 * np.sin(2 * np.pi * f * u) + 0.03 * np.sin(4 * np.pi * f * u * 1.002)) for f in ch[:3])
        add(t0, pad_sig * env)
        # piano arpeggio, 8ths
        arp = [ch[0], ch[1], ch[2], ch[3], ch[2], ch[1], ch[2], ch[3]]
        for k in range(8):
            v = np.arange(int(1.2 * SR)) / SR
            f = arp[k]
            tone = (np.sin(2 * np.pi * f * v) + 0.35 * np.sin(4 * np.pi * f * v) + 0.12 * np.sin(6 * np.pi * f * v)) * np.exp(-v / 0.45)
            add(t0 + k * beat / 2, 0.075 * tone * (1.0 if k % 2 == 0 else 0.75))
        sec = (b // 15) % 4                                         # energy follows the parts
        if b % 15 >= 1:
            for k in range(4):                                     # bass
                v = np.arange(int(0.5 * SR)) / SR
                add(t0 + k * beat, 0.22 * np.sin(2 * np.pi * root * v) * np.exp(-v / 0.25))
        if b % 15 >= 2:
            for k in range(4):                                     # soft kick on every beat
                v = np.arange(int(0.25 * SR)) / SR
                add(t0 + k * beat, 0.32 * np.sin(2 * np.pi * (50 + 70 * np.exp(-v / 0.03)) * v) * np.exp(-v / 0.09))
            for k in (1, 3):                                       # clap
                v = np.arange(int(0.18 * SR)) / SR
                add(t0 + k * beat, 0.07 * rng.standard_normal(len(v)) * np.exp(-v / 0.05))
            for k in range(8):                                     # shaker
                v = np.arange(int(0.06 * SR)) / SR
                add(t0 + k * beat / 2 + beat / 4, 0.02 * rng.standard_normal(len(v)) * np.exp(-v / 0.015))
    # fold the tail onto the start: exactly periodic, no click at the loop point
    out[:pad] += out[n:n + pad]
    out = out[:n]
    # light reverb via FFT convolution with a decaying-noise impulse
    ir = rng.standard_normal(int(1.4 * SR)) * np.exp(-np.arange(int(1.4 * SR)) / SR / 0.35) * 0.02
    L = 1 << int(np.ceil(np.log2(n + len(ir))))
    wet = np.fft.irfft(np.fft.rfft(out, L) * np.fft.rfft(ir, L), L)
    wet[:len(ir)] += wet[n:n + len(ir)]                             # periodic tail
    out = out + wet[:n] * 0.6
    return out / np.abs(out).max() * 0.6


def soundtrack(path):
    mus = music()
    n = len(mus)
    voice = np.zeros(n); duck = np.ones(n)
    for l in LINES:
        b = subprocess.run([FF, "-v", "error", "-i", J("build", "portrait_vo", l["key"] + ".mp3"), "-ac", "1", "-ar", str(SR),
                            "-af", "highpass=f=80,loudnorm=I=-15:TP=-1.5", "-f", "f32le", "-"], capture_output=True).stdout
        a = np.frombuffer(b, np.float32).astype(np.float64)
        i0 = int(l["t0"] * SR); a = a[: max(0, n - i0)]
        voice[i0:i0 + len(a)] += a
        duck[max(0, i0 - int(0.2 * SR)): i0 + len(a) + int(0.3 * SR)] = 0.32
    k = int(0.4 * SR)
    c = np.concatenate(([0.0], np.cumsum(np.pad(duck, (k // 2, k - k // 2), mode="wrap"))))
    duck = (c[k:] - c[:-k])[:n] / k
    mix = np.tanh((mus * duck + voice * 0.95) * 1.05) * 0.85
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())


# ------------------------------------------------------------------ main
def media_stream():
    """Concatenated media-box frames with cross-fades; exactly N frames."""
    tail = []
    S = shots()
    count = 0
    for i, (name, dur, gen) in enumerate(S):
        n = int(round(dur * FPS)) + (XF if i else 0)          # the cross-fade overlap must not eat timeline
        last = i == len(S) - 1
        if last: n = N - count
        buf = []
        for f, fr in enumerate(gen(n / FPS + 0.01)):
            if f >= n: break
            if f < len(tail):
                w = (f + 1) / (len(tail) + 1)
                fr = (tail[f].astype(np.float32) * (1 - w) + fr.astype(np.float32) * w).astype(np.uint8)
            if not last and f >= n - XF:
                buf.append(fr); continue
            count += 1
            yield name, fr
        tail = buf
        print("  shot %2d/%d %-38s %5.2fs" % (i + 1, len(S), name[:38], dur), flush=True)


def main():
    os.makedirs(J("build", "portrait"), exist_ok=True)
    wav = J("build", "portrait", "soundtrack.wav")
    soundtrack(wav)
    out = J("build", "portrait", "NovaBand_Portrait_Reel%s.mp4" % ("_preview" if PREVIEW else ""))
    ow, oh = (W // 2, H // 2) if PREVIEW else (W, H)
    enc = subprocess.Popen([FF, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (ow, oh), "-r", str(FPS / 2 if PREVIEW else FPS),
                            "-i", "-", "-i", wav, "-c:v", "libx264", "-preset", "veryfast" if PREVIEW else "medium",
                            "-crf", "28" if PREVIEW else "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                            "-movflags", "+faststart", "-t", "%.2f" % TOTAL, out], stdin=subprocess.PIPE)
    head = {}
    LOOPXF = 15
    for k, (name, fr) in enumerate(media_stream()):
        t = k / FPS
        if k >= N: break
        if PREVIEW and k % 2: continue                             # preview: half the frames, half the size
        im = BG.copy()
        if not name.startswith("app"):
            im.paste(SHADOW, (BX - 60, BY - 60), SHADOW)
            im.paste(Image.fromarray(fr), (BX, BY), BOXMASK)
            d = ImageDraw.Draw(im, "RGBA")
            lab = name.split(":", 1)[1] if ":" in name else ""
            if lab:
                f = BOLD(34); tw = d.textlength(lab, font=f)
                d.rounded_rectangle((BX + 30, BY + 30, BX + 30 + tw + 50, BY + 92), 31, fill=(20, 4, 10, 200))
                d.text((BX + 55, BY + 61), lab, font=f, fill=WHITE, anchor="lm")
        else:
            im.paste(Image.fromarray(fr), (BX, BY), BOXMASK)
        phone(im, t)
        im = overlay(im, t)
        a = np.asarray(im)
        if k < LOOPXF:
            head[k] = a                                            # blended into the last frames: seamless loop
        if k >= N - LOOPXF and (k - (N - LOOPXF)) in head:
            w = (k - (N - LOOPXF) + 1) / (LOOPXF + 1)
            a = (a.astype(np.float32) * (1 - w) + head[k - (N - LOOPXF)].astype(np.float32) * w).astype(np.uint8)
        if PREVIEW:
            a = np.asarray(Image.fromarray(a).resize((ow, oh), Image.BILINEAR))
        enc.stdin.write(np.ascontiguousarray(a).tobytes())
    enc.stdin.close(); enc.wait()
    print(out)


if __name__ == "__main__":
    main()
