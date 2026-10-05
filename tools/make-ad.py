"""
Nova-Band 10-second looping ad, landscape (1920x1080) and portrait (1080x1920).

    python tools/make-ad.py landscape|portrait|both [--preview] [--still]

Layers: wine-red space + neon perspective grid, holo pad with pulse rings,
3D Nova (build/ad_nova/f_####.png, transparent, 240 frames = 10 s @ 24 fps,
rendered by blender/ad_nova.py), the Android phone mockup playing the real
app, the band product, and three copy beats. Every motion is a function of
phase = t / 10 s, so frame 240 equals frame 0 and the clip loops seamlessly.
--still uses a single mascot image (concept frames before the 3D render).
"""
import glob
import importlib.util
import math
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
J = lambda *p: os.path.join(ROOT, *p)
spec = importlib.util.spec_from_file_location("sr", J("tools", "make-app-showreel.py"))
SR = importlib.util.module_from_spec(spec)
spec.loader.exec_module(SR)
E = SR.E
PREVIEW = "--preview" in sys.argv
STILL = "--still" in sys.argv
FPS, DUR = 24, 10.0
N = int(FPS * DUR)
NEON, ROSE, CREAM, CYAN, WHITE = E.NEON, E.ROSE, E.CREAM, E.CYAN, E.WHITE
TAU = 2 * math.pi
clamp = E.clamp


def sm(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


def beat(ph, a, b, fade=0.05):
    """1 inside [a, b) of the loop (phase 0..1), smooth fades; periodic."""
    ph %= 1.0
    return sm((ph - a) / fade) * sm((b - ph) / fade) if a <= ph < b + 1e-9 else 0.0


# copy beats: (start, end, chip, line 1, line 2, sub)
BEATS = [
    (0.00, 0.33, "UPPER-ARM WEARABLE", "Lari lebih", "aman.", "Detak jantung real-time, langsung dari lengan atas."),
    (0.33, 0.66, "AI EARLY WARNING", "Tahu kapan", "harus berhenti.", "Peringatan dini untuk kamu dan pelatihmu."),
    (0.66, 1.00, "NOVA-BAND", "Monitor. Analyze.", "Improve.", "novaband-id.web.app"),
]


class Layout:
    def __init__(self, fmt, scale):
        self.fmt = fmt
        self.W, self.H = (1920, 1080) if fmt == "landscape" else (1080, 1920)
        if PREVIEW:
            self.W, self.H = self.W // 2, self.H // 2
        self.k = self.W / (1920 if fmt == "landscape" else 1080)
        k = self.k
        if fmt == "landscape":
            self.nova = (400 * k, 1010 * k, 880 * k)          # feet x, feet y, height
            self.phone = (850 * k, 520 * k, 760 * k)           # centre x, centre y, height
            self.band = (1090 * k, 860 * k, 190 * k)
            self.copy = (1170 * k, 330 * k, "la")
        else:
            self.nova = (430 * k, 1840 * k, 1000 * k)
            self.phone = (780 * k, 1020 * k, 760 * k)
            self.band = (880 * k, 1520 * k, 200 * k)
            self.copy = (80 * k, 150 * k, "la")


def S(L, v):
    return int(round(v * L.k))


# ---------------------------------------------------------------- background (periodic)
def make_bg(L):
    W, H = L.W, L.H
    yy = np.linspace(0, 1, H)[:, None, None]
    top, bot = np.array([10, 4, 9]), np.array([26, 6, 15])
    base = Image.fromarray(((top + (bot - top) * yy) * np.ones((1, W, 1))).astype(np.uint8)).convert("RGBA")
    rng = np.random.default_rng(5)
    d = ImageDraw.Draw(base)
    for _ in range(int(W * H / 9000)):
        x, y = rng.uniform(0, W), rng.uniform(0, H * 0.7)
        r = rng.uniform(0.5, 1.8) * L.k + 0.3
        d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 215, 222, int(rng.uniform(60, 210))))
    m = int(120 * L.k)
    blobs = []
    for cx, cy, rr, col in ((0.15, 0.08, 0.5, (160, 16, 44)), (0.9, 0.35, 0.42, (90, 14, 74)),
                            (0.5, 1.0, 0.36, (40, 120, 150))):
        R_ = rr * max(W, H)
        Lb = Image.new("RGBA", (W + 2 * m, H + 2 * m), (0, 0, 0, 0))
        ImageDraw.Draw(Lb).ellipse([m + cx * W - R_, m + cy * H - R_, m + cx * W + R_, m + cy * H + R_],
                                   fill=col + (150,))
        blobs.append(Lb.filter(ImageFilter.GaussianBlur(160 * L.k)))
    # grid floor: 24 phases = one cell per second (10 s loop stays seamless)
    yh = int(H * (0.62 if L.fmt == "landscape" else 0.70))
    ys = np.arange(yh + 1, H)[:, None].astype(np.float64)
    xs = np.arange(W)[None, :].astype(np.float64)
    f, hc = 900 * L.k, 3.4
    z = f * hc / (ys - yh)
    xw = (xs - W / 2) * z / f
    dx = np.abs(xw - np.round(xw)) * f / z
    fade = np.clip((ys - yh) / (H * 0.3), 0, 1) ** 1.4
    dzdy = f * hc / (ys - yh) ** 2
    grid = []
    for p in range(FPS):
        zz = z + p / FPS
        dz = np.abs(zz - np.round(zz)) / dzdy
        a = np.maximum(np.clip(1.3 - dx / (1.1 * L.k + .3), 0, 1), np.clip(1.3 - dz / (1.1 * L.k + .3), 0, 1)) * fade
        rgba = np.zeros((H - yh - 1, W, 4), np.uint8)
        rgba[..., :3] = NEON
        rgba[..., 3] = (a * 120).astype(np.uint8)
        grid.append(Image.fromarray(rgba, "RGBA"))
    return base, blobs, m, yh + 1, grid


