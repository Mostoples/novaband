"""
Nova-Band company profile (16:9, ~95 s), cut mostly from original footage:
the field shoot in dokumentasi/ADEGAN, the running-community test, the
expert and partner visits. Graphics stay light: statements, a few numbers
from the website, lower thirds.

    python tools/make-profile.py              # -> build/promo/NovaBand_Company_Profile.mp4
    python tools/make-profile.py --preview    # 960 px

Re-uses fonts, lower thirds, subtitles and the music bed from tools/make-rekap.py.
"""
import importlib.util
import os
import subprocess
import wave

import numpy as np
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
J = lambda *p: os.path.join(ROOT, *p)
spec = importlib.util.spec_from_file_location("rekap", J("tools", "make-rekap.py"))
K = importlib.util.module_from_spec(spec)
spec.loader.exec_module(K)
R, W, H, FPS, S, FF, SR = K.R, K.W, K.H, K.FPS, K.S, K.FF, K.SR
ease, clamp, text = K.ease, K.clamp, K.text
RED, CREAM, MUTED = K.RED, K.CREAM, K.MUTED
XF = 10
DOC = J("dokumentasi")
AD = os.path.join(DOC, "ADEGAN")
A = lambda stamp: os.path.join(AD, "WhatsApp Video 2026-10-10 at %s.mp4" % stamp)
KL = lambda n: os.path.join(DOC, "KOMUNITAS LARI SURAKARTA", n)

# kind, path, start, dur, extra
#   big: centred statement (kicker, line1, line2) | lt: lower third | subs | audio | rot (transpose)
SHOTS = [
    ("video", A("12.26.24"), 0.2, 8.0, {"big": ("SMA NEGERI 1 SURAKARTA  ·  ISIF 2026", "Nova-Band", "Lari lebih aman, dari lengan atas."), "title": True}),
    ("video", A("12.25.37"), 0.0, 2.2, {}),
    ("video", A("12.25.35"), 0.0, 3.7, {"big": ("LATAR BELAKANG", "Lari makin digemari.", "Event lari digelar di seluruh Indonesia.")}),
    ("video", A("12.24.50"), 0.3, 5.6, {"lt": ("Masalah", "Overtraining", "Memaksa tubuh melewati batas memicu cedera tendon & jaringan lunak")}),
    ("video", A("12.25.09"), 0.6, 5.4, {"lt": ("Masalah", "Motion artifact", "Ayunan pergelangan mengganggu pembacaan detak jantung")}),
    ("video", A("12.25.34 (2)"), 3.6, 6.0, {"big": ("SOLUSI", "Nova-Band", "Armband lengan atas: PPG + IMU + ESP32.")}),
    ("video", A("12.26.23"), 0.0, 4.2, {"lt": ("Produk", "Layar langsung di lengan", "Detak jantung, pace, dan zona latihan saat berlari")}),
    ("video", A("12.26.23"), 4.2, 4.0, {"stat": ("2,5–3,5%", "MAPE terhadap alat acuan")}),
    ("video", A("12.25.34"), 4.0, 8.4, {"lt": ("Kenapa lengan atas", "Lebih stabil, lebih akurat", "Lengan atas bergerak lebih sedikit, sinyal PPG lebih bersih")}),
    ("video", A("12.25.33"), 4.0, 7.0, {"rot": True, "lt": ("AI di aplikasi", "Readiness Score 0–100", "Tahu kapan gas, tahu kapan istirahat · 5 zona intensitas")}),
    ("video", A("12.25.34 (1)"), 2.2, 1.7, {}),
    ("video", A("12.25.34 (2)"), 9.6, 3.2, {}),
    ("video", KL("WhatsApp Video 2026-09-30 at 20.33.41 (1).mp4"), 0, 9.8,
     {"audio": 1.0, "lt": ("Shared Safety Net", "Pelatih ikut menjaga", ""),
      "subs": [(0.0, 5.0, "…di jarak yang mungkin tidak bisa kita jangkau dengan efisien, atau jarak yang jauh."),
               (5.0, 8.5, "Makanya kita bisa cek apakah anggota kita yang sedang berlatih aman kondisinya,"),
               (8.5, 9.8, "atau perlu dipantau.")]}),
    ("video", KL("WhatsApp Video 2026-10-08 at 06.57.02.mp4"), 2.0, 4.0, {"lt": ("Uji lapangan", "Komunitas Lari Surakarta", "")}),
    ("video", KL("WhatsApp Video 2026-10-08 at 06.57.04.mp4"), 0, 6.0, {"audio": 0.9}),
    ("photo", os.path.join(DOC, "PROFESOR PRINGGO UNS", "IMG_20261007_080939675_HDR.jpg"), 0, 3.0,
     {"lt": ("Konsultasi pakar", "Prof. Pringgo · UNS", "")}),
    ("photo", os.path.join(DOC, "PROFESSOR NURYANI UNS FISIKA", "WhatsApp Image 2026-10-09 at 15.51.48.jpeg"), 0, 3.0,
     {"lt": ("Konsultasi pakar", "Prof. Nuryani · Fisika UNS", "")}),
    ("photo", os.path.join(DOC, "Dokter Yasa Moewardi", "WhatsApp Image 2026-10-09 at 04.24.32 (1).jpeg"), 0, 3.0,
     {"lt": ("Masukan klinis", "dr. Yasa · RSUD Dr. Moewardi", "")}),
    ("photo", os.path.join(DOC, "DINAS KESEHATAN SURAKARTA", "WhatsApp Image 2026-10-08 at 19.16.18.jpeg"), 0, 3.0,
     {"lt": ("Surat dukungan", "Dinas Kesehatan Kota Surakarta", "")}),
    ("photo", os.path.join(DOC, "KLINIK UTAMA HAUNAA", "WhatsApp Image 2026-10-09 at 04.38.22.jpeg"), 0, 3.0,
     {"lt": ("Surat dukungan", "Klinik Utama Haunaa", "")}),
    ("photo", KL("WhatsApp Image 2026-10-08 at 06.57.05.jpeg"), 0, 4.5, {"stat": ("84,5", "Skor SUS · Grade A · 60 responden"), "dark": 0.35}),
    ("photo", os.path.join(DOC, "SMA Negeri 1 Surakarta", "WhatsApp Image 2026-10-09 at 04.36.23.jpeg"), 0, 7.0, {"end": True}),
]


