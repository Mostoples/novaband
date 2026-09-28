"""
Nova-Band gym showreel: cut the Cycles shots (blender/reel_gym.py ->
build/reel2/<shot>/f_####.png) with titles, captions and cross-fades.

    python tools/make-showreel2.py            # -> assets/novaband-showreel-gym.{mp4,webm} + poster
    python tools/make-showreel2.py --preview  # every 5th frame, 960 px, fast

Frames stream straight into ffmpeg (rawvideo on stdin): nothing
intermediate is written to disk.
"""
import glob
import os
import shutil
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
J = lambda *p: os.path.join(ROOT, *p)
PREVIEW = "--preview" in sys.argv
W, H = (960, 540) if PREVIEW else (1920, 1080)
K = W / 1920
FPS = 25
XF = 10                          # cross-fade, frames
WINE, CREAM, ROSE = (123, 32, 33), (243, 227, 211), (201, 163, 163)

SHOTS = [  # folder, title, subtitle
    ("establish", "Built for the gym floor", "Heart rate, PPG and motion, read on the upper arm"),
    ("orbit", "Worn on the upper arm", "Where the swing is smallest, the optical signal stays clean"),
    ("arm", "A live screen on the band", "ESP32-S3  ·  1.9\" touch  ·  60 fps firmware"),
    ("bench", "Paired with the app", "Bluetooth LE or USB  ·  installable web app (PWA)"),
    ("exploded", "A printed prototype", "Sketched in LibreCAD  ·  solid-modelled in FreeCAD"),
    ("hero", "Nova-Band", "Monitor. Analyze. Improve."),
]
INTRO, OUTRO = 3.0, 4.5


def find_ffmpeg():
    c = [os.environ.get("NB_FFMPEG"), shutil.which("ffmpeg")]
    c += glob.glob(os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WinGet", "Packages",
                                "Gyan.FFmpeg*", "*", "bin", "ffmpeg.exe"))
    for p in c:
        if p and os.path.exists(p):
            return p
    raise SystemExit("ffmpeg not found")


def F(name, size):
    return ImageFont.truetype(J("build", "fonts", name), max(8, int(size * K)))


BOLD = lambda s: F("Poppins-Bold.ttf", s)
XB = lambda s: F("Poppins-ExtraBold.ttf", s)
SEMI = lambda s: F("Poppins-SemiBold.ttf", s)
REG = lambda s: F("Poppins-Regular.ttf", s)
SERIF = lambda s: F("Fraunces-Italic.ttf", s)
clamp = lambda x, a=0.0, b=1.0: max(a, min(b, x))
ease = lambda t: 1 - (1 - clamp(t)) ** 3


def frames(shot):
    import time
    fs = sorted(glob.glob(J("build", "reel2", shot, "f_*.png")) + glob.glob(J("build", "reel2", shot, "f_*.jpg")))
    # skip a frame Blender may still be writing, or one a full disk left truncated
    return [f for f in fs if time.time() - os.path.getmtime(f) > 8 and os.path.getsize(f) > 100_000]


_cache = {}


def load(path):
    if path not in _cache:
        if len(_cache) > 3:                          # each frame is read once: keep RAM low
            _cache.clear()
        _cache[path] = Image.open(path).convert("RGB").resize((W, H), Image.LANCZOS if not PREVIEW else Image.BILINEAR)
    return _cache[path]


def txt(d, xy, s, f, fill, a=1.0, anchor="la", spacing=0):
    if a <= 0:
        return
    if spacing:
        x, y = xy
        for ch in s:
            d.text((x, y), ch, font=f, fill=fill + (int(255 * a),), anchor=anchor)
            x += f.getlength(ch) + spacing
    else:
        d.text(xy, s, font=f, fill=fill + (int(255 * a),), anchor=anchor)


VIG = None


def vignette(im):
    global VIG
    if VIG is None:
        yy, xx = np.mgrid[0:H, 0:W]
        VIG = np.clip(1 - 0.30 * (((xx - W / 2) / (W * .6)) ** 2 + ((yy - H / 2) / (H * .6)) ** 2), 0.5, 1)[..., None].astype(np.float32)
    a = np.asarray(im).astype(np.float32) * VIG
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def lower_third(im, title, sub, t, dur):
    """Title + subtitle, bottom-left, rising in after 0.35 s and fading before the cut."""
    a_in = ease((t - 0.35) / 0.5)
    a_out = 1 - clamp((t - (dur - 0.7)) / 0.45)
    a = a_in * a_out
    if a <= 0:
        return im
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    # a soft dark gradient behind the text for legibility
    g = np.zeros((H, W), np.float32)
    g[int(H * .62):] = np.linspace(0, 0.55, H - int(H * .62))[:, None]
    ov.putalpha(Image.fromarray((g * 255 * a).astype(np.uint8)))
    im = Image.alpha_composite(im.convert("RGBA"), ov)
    d = ImageDraw.Draw(im)
    x, y = int(110 * K), int(H - 190 * K)
    dy = int((1 - a_in) * 26 * K)
    d.rectangle([x, y + dy, x + int(8 * K), y + dy + int(96 * K)], fill=WINE + (int(255 * a),))
    txt(d, (x + int(30 * K), y + dy - int(6 * K)), title, BOLD(58), (255, 255, 255), a)
    txt(d, (x + int(32 * K), y + dy + int(72 * K)), sub, REG(28), (235, 222, 224), a)
    return im.convert("RGB")


