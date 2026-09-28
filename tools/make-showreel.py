"""
Nova-Band showreel compositor.

    python tools/make-showreel.py            -> assets/novaband-showreel.{mp4,webm} + poster
    python tools/make-showreel.py --preview  -> build/reel-frames/*.png (one still per scene)

Inputs
  build/reel/{orbit,exploded,arm}/frame_####.png   3D shots (blender/novaband_reel3d.py)
  assets/3d/*.webp                                   Blender icon library
  assets/img/*.webp                                  photos + app mockup from the ISIF deck
  build/fonts/*.ttf                                  Poppins + Fraunces (same as the site)

Every frame is drawn in the site's "white & clean" language — white
ground, deck red accents, Poppins headlines — and piped straight into
ffmpeg, so no intermediate frame sequence ever hits the disk.
"""
import math
import os
import subprocess
import sys
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
J = lambda *p: os.path.join(ROOT, *p)

W, H, FPS = 1920, 1080, 30


def find_ffmpeg():
    """NB_FFMPEG env var, then PATH, then the WinGet install location."""
    import glob
    import shutil
    cands = [os.environ.get("NB_FFMPEG"), shutil.which("ffmpeg")]
    cands += glob.glob(os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WinGet",
                                    "Packages", "Gyan.FFmpeg*", "*", "bin", "ffmpeg.exe"))
    for c in cands:
        if c and os.path.exists(c):
            return c
    raise SystemExit("ffmpeg not found: install it or set NB_FFMPEG")


FFMPEG = None
PREVIEW = "--preview" in sys.argv

WHITE = (255, 255, 255)
RED = (123, 32, 33)
DEEP = (75, 7, 15)
MID = (150, 42, 44)
INK = (28, 18, 21)
INK2 = (93, 82, 86)
INK3 = (148, 138, 141)
ROSE = (201, 163, 163)
SOFT = (248, 238, 238)


# ---------------------------------------------------------------- helpers
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease_out(t):
    t = clamp(t)
    return 1 - (1 - t) ** 3


def ease_in_out(t):
    t = clamp(t)
    return 3 * t * t - 2 * t * t * t


def back_out(t, s=1.5):
    t = clamp(t) - 1
    return t * t * ((s + 1) * t + s) + 1


def seg(t, a, b):
    """Normalised progress of t inside [a, b] seconds."""
    return clamp((t - a) / (b - a)) if b > a else float(t >= a)


@lru_cache(maxsize=None)
def font(name, size):
    f = ImageFont.truetype(J("build", "fonts", name), size)
    if name.startswith("Fraunces"):
        try:
            f.set_variation_by_axes([144, 600, 50, 1])   # opsz, wght, SOFT, WONK
        except Exception:
            pass
    return f


def BOLD(s):
    return font("Poppins-ExtraBold.ttf", s)


def SEMI(s):
    return font("Poppins-SemiBold.ttf", s)


def MEDI(s):
    return font("Poppins-Medium.ttf", s)


def REG(s):
    return font("Poppins-Regular.ttf", s)


def SERIF(s):
    return font("Fraunces-Italic.ttf", s)


@lru_cache(maxsize=None)
def asset(path, w=None):
    im = Image.open(J(*path.split("/"))).convert("RGBA")
    if w and im.width != w:
        im = im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)
    return im


def fade(im, a):
    if a >= 0.999:
        return im
    im = im.copy()
    alpha = im.getchannel("A").point(lambda v: int(v * clamp(a)))
    im.putalpha(alpha)
    return im


def paste(canvas, im, x, y, alpha=1.0, anchor="mm"):
    if alpha <= 0.002:
        return
    im = fade(im, alpha)
    if anchor == "mm":
        x, y = x - im.width // 2, y - im.height // 2
    elif anchor == "lm":
        y = y - im.height // 2
    canvas.alpha_composite(im, (int(round(x)), int(round(y))))


