"""
Nova-Band app showreel on an Android phone mockup (16:9, ~58 s).

    python tools/record-app.py                 # real app recording -> build/app_rec/
    python tools/make-app-showreel.py          # -> assets/novaband-app-showreel.{mp4,webm} + poster
    python tools/make-app-showreel.py --preview

The phone is drawn here (Pixel-style: punch-hole camera, status bar, gesture
pill, side keys) and tilted in perspective; the screen plays the recording,
resampled from the screencast timestamps. Background, cards and type come
from tools/make-nova-explainer.py so both films share one look.
"""
import bisect
import importlib.util
import json
import math
import os
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
J = lambda *p: os.path.join(ROOT, *p)
spec = importlib.util.spec_from_file_location("nx", J("tools", "make-nova-explainer.py"))
E = importlib.util.module_from_spec(spec)
spec.loader.exec_module(E)
R = E.R
W, H, K, S = E.W, E.H, E.K, E.S
FPS = 24
PREVIEW = E.PREVIEW
NEON, ROSE, CREAM, CYAN, WHITE = E.NEON, E.ROSE, E.CREAM, E.CYAN, E.WHITE
XB, BOLD, SEMI, REG = E.XB, E.BOLD, E.SEMI, E.REG
ease, clamp = E.ease, E.clamp

REC = J("build", "app_rec")
FR = json.load(open(os.path.join(REC, "frames.json")))
MK = json.load(open(os.path.join(REC, "marks.json")))

# scene: (key, rec start, rec end, chip, title line 1, title line 2, description, pills)
SCENES = [
    ("home", MK["home"], MK["connect"], "01 · BERANDA", "Disambut", "oleh Nova.",
     "Ringkasan harian: langkah, kalori, jarak, detak jantung 24 jam, dan Readiness.",
     ["Maskot AI coach", "Data harian"]),
    ("connect", MK["connect"], MK["run"], "02 · HUBUNGKAN", "Sambungkan", "band-mu.",
     "Bluetooth LE, kabel USB, atau mode simulasi tanpa perangkat.", ["Web Bluetooth", "Web Serial"]),
    ("run", MK["run"], MK["alert"], "03 · SESI LARI", "Pantau", "real-time.",
     "Detak jantung, kadensi, pace, sinyal PPG, dan beban otot langsung dari lengan atas.",
     ["PPG", "IMU", "Zona detak"]),
    ("alert", MK["alert"], MK["ready"], "04 · EARLY WARNING", "Peringatan", "dini.",
     "Detak jantung melewati ambang: Nova memberi tanda stop, layar berkedip, pelatih ikut diberi tahu.",
     ["Ambang personal", "Shared Safety Net"]),
    ("ready", MK["ready"], MK["comm"], "05 · PERFORMA", "Readiness", "Score.",
     "Enam faktor (HRV, detak istirahat, beban latihan, pemulihan) menjadi satu skor harian.",
     ["AI advisory", "Beban 7 hari"]),
    ("comm", MK["comm"], MK["finish"], "06 · KOMUNITAS", "Lari aman", "bersama.",
     "Peta kelompok pelari dan status kesehatan anggota untuk koordinator event.",
     ["Peta live", "Status anggota"]),
    ("finish", MK["finish"], MK["end"], "07 · SELESAI", "Sesi", "tuntas!",
     "Ringkasan sesi tersimpan, Nova merayakan, saatnya pendinginan.", ["Riwayat sesi", "PWA"]),
]
INTRO, OUTRO, XF = 3.2, 4.6, 0.5

# ---------------------------------------------------------------- phone mockup
SW, SH = 824, 1830                    # screen px (412 x 915 css at 2x)
STATUS = 60
BEZ, BODY_R, SCR_R = 26, 118, 96