def intro(t):
    base = load(frames("establish")[0]).filter(ImageFilter.GaussianBlur(18 * K))
    a = np.asarray(base).astype(np.float32) * 0.35 + np.array(WINE, np.float32) * 0.18
    im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).convert("RGBA")
    d = ImageDraw.Draw(im)
    word = "NOVA-BAND"
    f = XB(118)
    total = sum(f.getlength(c) for c in word) + 14 * K * (len(word) - 1)
    x = (W - total) / 2
    for i, ch in enumerate(word):
        e = ease((t - 0.3 - i * 0.06) / 0.6)
        d.text((x, H / 2 - 40 * K + (1 - e) * 40 * K), ch, font=f, fill=(WINE if ch == "-" else (255, 255, 255)) + (int(255 * e),), anchor="ls")
        x += f.getlength(ch) + 14 * K
    e2 = ease((t - 1.2) / 0.6)
    txt(d, (W / 2, H / 2 + 40 * K), "An AIoT upper-arm wearable for runners", SERIF(40), CREAM, e2, anchor="mm")
    e3 = ease((t - 1.7) / 0.6)
    txt(d, (W / 2, H - 90 * K), "ISIF 2026  ·  SMA NEGERI 1 SURAKARTA", SEMI(22), ROSE, e3, anchor="mm")
    fade_in = clamp(t / 0.6)
    return Image.blend(Image.new("RGB", (W, H)), im.convert("RGB"), fade_in)


def outro(t):
    im = Image.new("RGB", (W, H), WINE)
    a = np.asarray(im).astype(np.float32)
    yy, xx = np.mgrid[0:H, 0:W]
    a *= np.clip(1.15 - 0.45 * (((xx - W * .5) / W) ** 2 + ((yy - H * .45) / H) ** 2) * 2.2, 0.55, 1.15)[..., None]
    im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).convert("RGBA")
    d = ImageDraw.Draw(im)
    e = ease(t / 0.7)
    txt(d, (W / 2, H * .36), "Nova-Band", XB(120), (255, 255, 255), e, anchor="mm")
    txt(d, (W / 2, H * .36 + 95 * K), "Monitor. Analyze. Improve.", SERIF(44), CREAM, ease((t - .4) / .6), anchor="mm")
    e2 = ease((t - .9) / .6)
    bw, bh = 420 * K, 70 * K
    d.rounded_rectangle([W / 2 - bw / 2, H * .6 - bh / 2, W / 2 + bw / 2, H * .6 + bh / 2], int(35 * K), fill=(255, 255, 255, int(255 * e2)))
    txt(d, (W / 2, H * .6), "novaband-id.web.app", BOLD(30), WINE, e2, anchor="mm")
    e3 = ease((t - 1.3) / .6)
    txt(d, (W / 2, H * .75), "Maheswara · Almira · Azra · Dela · Rizkyta · Satriya  —  SMA Negeri 1 Surakarta", REG(24), (241, 217, 217), e3, anchor="mm")
    txt(d, (W / 2, H - 60 * K), "Gym, runner and props: Sketchfab models (CC-BY), see credits  ·  rendered in Blender Cycles", REG(19), (226, 180, 184), e3, anchor="mm")
    fade_out = 1 - clamp((t - (OUTRO - 0.6)) / 0.6)
    return Image.blend(Image.new("RGB", (W, H)), im.convert("RGB"), fade_out)


def timeline():
    """Yields PIL frames in order. The last XF frames of a shot are held back and
    blended into the first XF frames of the next one."""
    for i in range(int(INTRO * FPS)):
        yield intro(i / FPS)
    shots = [(sh, t, st, frames(sh)) for sh, t, st in SHOTS]
    shots = [x for x in shots if x[3] or print("missing shot", x[0])]
    pending = None
    for si, (shot, title, sub, fs) in enumerate(shots):
        dur, n, last = len(fs) / FPS, len(fs), si == len(shots) - 1
        held = []
        for i, f in enumerate(fs):
            im = lower_third(vignette(load(f)), title, sub, i / FPS, dur)
            if pending and i < len(pending):
                im = Image.blend(pending[i], im, (i + 1) / (len(pending) + 1))
            if not last and i >= n - XF:
                held.append(im)
            else:
                yield im
        pending = held
    for i in range(int(OUTRO * FPS)):
        yield outro(i / FPS)


def main():
    ff = find_ffmpeg()
    out = J("build", "reel2", "preview.mp4") if PREVIEW else J("assets", "novaband-showreel-gym.mp4")
    if "--out" in sys.argv:                           # e.g. a work-in-progress cut
        out = sys.argv[sys.argv.index("--out") + 1]
    step = 5 if PREVIEW else 1
    cmd = [ff, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H),
           "-r", str(FPS / step), "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "20",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", out]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    n = 0
    poster = None
    for i, im in enumerate(timeline()):
        if i % step:
            continue
        if n == int((INTRO + 7.5) * FPS / step):
            poster = im
        p.stdin.write(im.tobytes())
        n += 1
    p.stdin.close()
    p.wait()
    print("wrote", out, n, "frames", "%.1f s" % (n * step / FPS))
    if not PREVIEW and "--out" not in sys.argv:
        (poster or im).save(J("assets", "novaband-showreel-gym-poster.jpg"), quality=86)
        subprocess.run([ff, "-y", "-loglevel", "error", "-i", out, "-c:v", "libvpx-vp9", "-b:v", "0", "-crf", "34",
                        "-row-mt", "1", "-deadline", "good", "-cpu-used", "2", J("assets", "novaband-showreel-gym.webm")], check=True)
        print("wrote webm + poster")


if __name__ == "__main__":
    main()