def background(L, BG, ph, fi):
    base, blobs, m, gy, grid = BG
    im = base.copy()
    for k, b in enumerate(blobs):
        ox = int(math.sin(TAU * ph + k * 2) * m * 0.6)
        oy = int(math.cos(TAU * ph + k) * m * 0.4)
        im.alpha_composite(b.crop((m - ox, m - oy, m - ox + L.W, m - oy + L.H)))
    im.alpha_composite(grid[fi % FPS], (0, gy))
    return im


# ---------------------------------------------------------------- music (exactly periodic over 10 s)
def loop_music(path, sr=44100):
    import wave
    n = int(DUR * sr)
    t = np.arange(n) / sr
    out = np.zeros(n)
    chords = [(220.0, 261.6, 329.6), (174.6, 220.0, 261.6), (130.8, 196.0, 261.6), (196.0, 246.9, 293.7)]
    bar = DUR / 4
    for k, ch in enumerate(chords):
        for shift in (-DUR, 0.0, DUR):                       # wrap the envelope around the loop point
            tt = t - k * bar - shift
            env = np.clip(tt / 0.8, 0, 1) * np.exp(-np.clip(tt - bar, 0, None) / 0.7) * (tt >= 0)
            for f in ch:
                f = round(f * DUR) / DUR                     # whole cycles per loop: no click at the seam
                for h, g in ((1, 1.0), (2, 0.3), (3, 0.1)):
                    out += g * env * np.sin(TAU * f * h * t)
            f0 = round(ch[0] / 2 * DUR) / DUR
            out += 0.5 * env * np.sin(TAU * f0 * t)
    # soft pulse: a muted pluck on every eighth (period 10 s / 32)
    step = DUR / 32
    for i in range(32):
        for shift in (-DUR, 0.0, DUR):
            tt = t - i * step - shift
            m = (tt >= 0) & (tt < 0.4)
            f = round(chords[i // 8][(i % 3)] * 2 * DUR) / DUR
            out[m] += 0.18 * np.exp(-tt[m] / 0.09) * np.sin(TAU * f * t[m])
    out = out / np.abs(out).max() * 0.5
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((out * 32767).astype(np.int16).tobytes())


# ---------------------------------------------------------------- pieces
def holo_pad(im, L, cx, cy, w, ph):
    pad = Image.new("RGBA", (int(w * 1.4), int(w * 0.42)), (0, 0, 0, 0))
    d = ImageDraw.Draw(pad)
    pw, phh = pad.size
    for k in range(12, 0, -1):
        rx, ry = pw / 2 * k / 12, phh / 2 * k / 12
        d.ellipse([pw / 2 - rx, phh / 2 - ry, pw / 2 + rx, phh / 2 + ry], fill=NEON + (int(10 + 7 * (12 - k)),))
    for k in range(3):
        u = (ph * 3 + k / 3) % 1
        rx, ry = pw / 2 * (0.35 + 0.65 * u), phh / 2 * (0.35 + 0.65 * u)
        d.ellipse([pw / 2 - rx, phh / 2 - ry, pw / 2 + rx, phh / 2 + ry], outline=(255, 150, 165, int(230 * (1 - u))),
                  width=max(1, S(L, 3)))
    im.alpha_composite(pad.filter(ImageFilter.GaussianBlur(2)), (int(cx - pw / 2), int(cy - phh / 2)))
    # light column
    col = Image.new("RGBA", (int(w * 0.9), int(w * 1.9)), (0, 0, 0, 0))
    cw, ch = col.size
    cd = ImageDraw.Draw(col)
    for y in range(ch):
        a = int(70 * (y / ch) ** 2)
        cd.line([(cw * 0.5 - cw * 0.5 * (0.5 + 0.5 * y / ch), y), (cw * 0.5 + cw * 0.5 * (0.5 + 0.5 * y / ch), y)],
                fill=NEON + (a,))
    im.alpha_composite(col.filter(ImageFilter.GaussianBlur(S(L, 14))), (int(cx - cw / 2), int(cy - ch)))


_nova = {}


def nova_frame(L, fi):
    if STILL:
        key = ("still", L.fmt)
        if key not in _nova:
            src = J("build", "mascot_concept", "hero_1.png")
            if not os.path.exists(src):
                src = J("assets", "img", "mascot-hero.webp")
            _nova[key] = Image.open(src).convert("RGBA")
        return _nova[key], 0.08
    fs = sorted(glob.glob(J("build", "ad_nova", "f_*.png")))
    return Image.open(fs[fi % len(fs)]).convert("RGBA"), 0.06


def put_nova(im, L, fi, ph):
    fx, fy, h = L.nova
    holo_pad(im, L, fx, fy, h * 0.55, ph)
    fr, foot_pad = nova_frame(L, fi)
    bob = 0 if not STILL else math.sin(TAU * ph * 2) * S(L, 8)
    k = h / fr.height
    fr = fr.resize((int(fr.width * k), int(h)), Image.LANCZOS if not PREVIEW else Image.BILINEAR)
    im.alpha_composite(fr, (int(fx - fr.width / 2), int(fy - fr.height * (1 - foot_pad) + bob)))


def put_phone(im, L, ph, alert_glow):
    cx, cy, h = L.phone
    starts = [(0.0, SR.MK["home"] + 2.5), (1 / 3, SR.MK["alert_on"] - 0.5), (2 / 3, SR.MK["ready"] + 0.8)]

    def rec(seg, p_):
        a, t0 = starts[seg]
        return t0 + ((p_ - a) % 1.0) * DUR

    seg = 0 if ph < 1 / 3 else (1 if ph < 2 / 3 else 2)
    yaw = -16 + 6 * math.sin(TAU * ph)
    p = SR.phone(rec(seg, ph), yaw, h)
    # dissolve the screen into the next beat's screen over the last 0.4 s of each beat
    nxt_a = starts[(seg + 1) % 3][0] or 1.0
    X = 0.04
    if ph > nxt_a - X:
        q = SR.phone(rec((seg + 1) % 3, ph), yaw, h)
        p = Image.blend(p, q.resize(p.size), (ph - (nxt_a - X)) / X * 0.5)
    elif ph < starts[seg][0] + X:
        q = SR.phone(rec((seg - 1) % 3, ph), yaw, h)
        p = Image.blend(q.resize(p.size), p, 0.5 + (ph - starts[seg][0]) / X * 0.5)
    y = cy + math.sin(TAU * ph * 2 + 1) * S(L, 12)
    g = Image.new("RGBA", (p.width + S(L, 200), p.height + S(L, 200)), (0, 0, 0, 0))
    ImageDraw.Draw(g).rounded_rectangle([S(L, 100), S(L, 100), S(L, 100) + p.width, S(L, 100) + p.height], S(L, 60),
                                        fill=(255, 60, 80, int(90 + 90 * alert_glow)))
    im.alpha_composite(g.filter(ImageFilter.GaussianBlur(S(L, 44))), (int(cx - g.width / 2), int(y - g.height / 2)))
    im.alpha_composite(p, (int(cx - p.width / 2), int(y - p.height / 2)))


_band = {}


def put_band(im, L, ph):
    cx, cy, h = L.band
    if h not in _band:
        b = Image.open(J("assets", "img", "product-side.webp")).convert("RGBA")
        _band[h] = b.resize((int(b.width * h / b.height), int(h)), Image.LANCZOS)
    b = _band[h].rotate(-12 + 8 * math.sin(TAU * ph), expand=True, resample=Image.BICUBIC)
    y = cy + math.sin(TAU * ph * 2) * S(L, 14)
    sh = Image.new("RGBA", (b.width, b.height // 3), (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse([b.width * 0.15, 0, b.width * 0.85, b.height // 3 - 1], fill=(0, 0, 0, 110))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(S(L, 16))), (int(cx - b.width / 2), int(cy + h * 0.45)))
    im.alpha_composite(b, (int(cx - b.width / 2), int(y - b.height / 2)))


def put_copy(im, L, ph):
    x, y, _ = L.copy
    for (a0, a1, chip, l1, l2, sub) in BEATS:
        a = beat(ph, a0, a1, 0.035)
        if a <= 0:
            continue
        u = ((ph - a0) % 1.0) / (a1 - a0)
        slide = (1 - sm(u / 0.12)) * S(L, 40)
        d = ImageDraw.Draw(im)
        F = lambda f, s: f(s * L.k / E.K)       # E fonts scale by the 1920-wide K
        E.R.txt(d, (x, y), chip, F(E.SEMI, 26), CYAN, a, spacing=S(L, 6))
        size = 70 if L.fmt == "landscape" else 104
        E.text(d, (x - S(L, 4) + slide, y + S(L, 44)), l1, F(E.XB, size), WHITE, a)
        E.glow_text(im, (x - S(L, 4) + slide, y + S(L, 44 + size * 1.12)), l2, F(E.XB, size), NEON, a, 20)
        d = ImageDraw.Draw(im)
        fs = F(E.REG, 28 if L.fmt == "landscape" else 36)
        maxw = (L.W - x - S(L, 60))
        words, line, ly = sub.split(), "", y + S(L, 60 + size * 2.3)
        for w_ in words:
            if fs.getlength((line + " " + w_).strip()) > maxw:
                E.text(d, (x, ly), line.strip(), fs, CREAM, a)
                line, ly = w_, ly + int(fs.size * 1.45)
            else:
                line += " " + w_
        E.text(d, (x, ly), line.strip(), fs, CREAM, a)


def logo(im, L):
    d = ImageDraw.Draw(im)
    if L.fmt == "landscape":
        x, y = L.W - S(L, 330), L.H - S(L, 100)
    else:
        x, y = S(L, 80), S(L, 60)
        return
    d.rounded_rectangle([x, y, x + S(L, 52), y + S(L, 52)], S(L, 14), fill=NEON + (255,))
    F = lambda f, s: f(s * L.k / E.K)
    E.text(d, (x + S(L, 26), y + S(L, 26)), "N", F(E.XB, 32), WHITE, 1, "mm")
    E.text(d, (x + S(L, 68), y + S(L, 26)), "Nova-Band", F(E.XB, 34), WHITE, 1, "lm")


def render_frame(L, BG, fi):
    ph = fi / N
    im = background(L, BG, ph, fi)
    alert = beat(ph, 0.36, 0.62, 0.05)
    if L.fmt == "landscape":
        put_phone(im, L, ph, alert)
        put_band(im, L, ph)
        put_nova(im, L, fi, ph)
    else:
        put_phone(im, L, ph, alert)
        put_nova(im, L, fi, ph)
        put_band(im, L, ph)
    put_copy(im, L, ph)
    logo(im, L)
    return im.convert("RGB")


def build(fmt):
    L = Layout(fmt, 1.0)
    SR.setup()
    BG = make_bg(L)
    if STILL:
        for fi in (int(N * 0.12), int(N * 0.47), int(N * 0.8)):
            render_frame(L, BG, fi).save(J("build", "ad_concept_%s_%d.jpg" % (fmt, fi)), quality=88)
        print("concept frames", fmt)
        return
    ff = E.R.find_ffmpeg()
    out = J("assets", "novaband-ad-%s%s.mp4" % (fmt, "-preview" if PREVIEW else ""))
    step = 3 if PREVIEW else 1
    music = J("build", "ad_music.wav")
    loop_music(music)
    p = subprocess.Popen([ff, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s",
                          "%dx%d" % (L.W, L.H), "-r", str(FPS / step), "-i", "-", "-i", music,
                          "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p",
                          "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", out],
                         stdin=subprocess.PIPE)
    for fi in range(0, N, step):
        p.stdin.write(render_frame(L, BG, fi).tobytes())
    p.stdin.close()
    p.wait()
    print("wrote", out)


if __name__ == "__main__":
    fmts = [a for a in sys.argv[1:] if not a.startswith("--")] or ["both"]
    for f in (["landscape", "portrait"] if fmts[0] == "both" else fmts):
        build(f)
