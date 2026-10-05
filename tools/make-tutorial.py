"""
"Cara pakai Nova-Band": 20-second 3D tutorial (5 steps x 4 s).

    python blender/tutorial.py                 # 3D shots -> build/tut/s1..s5
    python tools/make-tutorial.py [--preview]  # -> assets/novaband-tutorial.{mp4,webm} + poster

Left: the Blender shot (detailed Nova). Right: big step number, title, caption,
and for steps 3-5 the Android phone playing the real app. Bottom: the five
steps as a progress rail. Voice: build/tut_vo/s*.mp3 (edge-tts), each trimmed
of silence and fitted inside its 4 seconds.
"""
import glob
import importlib.util
import json
import math
import os
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
J = lambda *p: os.path.join(ROOT, *p)
spec = importlib.util.spec_from_file_location("sr", J("tools", "make-app-showreel.py"))
SR = importlib.util.module_from_spec(spec)
spec.loader.exec_module(SR)
E = SR.E
PREVIEW = E.PREVIEW
W, H, S = E.W, E.H, E.S
FPS, STEP = 24, 4.0
NEON, ROSE, CREAM, CYAN, WHITE = E.NEON, E.ROSE, E.CREAM, E.CYAN, E.WHITE
XB, BOLD, SEMI, REG = E.XB, E.BOLD, E.SEMI, E.REG
appear, clamp = E.appear, E.clamp

STEPS = [  # shot, short label, title, caption
    ("s1", "Nyalakan", "Nyalakan band", "Tekan tombol samping. Layar menyala dan siap dipasangkan."),
    ("s2", "Pasang", "Pasang di lengan atas", "Lengan kiri, layar menghadap luar. Kencangkan strap secukupnya."),
    ("s3", "Hubungkan", "Hubungkan aplikasi", "Buka novaband-id.web.app, tekan Hubungkan, pilih Bluetooth."),
    ("s4", "Lari", "Mulai sesi & lari", "Tekan Mulai Sesi. Data tampil di band dan di ponsel."),
    ("s5", "Pantau", "Pantau & waspada", "Detak jantung lewat batas? Band memberi peringatan, pelatih ikut tahu."),
]


def shot(k, f):
    fs = sorted(glob.glob(J("build", "tut", STEPS[k][0], "f_*.png")))
    if not fs:
        return None
    im = Image.open(fs[min(f, len(fs) - 1)]).convert("RGBA")
    size = S(1080)
    return im.resize((size, size), Image.BILINEAR if PREVIEW else Image.LANCZOS)


def phone_t(k, u):
    """Recording time to show on the phone for step k at progress u (0..1)."""
    mk = SR.MK
    if k == 2:
        return mk["connect"] + 0.9 + u * 1.2          # stay on the Bluetooth / USB / simulasi dialog
    if k == 3:
        return mk["run"] + 3.4 + u * 4
    return mk["alert"] + 1.2 + u * 4


def notification(im, x, y, a):
    if a <= 0:
        return
    w, h = S(640), S(150)
    E.glass(im, (x, y, x + w, y + h), a, tint=(70, 12, 22), edge=(255, 90, 100))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([x + S(24), y + S(30), x + S(104), y + S(110)], S(22), fill=NEON + (int(255 * a),))
    E.text(d, (x + S(64), y + S(70)), "N", XB(44), WHITE, a, "mm")
    E.spaced(d, (x + S(126), y + S(26)), "NOVA-BAND · PERINGATAN", SEMI(18), ROSE, a, 3)
    E.text(d, (x + S(124), y + S(52)), "Detak jantung 188 bpm", BOLD(32), WHITE, a)
    E.text(d, (x + S(124), y + S(100)), "Turunkan intensitas, atur napas", REG(24), CREAM, a)


def rail(im, k, u):
    d = ImageDraw.Draw(im)
    x0, y, w = S(140), S(985), S(1640)
    seg = w / 5
    for i, (_, lab, _, _) in enumerate(STEPS):
        x = x0 + i * seg
        done = i < k or (i == k and u >= 1)
        cur = i == k
        tr = Image.new("RGBA", im.size, (0, 0, 0, 0))
        ImageDraw.Draw(tr).rounded_rectangle([x + S(6), y, x + seg - S(6), y + S(6)], S(3), fill=(255, 255, 255, 40))
        im.alpha_composite(tr)
        d = ImageDraw.Draw(im)
        fill = u if cur else (1.0 if i < k else 0.0)
        if fill > 0:
            d.rounded_rectangle([x + S(6), y, x + S(6) + (seg - S(12)) * fill, y + S(6)], S(3), fill=NEON + (255,))
        col = WHITE if cur or done or i < k else (150, 120, 128)
        cx = x + S(30)
        d.ellipse([cx - S(17), y - S(52), cx + S(17), y - S(18)],
                  fill=(NEON if (cur or i < k) else (60, 30, 40)) + (255,))
        E.text(d, (cx, y - S(35)), str(i + 1), BOLD(20), WHITE, 1, "mm")
        E.text(d, (cx + S(28), y - S(35)), lab, SEMI(24), col, 1, "lm")