def status_bar():
    im = Image.new("RGBA", (SW, STATUS), (7, 4, 10, 255))
    d = ImageDraw.Draw(im)
    f = ImageFont.truetype(J("build", "fonts", "Poppins-SemiBold.ttf"), 28)   # the screen is drawn at 2x
    d.text((40, STATUS // 2 + 2), "09:41", font=f, fill=(245, 236, 238), anchor="lm")
    x = SW - 40
    d.rounded_rectangle([x - 44, 20, x - 4, 40], 6, outline=(245, 236, 238), width=3)      # battery
    d.rectangle([x - 2, 26, x + 2, 34], fill=(245, 236, 238))
    d.rounded_rectangle([x - 40, 24, x - 14, 36], 3, fill=(245, 236, 238))
    for i in range(4):                                                                      # signal
        h = 8 + i * 6
        d.rectangle([x - 106 + i * 10, 40 - h, x - 100 + i * 10, 40], fill=(245, 236, 238))
    cx, cy = x - 140, 40                                                                    # wifi
    for r in (22, 15, 8):
        d.pieslice([cx - r, cy - r, cx + r, cy + r], 225, 315, fill=(245, 236, 238))
        d.pieslice([cx - r + 5, cy - r + 5, cx + r - 5, cy + r - 5], 225, 315, fill=(7, 4, 10))
    d.ellipse([cx - 3, cy - 6, cx + 3, cy], fill=(245, 236, 238))
    return im


def phone_frame():
    """Body + bezel with a transparent screen window, and a screen mask."""
    pw, ph = SW + 2 * BEZ, SH + 2 * BEZ
    im = Image.new("RGBA", (pw + 20, ph), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    # side keys (right edge)
    for y0, y1 in ((380, 520), (600, 820)):
        d.rounded_rectangle([pw - 6, y0, pw + 10, y1], 6, fill=(70, 60, 66, 255))
    # metal rim: a vertical gradient band
    rim = Image.new("RGBA", (pw, ph))
    rd = ImageDraw.Draw(rim)
    for y in range(ph):
        u = y / ph
        g = int(58 + 50 * math.exp(-((u - 0.12) / 0.08) ** 2) + 30 * math.exp(-((u - 0.8) / 0.1) ** 2))
        rd.line([(0, y), (pw, y)], fill=(g, g - 6, g - 2, 255))
    m = Image.new("L", (pw, ph), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, pw - 1, ph - 1], BODY_R, fill=255)
    im.paste(rim, (0, 0), m)
    d.rounded_rectangle([5, 5, pw - 6, ph - 6], BODY_R - 5, fill=(6, 4, 6, 255))           # black glass bezel
    win = Image.new("L", (SW, SH), 0)
    ImageDraw.Draw(win).rounded_rectangle([0, 0, SW - 1, SH - 1], SCR_R, fill=255)
    hole = Image.new("RGBA", (SW, SH), (0, 0, 0, 0))
    im.paste(hole, (BEZ, BEZ), win)
    return im, win


STATUSBAR = None
FRAME = WIN = None


def screen(t_rec):
    i = max(0, bisect.bisect(FR, t_rec) - 1)
    app = Image.open(os.path.join(REC, "f_%05d.jpg" % i)).convert("RGBA")
    if app.size != (SW, SH - STATUS):
        app = app.resize((SW, SH - STATUS), Image.BILINEAR)
    scr = Image.new("RGBA", (SW, SH))
    scr.paste(STATUSBAR, (0, 0))
    scr.paste(app, (0, STATUS))
    d = ImageDraw.Draw(scr)
    d.ellipse([SW // 2 - 17, 18, SW // 2 + 17, 52], fill=(0, 0, 0, 255))                  # punch-hole camera
    d.ellipse([SW // 2 - 7, 28, SW // 2 + 3, 38], fill=(30, 40, 70, 255))
    d.rounded_rectangle([SW // 2 - 110, SH - 26, SW // 2 + 110, SH - 16], 5, fill=(255, 255, 255, 170))
    return scr


def coeffs(src, dst):
    """Perspective transform coefficients mapping dst quad -> src quad (PIL convention)."""
    import numpy as np
    A, B = [], []
    for (x, y), (u, v) in zip(dst, src):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y])
        B += [u, v]
    return np.linalg.solve(np.array(A, float), np.array(B, float)).tolist()


def phone(t_rec, yaw_deg, height_px, glow=1.0):
    """The finished phone at `height_px`, rotated about its vertical axis by yaw."""
    ph = FRAME.copy()
    scr = screen(t_rec)
    ph.paste(scr, (BEZ, BEZ), WIN)
    ph.alpha_composite(FRAME_OVER)
    k = height_px / ph.height
    w0, h0 = int(ph.width * k), int(height_px)
    ph = ph.resize((w0, h0), Image.LANCZOS if not PREVIEW else Image.BILINEAR)
    a = math.radians(yaw_deg)
    f = 2.6 * h0
    half = w0 / 2
    pts = []
    for (x, y) in ((-half, 0), (half, 0), (half, h0), (-half, h0)):
        X, Z = x * math.cos(a), x * math.sin(a)
        s = f / (f + Z)
        pts.append((X * s, (y - h0 / 2) * s))
    minx = min(p[0] for p in pts)
    miny = min(p[1] for p in pts)
    dst = [(p[0] - minx, p[1] - miny) for p in pts]
    ow = int(max(p[0] for p in dst)) + 1
    oh = int(max(p[1] for p in dst)) + 1
    src = [(0, 0), (w0, 0), (w0, h0), (0, h0)]
    out = ph.transform((ow, oh), Image.PERSPECTIVE, coeffs(src, dst), Image.BICUBIC)
    return out


GLOSS = None


def frame_over():
    """Glass sheen over the screen (very subtle diagonal highlight)."""
    pw, ph = FRAME.size
    g = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    d = ImageDraw.Draw(g)
    d.polygon([(BEZ, BEZ), (pw * 0.55, BEZ), (BEZ, ph * 0.42)], fill=(255, 255, 255, 16))
    m = Image.new("L", (pw, ph), 0)
    m.paste(WIN, (BEZ, BEZ))
    out = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    out.paste(g, (0, 0), m)
    return out


def place_phone(im, ph, cx, cy, a=1.0):
    # floor glow + soft shadow
    sh = Image.new("RGBA", (ph.width + S(240), S(200)), (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse([S(60), S(60), sh.width - S(60), S(140)], fill=(0, 0, 0, int(150 * a)))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(S(26))), (int(cx - sh.width / 2), int(cy + ph.height / 2 - S(80))))
    gl = Image.new("RGBA", (ph.width + S(200), ph.height + S(200)), (0, 0, 0, 0))
    ImageDraw.Draw(gl).rounded_rectangle([S(100), S(100), S(100) + ph.width, S(100) + ph.height], S(70),
                                         fill=NEON + (int(95 * a),))
    im.alpha_composite(gl.filter(ImageFilter.GaussianBlur(S(46))), (int(cx - gl.width / 2), int(cy - gl.height / 2)))
    E.paste(im, ph, (cx - ph.width / 2, cy - ph.height / 2), a)


# ---------------------------------------------------------------- copy (left column)
def copy_block(im, sc, t, dur):
    key, _, _, chip, l1, l2, desc, pills = sc
    out = clamp((dur - t) / 0.4)
    d = ImageDraw.Draw(im)
    x = S(150)
    a0 = E.appear(t, 0.15) * out
    E.spaced(d, (x, S(300)), chip, SEMI(26), CYAN, a0, 6)
    a1 = E.appear(t, 0.3, 0.6) * out
    E.text(d, (x - S(4) + int((1 - a1) * S(40)), S(345)), l1, XB(96), WHITE, a1)
    a2 = E.appear(t, 0.45, 0.6) * out
    E.glow_text(im, (x - S(4) + int((1 - a2) * S(40)), S(455)), l2, XB(96), NEON, a2, 22)
    d = ImageDraw.Draw(im)
    a3 = E.appear(t, 0.8, 0.6) * out
    words, line, ly = desc.split(), "", S(605)
    f = REG(34)
    for w_ in words:
        if f.getlength(line + " " + w_) > S(760):
            E.text(d, (x, ly), line.strip(), f, CREAM, a3)
            line, ly = w_, ly + S(52)
        else:
            line += " " + w_
    E.text(d, (x, ly), line.strip(), f, CREAM, a3)
    px = x
    for i, p in enumerate(pills):
        px += E.chip(im, d, (px, ly + S(90)), p, E.appear(t, 1.2 + i * 0.25) * out, SEMI(26)) + S(14)


def chrome(im, idx, n, t_total, total):
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([S(60), S(48), S(112), S(100)], S(14), fill=NEON + (255,))
    E.text(d, (S(86), S(74)), "N", XB(32), WHITE, 1, "mm")
    E.text(d, (S(128), S(74)), "Nova-Band App", XB(32), WHITE, 1, "lm")
    d.rounded_rectangle([S(150), S(1010), S(1770), S(1014)], S(2), fill=(255, 255, 255, 30))
    d.rounded_rectangle([S(150), S(1010), S(150) + S(1620) * t_total / total, S(1014)], S(2), fill=NEON + (255,))


# ---------------------------------------------------------------- intro / outro
def nova(im, clip, t, feet):
    keep = E.FEET
    E.FEET = feet
    E.mascot(im, clip, t)
    E.FEET = keep


def intro(t):
    im = E.background(t)
    a = clamp(t / 0.5)
    nova(im, "wave", t, (1390, 1000))
    d = ImageDraw.Draw(im)
    E.spaced(d, (S(150), S(360)), "SHOWREEL APLIKASI", SEMI(30), CYAN, E.appear(t, 0.2), 8)
    E.glow_text(im, (S(140), S(395)), "Nova-Band", XB(150), WHITE, E.appear(t, 0.4, 0.7), 26)
    d = ImageDraw.Draw(im)
    E.text(d, (S(150), S(600)), "App pendamping pelari, langsung dari lengan atas.", REG(40), CREAM, E.appear(t, 0.9))
    E.chip(im, d, (S(150), S(690)), "novaband-id.web.app", E.appear(t, 1.4))
    return im


def outro(t):
    im = E.background(100 + t)
    d = ImageDraw.Draw(im)
    a = 1.0 if t < OUTRO - 0.6 else clamp((OUTRO - t) / 0.6)
    E.glow_text(im, (S(140), S(300)), "Nova-Band", XB(150), WHITE, E.appear(t, 0.2, 0.7) * a, 26)
    d = ImageDraw.Draw(im)
    E.text(d, (S(150), S(500)), "Monitor. Analyze. Improve.", E.SERIF(60), CREAM, E.appear(t, 0.7) * a)
    E.chip(im, d, (S(150), S(610)), "novaband-id.web.app  ·  pasang sebagai aplikasi", E.appear(t, 1.2) * a)
    nova(im, "cheer", t, (1450, 1000))
    d = ImageDraw.Draw(im)
    E.text(d, (S(150), S(760)), "SMA Negeri 1 Surakarta  ·  ISIF 2026", SEMI(30), WHITE, E.appear(t, 1.8) * a)
    return im


# ---------------------------------------------------------------- main
def setup():
    global STATUSBAR, FRAME, WIN, FRAME_OVER
    E.BG, E.BLOBS = E.build_bg()
    E.GRID_Y, E.GRID = E.build_grid()
    STATUSBAR = status_bar()
    FRAME, WIN = phone_frame()
    FRAME_OVER = frame_over()


def main():
    global STATUSBAR, FRAME, WIN, FRAME_OVER
    E.BG, E.BLOBS = E.build_bg()
    E.GRID_Y, E.GRID = E.build_grid()
    STATUSBAR = status_bar()
    FRAME, WIN = phone_frame()
    FRAME_OVER = frame_over()
    plan, st = [], INTRO
    for sc in SCENES:
        dur = sc[2] - sc[1]
        plan.append((sc, st, dur))
        st += dur - XF
    total = st + XF + OUTRO
    ff = R.find_ffmpeg()
    step = 4 if PREVIEW else 1
    silent = J("build", "app_showreel_video.mp4")
    out = J("build", "app_showreel_preview.mp4") if PREVIEW else silent
    p = subprocess.Popen([ff, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H),
                          "-r", str(FPS / step), "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "18",
                          "-pix_fmt", "yuv420p", out], stdin=subprocess.PIPE)
    PH_H = S(930)
    CX, CY = S(1390), S(530)

    def scene_frame(k, t):
        sc, s0, dur = plan[k]
        im = E.background(s0 + t)
        yaw = -14 + 5 * math.sin((s0 + t) * 0.35)
        rise = ease(t / 0.8) if k == 0 else 1.0
        ph = phone(sc[1] + t, yaw, PH_H)
        place_phone(im, ph, CX, CY + (1 - rise) * S(500), rise)
        copy_block(im, sc, t, dur)
        chrome(im, k, len(plan), s0 + t, total)
        return im

    poster = None
    n = int(total * FPS)
    for i in range(0, n, step):
        g = i / FPS
        if g < INTRO:
            im = intro(g)
            if g > INTRO - XF:
                im = Image.blend(im.convert("RGB"), scene_frame(0, 0).convert("RGB"), (g - INTRO + XF) / XF)
        elif g >= total - OUTRO:
            im = outro(g - (total - OUTRO))
        else:
            act = [k for k, (_, s0, dur) in enumerate(plan) if s0 <= g < s0 + dur]
            if len(act) == 2:
                a0, a1 = act
                u = (g - plan[a1][1]) / XF
                im = Image.blend(scene_frame(a0, g - plan[a0][1]).convert("RGB"),
                                 scene_frame(a1, g - plan[a1][1]).convert("RGB"), clamp(u))
            elif act:
                im = scene_frame(act[0], g - plan[act[0]][1])
            else:
                im = outro(0)
        im = im.convert("RGB")
        if poster is None and g >= plan[2][1] + 4:
            poster = im
        p.stdin.write(im.tobytes())
        if i % (FPS * 10) < step:
            print("  %5.1f / %.1f s" % (g, total), flush=True)
    p.stdin.close()
    p.wait()
    if PREVIEW:
        print("wrote", out)
        return
    pad = J("build", "app_showreel_pad.wav")
    E.pad_music(total, pad)
    final = J("assets", "novaband-app-showreel.mp4")
    subprocess.run([ff, "-y", "-loglevel", "error", "-i", silent, "-i", pad, "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", final],
                   check=True)
    poster.save(J("assets", "novaband-app-showreel-poster.jpg"), quality=86)
    subprocess.run([ff, "-y", "-loglevel", "error", "-i", final, "-c:v", "libvpx-vp9", "-b:v", "0", "-crf", "34",
                    "-row-mt", "1", "-deadline", "good", "-cpu-used", "2", "-c:a", "libopus", "-b:a", "96k",
                    J("assets", "novaband-app-showreel.webm")], check=True)
    print("wrote", final, "%.1f s" % total)


if __name__ == "__main__":
    main()
