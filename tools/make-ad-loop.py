"""
Nova-Band looping ad, vertical 9:16, 15 s, cut from original footage
(dokumentasi/ADEGAN field shoot + the running-community test).

Six 2.5 s beats; each sits in a full-width 16:9 band (the 848x478 phone clips
only need a 1.27x upscale there) over a blurred fill of the same clip, with a
headline above and a caption below. The last beat cross-fades into the first
frames of beat one and the music is exactly periodic, so the file loops
seamlessly.

    python tools/make-ad-loop.py      # -> build/promo/NovaBand_Ad_Loop_9x16.mp4
"""
import importlib.util
import os
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
J = lambda *p: os.path.join(ROOT, *p)


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, J("tools", file))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


R = load("reel", "make-showreel2.py")               # fonts + ffmpeg
AD = load("ad", "make-ad.py")                       # periodic music
FF = R.find_ffmpeg()
W, H, FPS = 1080, 1920, 25
LOOP = 15.0
XF = 8
BW, BH, BY = 1080, 608, 640                         # footage band
RED, CREAM, MUTED, WHITE = (255, 79, 99), (243, 227, 211), (215, 200, 205), (255, 255, 255)
clamp = lambda x, a=0.0, b=1.0: max(a, min(b, x))
ease = lambda x: 1 - (1 - clamp(x)) ** 3
SRC = J("dokumentasi", "ADEGAN")
A = lambda stamp: os.path.join(SRC, "WhatsApp Video 2026-10-10 at %s.mp4" % stamp)
KL = J("dokumentasi", "KOMUNITAS LARI SURAKARTA", "WhatsApp Video 2026-09-30 at 20.33.41 (1).mp4")

# clip, start, frames, rotate, kicker, headline lines, caption
BEATS = [
    (A("12.26.23"), 0.3, 71, False, "UPPER-ARM WEARABLE", ["Lari lebih", "aman."], "Pantau tubuhmu langsung dari lengan atas."),
    (A("12.25.34 (2)"), 4.2, 70, False, "CARA PAKAI", ["Pasang di", "lengan atas."], "Lebih stabil daripada di pergelangan."),
    (A("12.25.34"), 6.0, 71, False, "AKURAT SAAT BERLARI", ["Sinyal tetap", "bersih."], "2,5–3,5% MAPE terhadap alat acuan"),
    (A("12.25.33"), 6.0, 70, True, "REAL-TIME", ["Detak jantung,", "setiap langkah."], "Pace · kadens · 5 zona intensitas"),
    (KL, 0.8, 71, False, "SHARED SAFETY NET", ["Pelatih ikut", "memantau."], "Peringatan dini saat melewati batas aman."),
    (A("12.26.23"), 4.0, 70, False, "", ["Nova-Band"], "Monitor. Analyze. Improve."),
]
assert sum(b[2] for b in BEATS) - XF * len(BEATS) == int(LOOP * FPS)


