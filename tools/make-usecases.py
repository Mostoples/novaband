"""
Nova-Band use-case film: cut the six Cycles scenes (blender/usecases.py ->
build/usecases/<scene>/f_####.jpg) with a numbered title, a live on-screen
widget per use case, cross-fades, an opening and an end card.

    python tools/make-usecases.py              # -> assets/novaband-usecases.{mp4,webm} + poster
    python tools/make-usecases.py --preview    # every 5th frame, 960 px
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
spec = importlib.util.spec_from_file_location("reel", J("tools", "make-showreel2.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)                      # fonts, easing, vignette, ffmpeg finder
W, H, K, FPS, XF = R.W, R.H, R.K, R.FPS, R.XF
PREVIEW = R.PREVIEW
WINE, CREAM, ROSE = R.WINE, R.CREAM, R.ROSE
RED, GREEN, AMBER, BLUE = (255, 77, 94), (59, 224, 122), (255, 179, 71), (90, 180, 255)
ease, clamp = R.ease, R.clamp

SCENES = [  # folder, title, subtitle
    ("park_run", "Morning run", "Live heart rate and PPG, right on the upper arm"),
    ("treadmill", "Treadmill session", "Pace, distance and energy on the band's own screen"),
    ("pushups", "Strength training", "The IMU follows every repetition"),
    ("coach", "Early warning", "Heart rate crosses the limit: the coach knows at once"),
    ("recovery", "Recovery", "The readiness score says when to train hard again"),
    ("walk", "Everyday activity", "Resting heart rate, steps and calories, all day"),
]
INTRO, OUTRO = 3.2, 4.5


def frames(scene):
    return sorted(glob.glob(J("build", "usecases", scene, "f_*.jpg")) + glob.glob(J("build", "usecases", scene, "f_*.png")))


def S(v):
    return int(v * K)


# ---------------------------------------------------------------- widgets (drawn on an RGBA overlay)
def card(d, box, a, radius=26):
    x0, y0, x1, y1 = box
    d.rounded_rectangle(box, S(radius), fill=(22, 10, 14, int(200 * a)), outline=(255, 255, 255, int(70 * a)), width=max(1, S(2)))


def text(d, xy, s, f, fill, a, anchor="la"):
    if a > 0:
        d.text(xy, s, font=f, fill=fill + (int(255 * a),), anchor=anchor)


def heart(d, cx, cy, r, col, a):
    """A heart from two circles and a triangle."""
    c = col + (int(255 * a),)
    d.ellipse([cx - r, cy - r * .9, cx, cy + r * .1], fill=c)
    d.ellipse([cx, cy - r * .9, cx + r, cy + r * .1], fill=c)
    d.polygon([(cx - r * .98, cy - r * .3), (cx + r * .98, cy - r * .3), (cx, cy + r * 1.05)], fill=c)


def ppg(t, p):
    ph = (t * 155 / 60 + p) % 1
    return math.exp(-((ph - .16) / .065) ** 2) + .38 * math.exp(-((ph - .47) / .085) ** 2)


def widget(scene, d, t, dur):
    a = ease((t - 0.7) / 0.5) * (1 - clamp((t - (dur - 0.6)) / 0.4))
    if a <= 0:
        return
    dx = int((1 - ease((t - 0.7) / 0.5)) * S(60))
    x1 = W - S(80) + dx
    if scene == "park_run":
        box = (x1 - S(430), S(90), x1, S(330))
        card(d, box, a)
        beat = math.exp(-((t * 155 / 60) % 1) * 9)
        heart(d, box[0] + S(62), box[1] + S(78), S(30 + 5 * beat), RED, a)
        text(d, (box[0] + S(115), box[1] + S(38)), "155", R.XB(76), (255, 255, 255), a)
        text(d, (box[0] + S(282), box[1] + S(78)), "bpm", R.SEMI(28), ROSE, a)
        text(d, (box[0] + S(118), box[1] + S(130)), "ZONE 3  ·  AEROBIC", R.SEMI(20), GREEN, a)
        pts = []
        for i in range(120):
            x = box[0] + S(36) + i * (box[2] - box[0] - S(72)) / 119
            y = box[3] - S(38) - ppg(t - (119 - i) / 60, 0) * S(48)
            pts.append((x, y))
        d.line(pts, fill=(255, 107, 122, int(255 * a)), width=max(1, S(3)), joint="curve")
    elif scene == "treadmill":
        box = (x1 - S(420), S(90), x1, S(390))
        card(d, box, a)
        rows = [("PACE", "5:21", "/km"), ("DISTANCE", "%.2f" % (1.84 + t * 0.0033), "km"), ("ENERGY", "%d" % (128 + t * 0.9), "kcal")]
        for i, (k, v, u) in enumerate(rows):
            y = box[1] + S(34) + i * S(88)
            text(d, (box[0] + S(40), y), k, R.SEMI(20), ROSE, a)
            text(d, (box[0] + S(40), y + S(26)), v, R.BOLD(46), (255, 255, 255), a)
            w = R.BOLD(46).getlength(v)
            text(d, (box[0] + S(52) + w, y + S(46)), u, R.REG(24), ROSE, a)
    elif scene == "pushups":
        box = (x1 - S(360), S(90), x1, S(320))
        card(d, box, a)
        reps = 9 + int(t / 2.12)
        text(d, (box[0] + S(40), box[1] + S(34)), "REPETITIONS · IMU", R.SEMI(20), ROSE, a)
        text(d, (box[0] + S(40), box[1] + S(66)), str(reps), R.XB(96), (255, 255, 255), a)
        text(d, (box[0] + S(40), box[1] + S(190)), "HR 128 bpm  ·  form steady", R.REG(22), CREAM, a)
    elif scene == "coach":
        pulse = 0.5 + 0.5 * math.sin(t * 7)
        box = (x1 - S(560), S(90), x1, S(290))
        card(d, box, a)
        d.rounded_rectangle((box[0] + S(28), box[1] + S(30), box[0] + S(92), box[1] + S(94)), S(16), fill=WINE + (int(255 * a),))
        text(d, (box[0] + S(60), box[1] + S(62)), "N", R.XB(40), (255, 255, 255), a, anchor="mm")
        text(d, (box[0] + S(112), box[1] + S(30)), "NOVA-BAND  ·  now", R.SEMI(19), ROSE, a)
        text(d, (box[0] + S(112), box[1] + S(56)), "Heart rate above limit", R.BOLD(34), (255, 255, 255), a)
        text(d, (box[0] + S(112), box[1] + S(104)), "Raka  ·  188 bpm  ·  Zone 5  ·  Treadmill 2", R.REG(23), CREAM, a)
        d.rounded_rectangle((box[0] + S(28), box[3] - S(38), box[2] - S(28), box[3] - S(26)), S(6),
                            fill=RED + (int(255 * a * (0.55 + 0.45 * pulse)),))
    elif scene == "recovery":
        box = (x1 - S(560), S(90), x1, S(330))
        card(d, box, a)
        cx, cy, r = box[0] + S(120), box[1] + S(120), S(80)
        v = 0.82 * ease((t - 0.9) / 1.4)
        d.arc((cx - r, cy - r, cx + r, cy + r), 135, 405, fill=(255, 255, 255, int(40 * a)), width=S(16))
        d.arc((cx - r, cy - r, cx + r, cy + r), 135, 135 + 270 * v, fill=GREEN + (int(255 * a),), width=S(16))
        text(d, (cx, cy - S(4)), str(int(round(v * 100))), R.XB(58), (255, 255, 255), a, anchor="mm")
        text(d, (cx, cy + S(44)), "/ 100", R.REG(20), ROSE, a, anchor="mm")
        text(d, (box[0] + S(240), box[1] + S(60)), "READINESS", R.SEMI(20), ROSE, a)
        text(d, (box[0] + S(240), box[1] + S(88)), "Go for tempo", R.BOLD(34), (255, 255, 255), a)
        text(d, (box[0] + S(240), box[1] + S(136)), "HRV 68 ms · sleep 7h 40m", R.REG(21), CREAM, a)
    elif scene == "walk":
        box = (x1 - S(420), S(90), x1, S(330))
        card(d, box, a)
        steps = 6240 + int(t * 1.9)
        text(d, (box[0] + S(40), box[1] + S(34)), "STEPS TODAY", R.SEMI(20), ROSE, a)
        text(d, (box[0] + S(40), box[1] + S(62)), "{:,}".format(steps), R.XB(70), (255, 255, 255), a)
        text(d, (box[0] + S(40), box[1] + S(160)), "Resting HR 65 bpm  ·  312 kcal", R.REG(23), CREAM, a)


def badge(d, n, t, dur):
    a = ease((t - 0.25) / 0.4) * (1 - clamp((t - (dur - 0.6)) / 0.4))
    if a <= 0:
        return
    s = "USE CASE %02d / %02d" % (n, len(SCENES))
    f = R.SEMI(20)
    w = f.getlength(s)
    x, y = S(110), S(90)
    d.rounded_rectangle((x, y, x + w + S(40), y + S(44)), S(22), fill=WINE + (int(235 * a),))
    text(d, (x + S(20), y + S(22)), s, f, (255, 255, 255), a, anchor="lm")


def compose(scene, n, im, t, dur):
    title, sub = next((tt, ss) for sc, tt, ss in SCENES if sc == scene)
    im = R.lower_third(R.vignette(im), title, sub, t, dur)
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    badge(d, n, t, dur)
    widget(scene, d, t, dur)
    return Image.alpha_composite(im.convert("RGBA"), ov).convert("RGB")


def intro(t):
    first = frames("park_run")[0]
    base = R.load(first).filter(ImageFilter.GaussianBlur(16 * K))
    arr = np.asarray(base).astype(np.float32) * 0.36 + np.array(WINE, np.float32) * 0.2
    im = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).convert("RGBA")
    d = ImageDraw.Draw(im)
    e = ease((t - 0.3) / 0.6)
    text(d, (W / 2, H / 2 - S(70)), "NOVA-BAND IN USE", R.SEMI(26), ROSE, e, anchor="mm")
    text(d, (W / 2, H / 2 + S(10)), "Six moments, one band", R.XB(96), (255, 255, 255), ease((t - 0.6) / 0.6), anchor="mm")
    text(d, (W / 2, H / 2 + S(95)), "Run · train · recover · everyday life", R.SERIF(40), CREAM, ease((t - 1.1) / 0.6), anchor="mm")
    return Image.blend(Image.new("RGB", (W, H)), im.convert("RGB"), clamp(t / 0.6) * (1 - clamp((t - (INTRO - 0.35)) / 0.35) * 0.0))


def main():
    ff = R.find_ffmpeg()
    out = J("build", "usecases", "preview.mp4") if PREVIEW else J("assets", "novaband-usecases.mp4")
    step = 5 if PREVIEW else 1
    cmd = [ff, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H),
           "-r", str(FPS / step), "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "20",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", out]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    def timeline():
        for i in range(int(INTRO * FPS)):
            yield intro(i / FPS)
        shots = [(sc, frames(sc)) for sc, _, _ in SCENES]
        shots = [(sc, fs) for sc, fs in shots if fs or print("missing", sc)]
        pending = None
        for si, (sc, fs) in enumerate(shots):
            n = [s for s, _, _ in SCENES].index(sc) + 1
            dur, cnt, last = len(fs) / FPS, len(fs), si == len(shots) - 1
            held = []
            for i, f in enumerate(fs):
                im = compose(sc, n, R.load(f), i / FPS, dur)
                if pending and i < len(pending):
                    im = Image.blend(pending[i], im, (i + 1) / (len(pending) + 1))
                if not last and i >= cnt - XF:
                    held.append(im)
                else:
                    yield im
            pending = held
        for i in range(int(OUTRO * FPS)):
            yield R.outro(i / FPS)

    poster, k = None, 0
    for i, im in enumerate(timeline()):
        if i % step:
            continue
        if k == int((INTRO + 3.0) * FPS / step):
            poster = im
        p.stdin.write(im.tobytes())
        k += 1
    p.stdin.close()
    p.wait()
    print("wrote", out, k, "frames", "%.1f s" % (k * step / FPS))
    if not PREVIEW:
        (poster or im).save(J("assets", "novaband-usecases-poster.jpg"), quality=86)
        subprocess.run([ff, "-y", "-loglevel", "error", "-i", out, "-c:v", "libvpx-vp9", "-b:v", "0", "-crf", "34",
                        "-row-mt", "1", "-deadline", "good", "-cpu-used", "2", J("assets", "novaband-usecases.webm")], check=True)
        print("wrote webm + poster")


if __name__ == "__main__":
    main()