def frame(gt):
    k = min(int(gt / STEP), 4)
    t = gt - k * STEP
    u = t / STEP
    im = E.background(gt)
    sh = shot(k, int(t * FPS))
    if sh is not None:
        if t > STEP - 0.25 and k < 4:                   # quick dissolve into the next shot
            nx = shot(k + 1, 0)
            if nx is not None:
                sh = Image.blend(sh, nx, (t - (STEP - 0.25)) / 0.25)
        im.alpha_composite(sh, (S(60), S(-20)))
    d = ImageDraw.Draw(im)
    # header
    d.rounded_rectangle([S(60), S(48), S(112), S(100)], S(14), fill=NEON + (255,))
    E.text(d, (S(86), S(74)), "N", XB(32), WHITE, 1, "mm")
    E.text(d, (S(128), S(74)), "Cara pakai Nova-Band", XB(32), WHITE, 1, "lm")
    # step copy
    _, _, title, cap = STEPS[k]
    a = appear(t, 0.05, 0.35) * (1 - clamp((t - (STEP - 0.2)) / 0.2) if k < 4 else 1)
    x = S(1180)
    E.glow_text(im, (x - S(6), S(150)), "%02d" % (k + 1), XB(150), NEON, a, 24)
    d = ImageDraw.Draw(im)
    E.text(d, (x, S(345)), title, XB(60), WHITE, a)
    words, line, ly = cap.split(), "", S(430)
    for w_ in words:
        if REG(30).getlength(line + " " + w_) > S(640):
            E.text(d, (x, ly), line.strip(), REG(30), CREAM, a)
            line, ly = w_, ly + S(44)
        else:
            line += " " + w_
    E.text(d, (x, ly), line.strip(), REG(30), CREAM, a)
    if k >= 2:
        pa = appear(t, 0.25, 0.5) * a
        ph = SR.phone(phone_t(k, u), -16, S(400))
        SR.place_phone(im, ph, S(1400), ly + S(235), pa)
    if k == 4:
        b = appear(t, 1.2, 0.5)
        notification(im, S(1150) + int((1 - b) * S(120)), ly + S(150), b)
    rail(im, k, clamp(u * 1.0))
    if gt > 19.0:                                       # end card
        e = clamp((gt - 19.0) / 0.5)
        ov = Image.new("RGBA", im.size, (14, 5, 9, int(200 * e)))
        im.alpha_composite(ov)
        E.glow_text(im, (S(560), S(400)), "Nova-Band", XB(140), WHITE, e, 26)
        d = ImageDraw.Draw(im)
        E.text(d, (S(960), S(620)), "Siap lari lebih aman.", E.SERIF(56), CREAM, e, "mm")
    return im.convert("RGB")


def voice_track(ff, total):
    """Trim each line's silence, fit it in 3.7 s, place it at its step start."""
    info = json.load(open(J("build", "tut_vo", "lines.json")))
    inputs, filt = [], []
    for i, (key, _) in enumerate(info["lines"]):
        src = J("build", "tut_vo", key + ".mp3")
        clean = J("build", "tut_vo", key + "_trim.wav")
        subprocess.run([ff, "-y", "-loglevel", "error", "-i", src, "-af",
                        "silenceremove=start_periods=1:start_threshold=-45dB,areverse,"
                        "silenceremove=start_periods=1:start_threshold=-45dB,areverse", clean], check=True)
        r = subprocess.run([ff, "-i", clean, "-f", "null", "-"], capture_output=True, text=True).stderr
        import re
        m = re.findall(r"time=(\d+):(\d+):([\d.]+)", r)
        dur = float(m[-1][2]) + 60 * float(m[-1][1]) if m else 3.5
        tempo = max(1.0, dur / 3.6)
        inputs += ["-i", clean]
        ms = int((i * STEP + 0.15) * 1000)
        filt.append("[%d:a]atempo=%.3f,aresample=44100,adelay=%d|%d,volume=1.7[v%d]" % (i + 1, tempo, ms, ms, i))
    return inputs, filt


def main():
    SR.setup()
    total = 5 * STEP
    ff = E.R.find_ffmpeg()
    step = 3 if PREVIEW else 1
    silent = J("build", "tutorial_preview.mp4" if PREVIEW else "tutorial_video.mp4")
    p = subprocess.Popen([ff, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H),
                          "-r", str(FPS / step), "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "18",
                          "-pix_fmt", "yuv420p", silent], stdin=subprocess.PIPE)
    poster = None
    for i in range(0, int(total * FPS), step):
        im = frame(i / FPS)
        if poster is None and i / FPS >= 9.5:
            poster = im
        p.stdin.write(im.tobytes())
    p.stdin.close()
    p.wait()
    if PREVIEW:
        print("wrote", silent)
        return
    pad = J("build", "tutorial_pad.wav")
    E.pad_music(total, pad)
    vin, vf = voice_track(ff, total)
    filt = vf + ["[%d:a]volume=0.45[pad]" % (len(vf) + 1),
                 "[pad]" + "".join("[v%d]" % i for i in range(len(vf))) +
                 "amix=inputs=%d:normalize=0:duration=first,alimiter=limit=0.95[a]" % (len(vf) + 1)]
    out = J("assets", "novaband-tutorial.mp4")
    subprocess.run([ff, "-y", "-loglevel", "error", "-i", silent] + vin + ["-i", pad, "-filter_complex", ";".join(filt),
                    "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest",
                    "-movflags", "+faststart", out], check=True)
    poster.save(J("assets", "novaband-tutorial-poster.jpg"), quality=86)
    subprocess.run([ff, "-y", "-loglevel", "error", "-i", out, "-c:v", "libvpx-vp9", "-b:v", "0", "-crf", "34",
                    "-row-mt", "1", "-deadline", "good", "-cpu-used", "2", "-c:a", "libopus", "-b:a", "96k",
                    J("assets", "novaband-tutorial.webm")], check=True)
    print("wrote", out)


if __name__ == "__main__":
    main()