def frames(path, start, n, rot):
    """Two outputs per frame from one decode: sharp 16:9 band + blurred 9:16 fill."""
    r = "transpose=2," if rot else ""
    vf = ("%ssplit[a][b];[a]scale=%d:%d:flags=lanczos:force_original_aspect_ratio=increase,crop=%d:%d,"
          "unsharp=5:5:0.6:5:5:0,eq=contrast=1.07:saturation=1.12,setsar=1,fps=%d[band];"
          "[b]scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,boxblur=40:3,eq=brightness=-0.25:saturation=0.8,"
          "setsar=1,fps=%d[bg];[bg][band]overlay=0:%d" % (r, BW, BH, BW, BH, FPS, W, H, W, H, FPS, BY))
    p = subprocess.Popen([FF, "-v", "error", "-ss", "%.3f" % start, "-i", path, "-t", "%.3f" % (n / FPS + 0.5),
                          "-filter_complex", vf, "-an", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    last = None
    for _ in range(n):
        b = p.stdout.read(W * H * 3)
        if len(b) == W * H * 3:
            last = np.frombuffer(b, np.uint8).reshape(H, W, 3)
        yield last
    p.stdout.close()
    p.kill()


def band_frame():
    """Soft shadow + thin red rules around the footage band."""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle((0, BY - 40, W, BY + BH + 40), fill=(0, 0, 0, 140))
    im = im.filter(ImageFilter.GaussianBlur(30))
    d = ImageDraw.Draw(im)
    d.rectangle((0, BY - 3, W, BY), fill=RED + (255,))
    d.rectangle((0, BY + BH, W, BY + BH + 3), fill=RED + (255,))
    return im


FRAME = band_frame()


def T(d, xy, s, f, fill, a, anchor="la"):
    if a > 0:
        d.text(xy, s, font=f, fill=tuple(fill) + (int(255 * clamp(a)),), anchor=anchor)


def logo(d, cx, y, size, a):
    f = R.XB(size)
    tw = d.textlength("Nova-Band", font=f)
    x = cx - tw / 2
    T(d, (x, y), "Nova", f, WHITE, a, "lm")
    T(d, (x + d.textlength("Nova", font=f), y), "-", f, RED, a, "lm")
    T(d, (x + d.textlength("Nova-", font=f), y), "Band", f, WHITE, a, "lm")


def overlay(im, k, f, n):
    t, dur = f / FPS, n / FPS
    _, _, _, _, kick, lines, cap = BEATS[k]
    im.paste(FRAME, (0, 0), FRAME)
    d = ImageDraw.Draw(im, "RGBA")
    # story-style progress bar
    seg = (W - 120 - 5 * 12) / 6
    for j in range(6):
        x = 60 + j * (seg + 12)
        d.rounded_rectangle((x, 70, x + seg, 76), 3, fill=(255, 255, 255, 70))
        fill = 1.0 if j < k else (clamp(t / dur) if j == k else 0)
        if fill > 0:
            d.rounded_rectangle((x, 70, x + seg * fill, 76), 3, fill=WHITE + (235,))
    out = clamp((dur - t) / 0.25)
    if lines == ["Nova-Band"]:                          # call to action
        a = ease((t - 0.25) / 0.5) * out
        logo(d, W // 2, 420 + int((1 - a) * 30), 150, a)
        T(d, (W // 2, 545), cap, R.SERIF(56), CREAM, ease((t - 0.6) / 0.5) * out, "mm")
        b = ease((t - 0.9) / 0.5) * out
        d.rounded_rectangle((W // 2 - 300, BY + BH + 120, W // 2 + 300, BY + BH + 220), 50, fill=RED + (int(255 * b),))
        T(d, (W // 2, BY + BH + 170), "novaband-id.web.app", R.BOLD(40), WHITE, b, "mm")
        T(d, (W // 2, BY + BH + 290), "Tim Peneliti SMA Negeri 1 Surakarta · ISIF 2026", R.REG(30), MUTED, b, "mm")
        return
    T(d, (80, 250), kick, R.SEMI(30), RED, ease((t - 0.1) / 0.4) * out)
    for j, ln in enumerate(lines):
        a = ease((t - 0.15 - 0.12 * j) / 0.45) * out
        T(d, (76 - int((1 - a) * 40), 300 + j * 120), ln, R.XB(104), WHITE, a)
    a = ease((t - 0.5) / 0.45) * out
    T(d, (80, BY + BH + 70), cap, R.SEMI(40), CREAM, a)
    logo(d, W // 2, H - 170, 64, 0.95)
    T(d, (W // 2, H - 105), "novaband-id.web.app", R.REG(28), MUTED, 0.9, "mm")


def beat_frames(k):
    path, start, n, rot = BEATS[k][:4]
    for f, a in enumerate(frames(path, start, n, rot)):
        im = Image.fromarray(np.array(a))
        overlay(im, k, f, n)
        yield np.asarray(im)


def main():
    os.makedirs(J("build", "promo"), exist_ok=True)
    AD.DUR = LOOP
    wav = J("build", "promo", "ad_loop.wav")
    AD.loop_music(wav)
    out = J("build", "promo", "NovaBand_Ad_Loop_9x16.mp4")
    enc = subprocess.Popen([FF, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H), "-r", str(FPS),
                            "-i", "-", "-i", wav, "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-t", "%.2f" % LOOP, out], stdin=subprocess.PIPE)
    head, tail = [], []
    for k in range(len(BEATS)):
        n = BEATS[k][2]
        buf = []
        for f, fr in enumerate(beat_frames(k)):
            if k == 0 and f < XF:
                head.append(fr)                         # shown at the very end, blended over the last beat
                continue
            if f < len(tail):
                w = (f + 1) / (len(tail) + 1)
                fr = (tail[f].astype(np.float32) * (1 - w) + fr.astype(np.float32) * w).astype(np.uint8)
            if f >= n - XF:
                buf.append(fr)
                continue
            enc.stdin.write(np.ascontiguousarray(fr).tobytes())
        tail = buf
        print("beat %d/%d" % (k + 1, len(BEATS)), flush=True)
    for f in range(XF):                                 # close the loop
        w = (f + 1) / (XF + 1)
        fr = (tail[f].astype(np.float32) * (1 - w) + head[f].astype(np.float32) * w).astype(np.uint8)
        enc.stdin.write(np.ascontiguousarray(fr).tobytes())
    enc.stdin.close()
    enc.wait()
    print(out)


if __name__ == "__main__":
    main()