def vf(path, ex):
    """ADEGAN is 848x478 WhatsApp video: Lanczos upscale + light sharpening; other clips use the recap's filter."""
    if os.path.dirname(path) != AD:
        return K.vf_for(path)
    rot = "transpose=2," if ex.get("rot") else ""
    return ("%sscale=%d:%d:flags=lanczos:force_original_aspect_ratio=increase,crop=%d:%d,"
            "unsharp=5:5:0.7:5:5:0,eq=contrast=1.07:saturation=1.12,setsar=1,fps=%d" % (rot, W, H, W, H, FPS))


def video_frames(path, start, dur, ex):
    n = int(round(dur * FPS))
    p = subprocess.Popen([FF, "-v", "error", "-ss", "%.3f" % start, "-i", path, "-t", "%.3f" % (dur + 0.5),
                          "-filter_complex", vf(path, ex), "-an", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    last = None
    for _ in range(n):
        b = p.stdout.read(W * H * 3)
        if len(b) == W * H * 3:
            last = np.frombuffer(b, np.uint8).reshape(H, W, 3)
        yield last
    p.stdout.close()
    p.kill()


def logo(d, x, y, size, a=1.0, anchor="l"):
    f = R.XB(size)
    tw = d.textlength("Nova-Band", font=f)
    x0 = x - tw / 2 if anchor == "m" else x
    text(d, (x0, y), "Nova", f, (255, 255, 255), a, "lm")
    text(d, (x0 + d.textlength("Nova", font=f), y), "-", f, RED, a, "lm")
    text(d, (x0 + d.textlength("Nova-", font=f), y), "Band", f, (255, 255, 255), a, "lm")


def big(d, b, t, dur, title=False):
    kick, l1, l2 = b
    out = clamp((dur - t) / 0.5)
    y = H // 2 - S(40)
    text(d, (W // 2, y - S(110)), kick, R.SEMI(24), MUTED, ease((t - 0.3) / 0.6) * out, "mm")
    p = ease((t - 0.5) / 0.8)
    if title:
        logo(d, W // 2, y + int((1 - p) * S(30)), 150, p * out, "m")
    else:
        text(d, (W // 2, y + int((1 - p) * S(30))), l1, R.XB(96), (255, 255, 255), p * out, "mm")
    text(d, (W // 2, y + S(110)), l2, R.SERIF(50), CREAM, ease((t - 1.1) / 0.8) * out, "mm")


def stat(d, st, t, dur):
    num, lab = st
    out = clamp((dur - t) / 0.5)
    p = ease((t - 0.2) / 0.7)
    x, y = S(110), H - S(330)
    text(d, (x, y + int((1 - p) * S(30))), num, R.XB(150), (255, 255, 255), p * out)
    text(d, (x + S(6), y + S(190)), lab, R.SEMI(34), CREAM, ease((t - 0.6) / 0.6) * out)
    d.rounded_rectangle((x + S(6), y + S(176), x + S(6) + int(S(380) * p), y + S(181)), S(3), fill=RED + (int(255 * out),))


def end_card(d, t, dur):
    out = clamp((dur - t) / 0.8)
    d.rectangle((0, 0, W, H), fill=(18, 5, 10, int(190 * ease((t - 0.8) / 0.8))))
    logo(d, W // 2, H // 2 - S(80), 130, ease((t - 1.0) / 0.8) * out, "m")
    text(d, (W // 2, H // 2 + S(30)), "Monitor. Analyze. Improve.", R.SERIF(50), CREAM, ease((t - 1.5) / 0.8) * out, "mm")
    text(d, (W // 2, H // 2 + S(120)), "Tim Peneliti SMA Negeri 1 Surakarta", R.SEMI(30), (255, 255, 255), ease((t - 2.0) / 0.8) * out, "mm")
    text(d, (W // 2, H // 2 + S(168)), "Maheswara · Almira · Azra · Dela · Rizkyta · Satriya  ·  Pembimbing: Andreas Wegiq Adia Hendix",
         R.REG(22), MUTED, ease((t - 2.3) / 0.8) * out, "mm")
    text(d, (W // 2, H // 2 + S(250)), "novaband-id.web.app", R.BOLD(30), RED, ease((t - 2.7) / 0.8) * out, "mm")


def corner(d):
    logo(d, S(64), S(62), 26, 0.95)


def shot_frames(i, shot):
    kind, path, start, dur, ex = shot
    src = video_frames(path, start, dur, ex) if kind == "video" else K.photo_frames(path, dur, i, dark=ex.get("dark", 0.0))
    for f, a in enumerate(src):
        t = f / FPS
        im = Image.fromarray(np.array(a))                    # RGB, so RGBA drawing blends
        if "big" in ex:
            ImageDraw.Draw(im, "RGBA").rectangle((0, 0, W, H), fill=(14, 4, 8, int(110 * ease(t / 0.6))))
        elif "end" not in ex:
            im.paste(K.SHADE, (0, 0), K.SHADE)
        d = ImageDraw.Draw(im, "RGBA")
        if not ex.get("title") and "end" not in ex:
            corner(d)
        if "big" in ex:
            big(d, ex["big"], t, dur, ex.get("title"))
        if "lt" in ex:
            K.lower_third(d, ex["lt"], t, dur, 0.3)
        if "stat" in ex:
            stat(d, ex["stat"], t, dur)
        if "subs" in ex:
            K.subtitle(d, ex["subs"], t)
        if "end" in ex:
            end_card(d, t, dur)
        yield np.asarray(im.convert("RGB"))


def timeline():
    t, out = 0.0, []
    for s in SHOTS:
        out.append(t)
        t += s[3] - XF / FPS
    return out, t + XF / FPS


def soundtrack(starts, total, path):
    mus = K.music(total)
    n = len(mus)
    voice, duck = np.zeros(n), np.ones(n)
    for t0, (kind, p, start, dur, ex) in zip(starts, SHOTS):
        if "audio" not in ex:
            continue
        a = K.clip_audio(p, start, dur) * ex["audio"]
        i0 = int(t0 * SR)
        a = a[: max(0, n - i0)]
        ramp = np.minimum(1, np.minimum(np.arange(len(a)) / (0.15 * SR), (len(a) - np.arange(len(a))) / (0.3 * SR)))
        voice[i0:i0 + len(a)] += a * ramp
        duck[i0:i0 + len(a)] = np.minimum(duck[i0:i0 + len(a)], 0.22)
    k = int(0.35 * SR)
    c = np.concatenate(([0.0], np.cumsum(np.pad(duck, (k // 2, k - k // 2), mode="edge"))))
    duck = (c[k:] - c[:-k])[:n] / k
    mix = np.tanh((mus * duck + voice * 0.95) * 1.1) * 0.82
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())


def main():
    os.makedirs(J("build", "promo"), exist_ok=True)
    starts, total = timeline()
    wav = J("build", "promo", "profile.wav")
    soundtrack(starts, total, wav)
    out = J("build", "promo", "NovaBand_Company_Profile%s.mp4" % ("_preview" if K.PREVIEW else ""))
    enc = subprocess.Popen([FF, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H), "-r", str(FPS),
                            "-i", "-", "-i", wav, "-c:v", "libx264", "-preset", "veryfast" if K.PREVIEW else "medium",
                            "-crf", "28" if K.PREVIEW else "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                            "-movflags", "+faststart", "-shortest", out], stdin=subprocess.PIPE)
    tail = []
    for i, shot in enumerate(SHOTS):
        last = i == len(SHOTS) - 1
        n = int(round(shot[3] * FPS))
        buf = []
        for f, fr in enumerate(shot_frames(i, shot)):
            if f < len(tail):
                w = (f + 1) / (len(tail) + 1)
                fr = (tail[f].astype(np.float32) * (1 - w) + fr.astype(np.float32) * w).astype(np.uint8)
            if not last and f >= n - XF:
                buf.append(fr)
                continue
            enc.stdin.write(np.ascontiguousarray(fr).tobytes())
        tail = buf
        print("%2d/%d  %4.1fs @%5.1fs  %s" % (i + 1, len(SHOTS), shot[3], starts[i], os.path.basename(shot[1])), flush=True)
    enc.stdin.close()
    enc.wait()
    print(out, "%.1f s" % total)


if __name__ == "__main__":
    main()