def text(canvas, xy, s, f, fill, alpha=1.0, anchor="la", spacing=0):
    """Text with its own alpha and optional letter tracking (in px)."""
    if alpha <= 0.002:
        return
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    col = fill + (int(255 * clamp(alpha)),)
    if spacing:
        x, y = xy
        if anchor[0] == "m":
            total = sum(d.textlength(ch, font=f) + spacing for ch in s) - spacing
            x -= total / 2
        for ch in s:
            d.text((x, y), ch, font=f, fill=col, anchor="l" + anchor[1])
            x += d.textlength(ch, font=f) + spacing
    else:
        d.text(xy, s, font=f, fill=col, anchor=anchor)
    canvas.alpha_composite(layer)


def rise(canvas, xy, s, f, fill, t, delay=0.0, dur=0.55, dist=26, anchor="la", spacing=0):
    """Headline entrance: fade + rise, the same motion as the site's .reveal."""
    p = ease_out(seg(t, delay, delay + dur))
    text(canvas, (xy[0], xy[1] + (1 - p) * dist), s, f, fill, alpha=p, anchor=anchor, spacing=spacing)


def pill(canvas, x, y, s, t, delay=0.0, bg=SOFT, fg=RED, size=22):
    p = ease_out(seg(t, delay, delay + 0.5))
    if p <= 0:
        return
    f = SEMI(size)
    d = ImageDraw.Draw(canvas)
    tw = sum(d.textlength(ch, font=f) + 3 for ch in s)
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    h = size * 2
    ld.rounded_rectangle([x, y, x + tw + 58, y + h], radius=h // 2, fill=bg + (int(255 * p),))
    ld.ellipse([x + 20, y + h / 2 - 5, x + 30, y + h / 2 + 5], fill=fg + (int(255 * p),))
    canvas.alpha_composite(layer)
    text(canvas, (x + 42, y + h / 2), s, f, fg, alpha=p, anchor="lm", spacing=3)


def rrect(canvas, box, r, fill, alpha=1.0, outline=None, width=2):
    if alpha <= 0.002:
        return
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle(box, radius=r, fill=fill + (int(255 * alpha),) if fill else None,
                        outline=(outline + (int(255 * alpha),)) if outline else None, width=width)
    canvas.alpha_composite(layer)


def shadowed(im, blur=26, offset=(0, 26), strength=0.22):
    """Soft card shadow under a sprite, for photos and the phone mockup."""
    pad = blur * 3
    sh = Image.new("RGBA", (im.width + pad * 2, im.height + pad * 2), (0, 0, 0, 0))
    a = im.getchannel("A").point(lambda v: int(v * strength))
    tint = Image.new("RGBA", im.size, DEEP + (255,))
    tint.putalpha(a)
    sh.alpha_composite(tint, (pad + offset[0], pad + offset[1]))
    sh = sh.filter(ImageFilter.GaussianBlur(blur))
    sh.alpha_composite(im, (pad, pad))
    return sh


# ---------------------------------------------------------------- background
DOTS = None


def background(t, tint=WHITE):
    global DOTS
    bg = Image.new("RGBA", (W, H), tint + (255,))
    if DOTS is None:
        d = asset("assets/3d/dots-wave.webp", 1500)
        DOTS = fade(d, 0.55)
    # the deck's dotted wave drifting slowly along the bottom
    x = -120 + 60 * math.sin(t * 0.25)
    bg.alpha_composite(DOTS, (int(x), H - DOTS.height + 150))
    return bg


@lru_cache(maxsize=4)
def shot_frame(shot, n):
    path = J("build", "reel", shot, "frame_%04d.png" % n)
    return Image.open(path).convert("RGBA")


def shot_count(shot):
    d = J("build", "reel", shot)
    return len([f for f in os.listdir(d) if f.endswith(".png")])


def draw_shot(canvas, shot, t, dur, dx=0, dy=0, scale=1.0, alpha=1.0):
    n = shot_count(shot)
    # t is negative while the previous scene is still dissolving into this one
    k = 1 + max(0, min(n - 1, int(t / dur * n)))
    im = shot_frame(shot, k)
    if scale != 1.0:
        im = im.resize((int(W * scale), int(H * scale)), Image.LANCZOS)
    paste(canvas, im, W / 2 + dx, H / 2 + dy, alpha=alpha)


# ---------------------------------------------------------------- scenes
# each scene: (duration seconds, draw(canvas, t_local))
def s_intro(c, t):
    prod = asset("assets/img/product-side.webp", 560)
    p = back_out(seg(t, 0.15, 1.1), 1.2)
    float_y = 12 * math.sin(t * 1.6)
    blob = Image.new("RGBA", (760, 760), (0, 0, 0, 0))
    ImageDraw.Draw(blob).ellipse([0, 0, 760, 760], fill=SOFT + (255,))
    paste(c, blob, 1480, 540, alpha=ease_out(seg(t, 0, 0.8)))
    paste(c, shadowed(prod, 40, (0, 50), 0.3), 1480 + (1 - p) * 260, 540 + float_y, alpha=clamp(p * 1.4))
    pills = asset("assets/3d/pills.webp", 420)
    paste(c, pills, 1760, 240 - 20 * math.sin(t), alpha=ease_out(seg(t, 0.6, 1.3)))

    pill(c, 150, 250, "ISIF 2026 · SMA NEGERI 1 SURAKARTA", t, 0.1, size=20)
    big = BOLD(156)
    rise(c, (140, 460), "Nova", big, INK, t, 0.25, anchor="ls")
    nova_w = ImageDraw.Draw(c).textlength("Nova", font=big)
    rise(c, (140 + nova_w, 460), "-", big, RED, t, 0.35, anchor="ls")
    dash_w = ImageDraw.Draw(c).textlength("-", font=big)
    rise(c, (140 + nova_w + dash_w, 460), "Band", big, INK, t, 0.45, anchor="ls")
    rise(c, (150, 560), "An AIoT-Driven Upper-Arm Wearable", SEMI(40), INK, t, 0.8)
    rise(c, (150, 612), "for Real-Time Physiological Monitoring", SEMI(40), INK, t, 0.9)
    rise(c, (150, 664), "and Running Performance", SEMI(40), INK, t, 1.0)
    rise(c, (150, 760), "AI Body Assistant for Runners", SERIF(46), RED, t, 1.4)


def s_orbit(c, t):
    draw_shot(c, "orbit", t, 5.0, dx=330, dy=10, scale=0.92)
    pill(c, 150, 330, "UPPER-ARM FIT", t, 0.1)
    rise(c, (140, 480), "Stabil di", BOLD(104), INK, t, 0.2, anchor="ls")
    rise(c, (140, 600), "lengan atas.", SERIF(112), RED, t, 0.35, anchor="ls")
    rise(c, (150, 680), "Jauh dari titik ayun terbesar saat berlari,", REG(34), INK2, t, 0.8)
    rise(c, (150, 728), "sensor tetap menempel rapat di kulit.", REG(34), INK2, t, 0.9)


EXPLODE_SCALE, EXPLODE_DY = 0.86, 40
EXPLODE_LABELS = [
    # (layer y in the raw 1080p render, side, label, appears at s) —
    # mapped through the same scale/offset the shot is drawn with
    (90, "r", "Jendela optik + 2 LED hijau + IR", 2.4),
    (360, "l", "Casing polimer cetak 3D", 2.6),
    (555, "r", "Baterai Li-Po", 2.8),
    (720, "l", "Mini PCB · ESP32 · IMU", 3.0),
    (930, "r", "Sensor pod sisi kulit", 3.2),
]


def s_exploded(c, t):
    draw_shot(c, "exploded", t, 5.0, dx=0, dy=EXPLODE_DY, scale=EXPLODE_SCALE)
    pill(c, 150, 120, "DI DALAM MODUL", t, 0.1)
    rise(c, (140, 250), "Lima lapis,", BOLD(84), INK, t, 0.2, anchor="ls")
    rise(c, (140, 345), "satu modul.", SERIF(92), RED, t, 0.35, anchor="ls")
    for y, side, label, at in EXPLODE_LABELS:
        y = H / 2 + (y - H / 2) * EXPLODE_SCALE + EXPLODE_DY
        p = ease_out(seg(t, at, at + 0.5))
        if p <= 0:
            continue
        f = SEMI(28)
        d = ImageDraw.Draw(c)
        tw = d.textlength(label, font=f)
        if side == "r":
            x0 = 1230 + (1 - p) * 40
        else:
            x0 = 690 - tw - 70 - (1 - p) * 40
        rrect(c, [x0, y - 30, x0 + tw + 70, y + 30], 30, WHITE, alpha=p, outline=(236, 228, 228))
        layer = Image.new("RGBA", c.size, (0, 0, 0, 0))
        ImageDraw.Draw(layer).ellipse([x0 + 22, y - 7, x0 + 36, y + 7], fill=RED + (int(255 * p),))
        c.alpha_composite(layer)
        text(c, (x0 + 50, y), label, f, INK, alpha=p, anchor="lm")


def s_arm(c, t):
    draw_shot(c, "arm", t, 4.0, dx=0, dy=40, scale=1.0)
    rrect(c, [0, 0, W, 330], 0, WHITE, alpha=0.0)
    pill(c, 150, 90, "AIoT SYNERGY", t, 0.1)
    first_w = ImageDraw.Draw(c).textlength("Satu band.", font=BOLD(96))
    rise(c, (140, 230), "Satu band.", BOLD(96), INK, t, 0.2, anchor="ls")
    rise(c, (140 + first_w + 28, 230), "Selalu memantau.", SERIF(100), RED, t, 0.4, anchor="ls")


PPG = [("led-sensor", "LED Sensor"), ("blood-cells", "Blood Absorbs Light"),
       ("photodetector", "Photodetector"), ("microcontroller", "Mikrokontroler"), ("heart", "Heart Beats")]


def s_ppg(c, t):
    pill(c, 150, 120, "HARDWARE OPERATION · PPG", t, 0.05)
    rise(c, (140, 250), "Dari seberkas cahaya", BOLD(84), INK, t, 0.15, anchor="ls")
    rise(c, (140, 345), "menjadi detak jantung.", SERIF(92), RED, t, 0.3, anchor="ls")
    x0, gap, y = 250, 355, 650
    for i, (name, label) in enumerate(PPG):
        at = 0.7 + i * 0.45
        p = back_out(seg(t, at, at + 0.55))
        if p <= 0:
            continue
        x = x0 + i * gap
        rrect(c, [x - 150, y - 175, x + 150, y + 190], 36, WHITE, alpha=clamp(p), outline=(238, 230, 230))
        icon = asset("assets/3d/%s.webp" % name, 250)
        s = max(0.05, p)
        im = icon.resize((max(1, int(icon.width * s)), max(1, int(icon.height * s))), Image.LANCZOS)
        paste(c, im, x, y - 30, alpha=clamp(p))
        rrect(c, [x - 128, y - 158, x - 88, y - 118], 20, RED, alpha=clamp(p))
        text(c, (x - 108, y - 138), str(i + 1), SEMI(22), WHITE, alpha=clamp(p), anchor="mm")
        text(c, (x, y + 145), label, SEMI(27), INK, alpha=clamp(p), anchor="mm")
        if i < len(PPG) - 1:
            q = ease_out(seg(t, at + 0.3, at + 0.6))
            text(c, (x + gap / 2, y), "›", BOLD(64), RED, alpha=q, anchor="mm")


IMU = [("accelerometer", "Accelerometer", "jatuh & kolaps"),
       ("gyroscope", "Gyroscope", "postur & keseimbangan"),
       ("magnetometer", "Magnetometer", "orientasi & lokasi")]


def s_imu(c, t):
    pill(c, 150, 120, "HARDWARE OPERATION · IMU", t, 0.05)
    rise(c, (140, 250), "Tiga sensor gerak", BOLD(84), INK, t, 0.15, anchor="ls")
    rise(c, (140, 345), "untuk keadaan darurat.", SERIF(92), RED, t, 0.3, anchor="ls")
    for i, (name, label, note) in enumerate(IMU):
        at = 0.6 + i * 0.4
        p = ease_out(seg(t, at, at + 0.6))
        x, y = 420 + i * 540, 680 + (1 - p) * 60
        rrect(c, [x - 230, y - 210, x + 230, y + 200], 40, WHITE, alpha=p, outline=(238, 230, 230))
        paste(c, asset("assets/3d/%s.webp" % name, 300), x, y - 50, alpha=p)
        text(c, (x, y + 118), label, BOLD(38), INK, alpha=p, anchor="mm")
        text(c, (x, y + 162), note.upper(), SEMI(20), RED, alpha=p, anchor="mm", spacing=3)


def s_results(c, t):
    pill(c, 150, 120, "RESULT & DISCUSSION", t, 0.05)
    rise(c, (140, 250), "Akurat di lapangan,", BOLD(84), INK, t, 0.15, anchor="ls")
    rise(c, (140, 345), "nyaman dipakai.", SERIF(92), RED, t, 0.3, anchor="ls")
    for i, (big, unit, label, icon, frac) in enumerate([
            ("2,5–3,5", "% MAPE", "Error pembacaan sensor · ambang profesional < 5%", "gauge", 0.07),
            (None, "/ 100 SUS", "Acceptable · Grade A · 60 responden", "medal", 0.845)]):
        at = 0.6 + i * 0.5
        p = ease_out(seg(t, at, at + 0.6))
        x0, y0 = 150 + i * 840, 470 + (1 - p) * 50
        rrect(c, [x0, y0, x0 + 780, y0 + 440], 44, WHITE, alpha=p, outline=(238, 230, 230))
        paste(c, asset("assets/3d/%s.webp" % icon, 150), x0 + 680, y0 + 95, alpha=p)
        if big is None:
            v = 84.5 * ease_out(seg(t, at + 0.2, at + 1.6))
            big = ("%.1f" % v).replace(".", ",")
        f = BOLD(150)
        text(c, (x0 + 50, y0 + 250), big, f, RED, alpha=p, anchor="ls")
        bw = ImageDraw.Draw(c).textlength(big, font=f)
        text(c, (x0 + 60 + bw, y0 + 250), unit, SEMI(40), INK3, alpha=p, anchor="ls")
        m = ease_out(seg(t, at + 0.3, at + 1.6)) * frac
        rrect(c, [x0 + 50, y0 + 300, x0 + 730, y0 + 318], 9, (239, 233, 232), alpha=p)
        if m > 0.005:
            rrect(c, [x0 + 50, y0 + 300, x0 + 50 + 680 * m, y0 + 318], 9, RED, alpha=p)
        text(c, (x0 + 50, y0 + 375), label, REG(28), INK2, alpha=p, anchor="ls")


def s_market(c, t):
    pill(c, 150, 120, "MARKET · DATA EVENT LARI 2025", t, 0.05)
    rise(c, (140, 250), "Ribuan event lari,", BOLD(84), INK, t, 0.15, anchor="ls")
    rise(c, (140, 345), "satu jaring pengaman.", SERIF(92), RED, t, 0.3, anchor="ls")
    rows = [("TAM", "Indonesia", 1818, DEEP, 0), ("SAM", "Jawa Tengah", 302, RED, 90), ("SOM", "Surakarta", 18, MID, 180)]
    for i, (k, where, n, col, inset) in enumerate(rows):
        at = 0.6 + i * 0.35
        p = ease_out(seg(t, at, at + 0.6))
        y = 470 + i * 150
        x0 = 150 + inset + (1 - p) * -80
        rrect(c, [x0, y, x0 + 1180 - 2 * inset, y + 124], 36, col, alpha=p)
        text(c, (x0 + 50, y + 62), k, BOLD(54), WHITE, alpha=p, anchor="lm")
        text(c, (x0 + 250, y + 62), where, MEDI(34), WHITE, alpha=p * 0.9, anchor="lm")
        v = int(n * ease_out(seg(t, at + 0.2, at + 1.4)))
        text(c, (x0 + 1130 - 2 * inset, y + 62), "{:,}".format(v).replace(",", "."), BOLD(60), WHITE,
             alpha=p, anchor="rm")
    paste(c, asset("assets/3d/target-tiers.webp", 380), 1620, 640, alpha=ease_out(seg(t, 0.9, 1.6)))


def s_outro(c, t):
    p = ease_in_out(seg(t, 0, 0.7))
    # red panel wipes up from the bottom, like the site's CTA block
    top = int(H - H * p)
    rrect(c, [0, top, W, H + 60], 0, RED, alpha=1.0)
    if p < 0.6:
        return
    q = seg(t, 0.6, 3.5)
    dev = asset("assets/3d/device-hero.webp", 700)
    paste(c, dev, 1500, 560 + 14 * math.sin(t * 1.4), alpha=ease_out(seg(t, 0.8, 1.6)))
    text(c, (150, 330), "ISIF 2026 · SMA NEGERI 1 SURAKARTA", SEMI(22), (255, 220, 220),
         alpha=ease_out(seg(t, 0.8, 1.3)), spacing=3)
    rise(c, (140, 520), "Nova-Band", BOLD(150), WHITE, t, 0.9, anchor="ls")
    rise(c, (150, 610), "AI Body Assistant for Runners", SERIF(58), (255, 226, 226), t, 1.2)
    a = ease_out(seg(t, 1.6, 2.2))
    rrect(c, [150, 690, 700, 770], 40, WHITE, alpha=a)
    text(c, (425, 730), "novaband-id.web.app", SEMI(34), DEEP, alpha=a, anchor="mm")
    text(c, (150, 900), "Monitor. Analyze. Improve.", MEDI(30), (255, 210, 210), alpha=ease_out(seg(t, 2.2, 2.8)))


SCENES = [
    ("intro", 3.2, s_intro),
    ("orbit", 5.0, s_orbit),
    ("exploded", 5.0, s_exploded),
    ("arm", 4.0, s_arm),
    ("ppg", 5.0, s_ppg),
    ("imu", 4.2, s_imu),
    ("results", 4.6, s_results),
    ("market", 4.4, s_market),
    ("outro", 4.2, s_outro),
]
XFADE = 0.35   # seconds of cross-dissolve between scenes


def render_scene(fn, t, total_t):
    c = background(total_t)
    fn(c, t)
    return c


def frames():
    starts, acc = [], 0.0
    for _, dur, _ in SCENES:
        starts.append(acc)
        acc += dur
    total = acc
    n = int(round(total * FPS))
    for k in range(n):
        T = k / FPS
        i = max(j for j, s in enumerate(starts) if s <= T)
        name, dur, fn = SCENES[i]
        t = T - starts[i]
        im = render_scene(fn, t, T)
        # dissolve into the next scene over the last XFADE seconds
        if i + 1 < len(SCENES) and t > dur - XFADE:
            nxt = SCENES[i + 1]
            im2 = render_scene(nxt[2], t - dur, T)
            im = Image.blend(im, im2, ease_in_out((t - (dur - XFADE)) / XFADE))
        yield k, n, im


def main():
    if PREVIEW:
        out = J("build", "reel-frames")
        os.makedirs(out, exist_ok=True)
        for name, dur, fn in SCENES:
            for frac in (0.85,):
                im = render_scene(fn, dur * frac, 0)
                im.convert("RGB").save(os.path.join(out, "%s.png" % name))
        print("previews ->", out)
        return

    mp4 = J("assets", "novaband-showreel.mp4")
    tmp = J("build", "showreel-master.mp4")
    global FFMPEG
    FFMPEG = find_ffmpeg()
    cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H), "-r", str(FPS), "-i", "-",
           "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-pix_fmt", "yuv420p", tmp]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    poster_at = int(SCENES[0][1] * FPS + 3.6 * FPS)
    for k, n, im in frames():
        rgb = im.convert("RGB")
        proc.stdin.write(rgb.tobytes())
        if k == poster_at:
            rgb.save(J("assets", "novaband-showreel-poster.jpg"), quality=86, optimize=True)
        if k % 60 == 0:
            print("frame %d/%d" % (k, n), flush=True)
    proc.stdin.close()
    proc.wait()

    # web encodes from the high-quality master
    subprocess.run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", tmp,
                    "-c:v", "libx264", "-preset", "slow", "-crf", "23", "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart", "-an", mp4], check=True)
    subprocess.run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", tmp,
                    "-c:v", "libvpx-vp9", "-b:v", "0", "-crf", "36", "-row-mt", "1", "-an",
                    J("assets", "novaband-showreel.webm")], check=True)
    for f in ("novaband-showreel.mp4", "novaband-showreel.webm", "novaband-showreel-poster.jpg"):
        print("%-32s %7.0f KB" % (f, os.path.getsize(J("assets", f)) / 1024))


if __name__ == "__main__":
    main()
