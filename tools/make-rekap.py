"""
Nova-Band documentation recap: field testing with Komunitas Lari Surakarta,
expert consultations at UNS and the Surakarta health office's letter of
support, cut from the raw phone footage in dokumentasi/.

    python tools/make-rekap.py              # -> build/rekap/NovaBand_Rekap_Dokumentasi.mp4
    python tools/make-rekap.py --preview    # 960 px, quick check

Every shot is decoded by ffmpeg (portrait clips sit on a blurred fill),
titled with Pillow and cross-faded here; the music is synthesised and ducked
under the coach's own voice.
"""
import importlib.util
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
spec.loader.exec_module(R)                      # fonts, easing, ffmpeg finder
W, H, K, FPS = R.W, R.H, R.K, R.FPS
PREVIEW = R.PREVIEW
XF = 12                                         # cross-fade, frames
FF = R.find_ffmpeg()
SR = 44100
WINE, CREAM = (123, 32, 33), (243, 227, 211)
RED, MUTED = (255, 79, 99), (215, 200, 205)
ease, clamp = R.ease, R.clamp
S = lambda v: int(round(v * K))

DOC = J("dokumentasi")
KL, PP, PN, DK = "KOMUNITAS LARI SURAKARTA", "PROFESOR PRINGGO UNS", "PROFESSOR NURYANI UNS FISIKA", "DINAS KESEHATAN SURAKARTA"
YS, HN, SM = "Dokter Yasa Moewardi", "KLINIK UTAMA HAUNAA", "SMA Negeri 1 Surakarta"

# letter cards: pdf, share of page 1 shown, background photo, texts
LETTERS = {
    "dinkes": dict(pdf=(DK, "surat dukungan nova band.pdf"), crop=0.56, bg=(DK, "WhatsApp Image 2026-10-08 at 19.16.40.jpeg"),
                   kicker="Surat dukungan", title=("Dinas Kesehatan", "Kota Surakarta"), meta="No. B/0.9/5995  ·  5 Oktober 2026",
                   items=[("Dukungan moril", "apresiasi untuk melanjutkan riset"),
                          ("Dukungan fasilitas", "sosialisasi lewat promosi kesehatan"),
                          ("Dukungan kepakaran", "masukan kesehatan olahraga & regulasi")],
                   note=("Dukungan pembinaan riset pelajar — bukan pernyataan kelayakan klinis",
                         "maupun izin edar alat kesehatan.")),
    "haunaa": dict(pdf=(HN, "Surat Dukungan Penelitian (1).pdf"), crop=0.62, bg=(HN, "WhatsApp Image 2026-10-09 at 04.38.22.jpeg"),
                   kicker="Surat dukungan", title=("Klinik Utama", "Haunaa"), meta="No. 008/HUM-HAUNAA/X/2026  ·  8 Oktober 2026",
                   items=[("Dukungan moril", "apresiasi untuk tim peneliti muda"),
                          ("Dukungan fasilitas", "uji coba & pengenalan kepada pasien jantung"),
                          ("Dukungan kepakaran", "masukan kesehatan & keselamatan olahraga")],
                   note=("Bukan rekomendasi komersial maupun pernyataan kelayakan alat kesehatan;",
                         "uji coba dengan persetujuan peserta dan pelindungan data pribadi.")),
    "nuryani": dict(pdf=(PN, "Surat Dukungan Pribadi Nova-Band - Prof. Nuryani.pdf"), crop=0.66,
                    bg=(PN, "WhatsApp Image 2026-10-09 at 15.51.47.jpeg"),
                    kicker="Surat dukungan pribadi", title=("Prof. Nuryani", "Instrumentasi Medis, UNS"), meta="Surakarta, 9 Oktober 2026",
                    items=[("Konsep dasar", "arah penelitian dan pengembangan"),
                           ("Instrumentasi sensor", "PPG dan sensor gerak IMU"),
                           ("Keandalan pengukuran", "untuk pengembangan alat yang optimal")],
                    note=("Teknologi kesehatan olahraga untuk membantu pelari", "berlatih lebih aman dan terukur.")),
}

# 3D opening (blender/intro_nova.py + tools/make-intro.py); falls back to the photo title
INTRO3D = J("build", "rekap", "intro3d.mp4")
HAS3D = os.path.exists(INTRO3D)
INTRO_T, INTRO_LAND = (8.0, 118 / 25) if HAS3D else (6.0, None)

CH = {1: ("Uji Lapangan", "Komunitas Lari Surakarta"),
      2: ("Konsultasi Pakar", "Akademisi & Klinisi"),
      3: ("Dukungan Resmi", "Pemerintah & Fasilitas Kesehatan")}

# kind, file, start, dur, extra
#   extra: ch (chapter card), lt (kicker, title, sub), subs [(t0, t1, text)], audio gain
SHOTS = [
    ("intro", (KL, "WhatsApp Image 2026-09-30 at 20.33.41 (1).jpeg"), 0, INTRO_T, {}),
    ("photo", (SM, "WhatsApp Image 2026-10-09 at 04.36.23.jpeg"), 0, 4.5,
     {"lt": ("Tim peneliti", "SMA Negeri 1 Surakarta", "Maheswara · Almira · Azra · Dela · Rizkyta · Satriya")}),
    ("photo", (KL, "WhatsApp Image 2026-10-08 at 06.57.05.jpeg"), 0, 5.5,
     {"ch": 1, "lt": ("Uji lapangan", "Sesi lari bersama komunitas", "Nova-Band diuji langsung oleh pelari di lapangan")}),
    ("video", (KL, "WhatsApp Video 2026-09-30 at 20.33.42.mp4"), 0.8, 5.0,
     {"lt": ("Purwarupa", "Dipakai di lengan atas", "Sensor PPG + IMU dalam satu band, membaca detak jantung dan gerak")}),
    ("video", (KL, "WhatsApp Video 2026-09-30 at 20.33.41 (1).mp4"), 0, 9.8,
     {"audio": 1.0, "lt": ("Pelatih komunitas", "Memantau anggota dari jauh", ""),
      "subs": [(0.0, 5.0, "…di jarak yang mungkin tidak bisa kita jangkau dengan efisien, atau jarak yang jauh."),
               (5.0, 8.5, "Makanya kita bisa cek apakah anggota kita yang sedang berlatih aman kondisinya,"),
               (8.5, 9.8, "atau perlu dipantau.")]}),
    ("video", (KL, "WhatsApp Video 2026-09-30 at 20.33.41.mp4"), 0, 18.2,
     {"audio": 1.0, "chips": ["Detak jantung", "Kadens (langkah/menit)", "Pace & waktu", "Zona: easy · tempo · interval"],
      "lt": ("Pelatih komunitas", "Yang bisa dipantau", ""),
      "subs": [(0.0, 5.2, "Bisa dipantau dari berapa detak jantung, lalu juga step per menitnya,"),
               (5.2, 10.0, "lalu pace dan juga waktunya, seperti biasa."),
               (10.0, 15.0, "Lalu juga tingkat intensitas latihan: easy, tempo, dan juga interval."),
               (15.0, 18.2, "Maka dari itu, kesimpulannya bisa juga nanti kita pantau.")]}),
    ("video", (KL, "WhatsApp Video 2026-10-08 at 06.56.56.mp4"), 0.3, 5.2,
     {"lt": ("Persiapan", "Band dipasang ke pelari", "")}),
    ("video", (KL, "WhatsApp Video 2026-10-08 at 06.57.02.mp4"), 2.0, 5.0,
     {"lt": ("Aplikasi", "Band terhubung ke ponsel", "Bluetooth LE · data tampil secara real-time")}),
    ("video", (KL, "WhatsApp Video 2026-10-08 at 06.57.04.mp4"), 0, 7.0,
     {"audio": 0.9, "lt": ("Mulai", "3, 2, 1… lari!", "Detak jantung dan gerak terekam sepanjang sesi")}),

    ("photo", (PP, "IMG_20261007_080939675_HDR.jpg"), 0, 5.5,
     {"ch": 2, "lt": ("7 Oktober 2026", "Prof. Pringgo · UNS", "Pemaparan konsep dan purwarupa Nova-Band")}),
    ("video", (PP, "VID_20261007_081009439.mp4"), 1.0, 4.4,
     {"lt": ("Pemaparan", "Latar belakang & masalah", "Masalah yang ingin diselesaikan Nova-Band")}),
    ("video", (PP, "VID_20261007_082859711.mp4"), 6.0, 5.0,
     {"lt": ("Masukan", "Arah pengembangan berikutnya", "")}),
    ("photo", (PN, "IMG_20261007_132927492_HDR.jpg"), 0, 5.0,
     {"lt": ("7 Oktober 2026", "Prof. Nuryani · Fisika UNS", "Demo aplikasi dan diskusi teknis purwarupa")}),
    ("video", (PN, "VID_20261007_132932005.mp4"), 0.5, 5.0,
     {"lt": ("Demo", "Antarmuka aplikasi Nova-Band", "")}),
    ("video", (PN, "VID_20261007_133052705.mp4"), 0.0, 5.0,
     {"lt": ("Beranda", "Performa harian pelari", "Readiness, detak jantung, dan riwayat latihan")}),
    ("video", (PN, "VID_20261007_133547528.mp4"), 12.0, 4.5,
     {"lt": ("Masukan", "Diskusi teknis bersama pakar", "")}),
    ("photo", (PN, "WhatsApp Image 2026-10-09 at 15.51.48.jpeg"), 0, 4.5,
     {"lt": ("9 Oktober 2026", "Department of Physics, UNS", "Surat dukungan pribadi untuk Nova-Band")}),
    ("letter", "nuryani", 0, 8.0, {}),
    ("photo", (YS, "WhatsApp Image 2026-10-09 at 04.24.32 (1).jpeg"), 0, 5.0,
     {"lt": ("Klinisi", "dr. Yasa · RSUD Dr. Moewardi", "Masukan dari sisi klinis untuk Nova-Band")}),
    ("video", (YS, "WhatsApp Video 2026-10-09 at 04.34.40 (1).mp4"), 72.0, 5.5,
     {"lt": ("Masukan klinis", "Zona detak jantung & target latihan", "Target latihan mengacu pada detak jantung maksimal")}),

    ("photo", (DK, "WhatsApp Image 2026-10-08 at 19.16.18.jpeg"), 0, 5.5,
     {"ch": 3, "lt": ("2 Oktober 2026", "Audiensi Dinas Kesehatan", "Kota Surakarta")}),
    ("video", (DK, "WhatsApp Video 2026-10-08 at 19.16.44.mp4"), 7.0, 6.0,
     {"lt": ("Pemaparan", "AI Buddy & mode latihan", "Nova memberi saran detak jantung dan pace saat berlari")}),
    ("photo", (DK, "WhatsApp Image 2026-10-08 at 19.16.44 (2).jpeg"), 0, 4.5,
     {"lt": ("Kunjungan", "Bersama Dispora Kota Surakarta", "")}),
    ("letter", "dinkes", 0, 8.5, {}),
    ("photo", (HN, "WhatsApp Image 2026-10-09 at 04.38.22.jpeg"), 0, 5.0,
     {"lt": ("Fasilitas kesehatan", "Klinik Utama Haunaa", "Audiensi 1 Oktober 2026 · Surakarta")}),
    ("letter", "haunaa", 0, 8.5, {}),
    ("outro", (SM, "WhatsApp Image 2026-10-09 at 04.36.23 (1).jpeg"), 0, 8.5, {}),
]


# ------------------------------------------------------------------ sources
def vf_for(path):
    """Landscape: fill the frame. Portrait: sharp clip on the right, blurred fill behind."""
    out = subprocess.run([FF.replace("ffmpeg.exe", "ffprobe.exe"), "-v", "error", "-select_streams", "v:0",
                          "-show_entries", "stream=width,height:stream_side_data=rotation", "-of", "default=nw=1", path],
                         capture_output=True, text=True).stdout
    kv = dict(l.split("=", 1) for l in out.split() if "=" in l)
    w, h = int(kv["width"]), int(kv["height"])
    if abs(int(float(kv.get("rotation", 0)))) == 90:
        w, h = h, w
    grade = "eq=contrast=1.06:saturation=1.1"
    if w >= h:
        return "scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,setsar=1,%s,fps=%d" % (W, H, W, H, grade, FPS)
    fw = int(H * w / h) // 2 * 2
    return ("split[a][b];[a]scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,boxblur=%d:2,eq=brightness=-0.22:saturation=0.8[bg];"
            "[b]scale=%d:%d,%s[fg];[bg][fg]overlay=%d:0,setsar=1,fps=%d"
            % (W, H, W, H, S(40), fw, H, grade, W - fw - S(150), FPS))


def video_frames(path, start, dur):
    n = int(round(dur * FPS))
    p = subprocess.Popen([FF, "-v", "error", "-ss", "%.3f" % start, "-i", path, "-t", "%.3f" % (dur + 0.5),
                          "-filter_complex", vf_for(path), "-an", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    last = None
    for _ in range(n):
        b = p.stdout.read(W * H * 3)
        if len(b) == W * H * 3:
            last = np.frombuffer(b, np.uint8).reshape(H, W, 3)
        yield last
    p.stdout.close()
    p.kill()


def load_photo(path, over=1.12):
    im = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    return ImageOps.fit(im, (int(W * over), int(H * over)), Image.LANCZOS)


def photo_frames(path, dur, i, blur=0, dark=0.0):
    base = load_photo(path)
    if blur:
        base = base.filter(ImageFilter.GaussianBlur(S(blur)))
    n = int(round(dur * FPS))
    bw, bh = base.size
    for f in range(n):
        p = f / max(1, n - 1)
        z = 1.0 + 0.08 * p if i % 2 == 0 else 1.08 - 0.08 * p    # alternate zoom in / out
        cw, ch = bw / z, bh / z
        x = (bw - cw) * (0.5 + 0.18 * (p - 0.5) * (1 if i % 3 else -1))
        y = (bh - ch) * 0.45
        fr = base.resize((W, H), Image.BILINEAR, box=(x, y, x + cw, y + ch))
        a = np.asarray(fr)
        if dark:
            a = (a * (1 - dark)).astype(np.uint8)
        yield a


# ------------------------------------------------------------------ drawing
def text(d, xy, s, f, fill, a=1.0, anchor="la"):
    if a > 0:
        d.text(xy, s, font=f, fill=tuple(fill) + (int(255 * clamp(a)),), anchor=anchor)


def shade():
    """Bottom-left gradient that keeps the titles legible on any footage."""
    g = np.zeros((H, W, 4), np.uint8)
    yy, xx = np.mgrid[0:H, 0:W]
    a = np.clip((yy / H - 0.45) / 0.55, 0, 1) ** 1.4 * 200 + np.clip(1 - xx / W * 1.6, 0, 1) * 40 * (yy / H)
    top = np.clip(1 - yy / (H * 0.16), 0, 1) * 110
    g[..., 3] = np.clip(a + top, 0, 230).astype(np.uint8)
    g[..., 0], g[..., 1], g[..., 2] = 18, 6, 10
    return Image.fromarray(g, "RGBA")


SHADE = shade()


def brand(d, chap):
    text(d, (S(64), S(52)), "NOVA", R.XB(26), (255, 255, 255))
    text(d, (S(64) + d.textlength("NOVA", font=R.XB(26)), S(52)), "-", R.XB(26), RED)
    text(d, (S(64) + d.textlength("NOVA-", font=R.XB(26)), S(52)), "BAND", R.XB(26), (255, 255, 255))
    text(d, (S(64), S(86)), "Rekap Dokumentasi  ·  Pengujian & Kemitraan", R.REG(19), MUTED, 0.9)
    if chap:
        for k in (1, 2, 3):
            x = W - S(64) - (3 - k) * S(290)
            on = k == chap
            d.rounded_rectangle((x - S(260), S(58), x, S(62)), S(2), fill=(255, 255, 255, 230 if on else 70))
            text(d, (x - S(260), S(72)), "0%d  %s" % (k, CH[k][0].upper()), R.SEMI(17), RED if on else MUTED, 1 if on else 0.6)


def lower_third(d, lt, t, dur, delay):
    kick, title, sub = lt
    a = ease((t - delay) / 0.7) * clamp((dur - t) / 0.5)
    if a <= 0:
        return
    dx = int((1 - ease((t - delay) / 0.7)) * S(-40))
    x, y = S(96) + dx, H - S(250)
    d.rounded_rectangle((x, y, x + S(6), y + S(118 if sub else 76)), S(3), fill=RED + (int(255 * a),))
    text(d, (x + S(28), y - S(4)), kick.upper(), R.SEMI(20), RED, a)
    text(d, (x + S(26), y + S(24)), title, R.XB(54), (255, 255, 255), a)
    if sub:
        text(d, (x + S(28), y + S(98)), sub, R.REG(26), CREAM, a * 0.95)


def chips(d, items, t, delay):
    x, y = S(96), S(300)
    for i, s in enumerate(items):
        a = ease((t - delay - 0.5 * i) / 0.5)
        if a <= 0:
            continue
        f = R.SEMI(28)
        w = d.textlength(s, font=f) + S(60)
        yy = y + i * S(86) + int((1 - a) * S(20))
        d.rounded_rectangle((x, yy, x + w, yy + S(64)), S(32), fill=(30, 10, 16, int(200 * a)), outline=RED + (int(230 * a),), width=max(1, S(2)))
        d.ellipse((x + S(22), yy + S(26), x + S(34), yy + S(38)), fill=RED + (int(255 * a),))
        text(d, (x + S(46), yy + S(32)), s, f, (255, 255, 255), a, "lm")


def subtitle(d, subs, t):
    for t0, t1, s in subs:
        if t0 <= t < t1:
            a = clamp((t - t0) / 0.2) * clamp((t1 - t) / 0.2)
            f = R.SEMI(34)
            words, lines, cur = s.split(), [], ""
            for w_ in words:
                if d.textlength(cur + " " + w_, font=f) > S(1300) and cur:
                    lines.append(cur); cur = w_
                else:
                    cur = (cur + " " + w_).strip()
            lines.append(cur)
            cx, y = W // 2, H - S(84) - (len(lines) - 1) * S(48)
            for k, ln in enumerate(lines):
                tw = d.textlength(ln, font=f)
                d.rounded_rectangle((cx - tw / 2 - S(18), y + k * S(48) - S(26), cx + tw / 2 + S(18), y + k * S(48) + S(24)),
                                    S(10), fill=(0, 0, 0, int(170 * a)))
                text(d, (cx, y + k * S(48)), ln, f, (255, 255, 255), a, "mm")


def chapter_card(d, ch, t):
    a = clamp(1 - (t - 1.9) / 0.6)
    if a <= 0:
        return
    d.rectangle((0, 0, W, H), fill=(22, 6, 11, int(225 * a)))
    k, (lab, title) = ch, CH[ch]
    p = ease(t / 0.8)
    text(d, (W // 2, H // 2 - S(120) + int((1 - p) * S(30))), "0%d" % k, R.SERIF(150), RED, a * p, "mm")
    text(d, (W // 2, H // 2 + S(10)), lab.upper(), R.SEMI(26), MUTED, a * ease((t - 0.25) / 0.6), "mm")
    text(d, (W // 2, H // 2 + S(80)), title, R.XB(68), (255, 255, 255), a * ease((t - 0.4) / 0.6), "mm")


def intro_overlay(d, t, dur):
    out = clamp((dur - t) / 0.6)
    text(d, (W // 2, H // 2 - S(170)), "REKAP DOKUMENTASI  ·  SEPTEMBER–OKTOBER 2026", R.SEMI(24), MUTED, ease((t - 0.3) / 0.8) * out, "mm")
    p = ease((t - 0.6) / 1.0)
    f = R.XB(150)
    tw = d.textlength("Nova-Band", font=f)
    x0, y0 = W // 2 - tw / 2, H // 2 - S(40) + int((1 - p) * S(30))
    text(d, (x0, y0), "Nova", f, (255, 255, 255), p * out, "lm")
    text(d, (x0 + d.textlength("Nova", font=f), y0), "-", f, RED, p * out, "lm")
    text(d, (x0 + d.textlength("Nova-", font=f), y0), "Band", f, (255, 255, 255), p * out, "lm")
    text(d, (W // 2, H // 2 + S(100)), "Pengujian & Kemitraan", R.SERIF(64), CREAM, ease((t - 1.4) / 0.9) * out, "mm")
    text(d, (W // 2, H // 2 + S(190)), "Tim Peneliti SMA Negeri 1 Surakarta", R.REG(26), MUTED, ease((t - 2.0) / 0.9) * out, "mm")


def letter_assets(L):
    import fitz
    doc = fitz.open(os.path.join(DOC, *L["pdf"]))
    pix = doc[0].get_pixmap(dpi=150 if not PREVIEW else 80)
    im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    im = im.crop((0, 0, im.width, int(im.height * L["crop"])))     # letterhead -> scope of support
    ph = int(H * 0.74)
    im = im.resize((int(im.width * ph / im.height), ph), Image.LANCZOS)
    return im


def letter_frame(t, dur, bg, page, L):
    fr = bg.copy()
    d = ImageDraw.Draw(fr, "RGBA")
    out = clamp((dur - t) / 0.5)
    p = ease(t / 0.9)
    px, py = S(110), (H - page.height) // 2 + int((1 - p) * S(40))
    sh = Image.new("RGBA", (page.width + S(60), page.height + S(60)), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((S(30), S(30), page.width + S(30), page.height + S(30)), S(12), fill=(0, 0, 0, 150))
    sh = sh.filter(ImageFilter.GaussianBlur(S(18)))
    fr.paste(sh, (px - S(30), py - S(10)), sh)
    pg = page.convert("RGBA")
    pg.putalpha(int(255 * p * out))
    fr.paste(pg, (px, py), pg)
    x = px + page.width + S(90)
    text(d, (x, S(250)), L["kicker"].upper(), R.SEMI(22), RED, ease((t - 0.4) / 0.6) * out)
    text(d, (x, S(282)), L["title"][0], R.XB(58), (255, 255, 255), ease((t - 0.5) / 0.6) * out)
    text(d, (x, S(352)), L["title"][1], R.XB(58 if len(L["title"][1]) < 18 else 44), (255, 255, 255), ease((t - 0.6) / 0.6) * out)
    text(d, (x, S(440)), L["meta"], R.REG(26), CREAM, ease((t - 0.8) / 0.6) * out)
    for i, (a_, b_) in enumerate(L["items"]):
        a = ease((t - 1.4 - 0.6 * i) / 0.6) * out
        yy = S(520) + i * S(96)
        d.ellipse((x, yy + S(8), x + S(36), yy + S(44)), fill=RED + (int(255 * a),))
        text(d, (x + S(18), yy + S(26)), str(i + 1), R.BOLD(20), (255, 255, 255), a, "mm")
        text(d, (x + S(56), yy), a_, R.BOLD(32), (255, 255, 255), a)
        text(d, (x + S(56), yy + S(42)), b_, R.REG(24), MUTED, a)
    for k, ln in enumerate(L["note"]):
        text(d, (x, S(850) + k * S(28)), ln, R.REG(19), MUTED, ease((t - 3.4) / 0.8) * out * 0.85)
    return fr


def outro_frame(t, dur, bg):
    fr = bg.copy()
    d = ImageDraw.Draw(fr, "RGBA")
    out = clamp((dur - t) / 0.8)
    text(d, (W // 2, S(200)), "TERIMA KASIH", R.SEMI(26), RED, ease(t / 0.7) * out, "mm")
    names = ["Komunitas Lari Surakarta", "Prof. Pringgo  ·  Universitas Sebelas Maret", "Prof. Nuryani  ·  Fisika, Universitas Sebelas Maret",
             "dr. Yasa  ·  RSUD Dr. Moewardi", "Dinas Kesehatan Kota Surakarta", "Klinik Utama Haunaa",
             "Dispora Kota Surakarta", "SMA Negeri 1 Surakarta"]
    for i, s in enumerate(names):
        text(d, (W // 2, S(262) + i * S(52)), s, R.BOLD(32), (255, 255, 255), ease((t - 0.4 - 0.2 * i) / 0.6) * out, "mm")
    a = ease((t - 2.6) / 0.8) * out
    f = R.XB(84)
    tw = d.textlength("Nova-Band", font=f)
    x0 = W // 2 - tw / 2
    text(d, (x0, S(745)), "Nova", f, (255, 255, 255), a, "lm")
    text(d, (x0 + d.textlength("Nova", font=f), S(745)), "-", f, RED, a, "lm")
    text(d, (x0 + d.textlength("Nova-", font=f), S(745)), "Band", f, (255, 255, 255), a, "lm")
    text(d, (W // 2, S(825)), "Monitor. Analyze. Improve.", R.SERIF(42), CREAM, ease((t - 2.9) / 0.8) * out, "mm")
    text(d, (W // 2, S(892)), "Tim Peneliti SMA Negeri 1 Surakarta  ·  ISIF 2026", R.REG(24), MUTED, ease((t - 3.3) / 0.8) * out, "mm")
    return fr


def dark_bg(path, dark=0.72, blur=26):
    im = load_photo(path, 1.0).filter(ImageFilter.GaussianBlur(S(blur)))
    a = np.asarray(im).astype(np.float32) * (1 - dark)
    tint = np.array(WINE, np.float32) * 0.18
    return Image.fromarray(np.clip(a + tint, 0, 255).astype(np.uint8))      # RGB: draws below blend


# ------------------------------------------------------------------ shots
def shot_frames(i, shot, chap):
    kind, src, start, dur, ex = shot
    path = os.path.join(DOC, *src) if isinstance(src, tuple) else None
    n = int(round(dur * FPS))
    if kind == "letter":
        L = LETTERS[src]
        bg, page = dark_bg(os.path.join(DOC, *L["bg"])), letter_assets(L)
        for f in range(n):
            yield np.asarray(letter_frame(f / FPS, dur, bg, page, L))
        return
    if kind == "outro":
        bg = dark_bg(path, 0.8)
        for f in range(n):
            yield np.asarray(outro_frame(f / FPS, dur, bg))
        return
    if kind == "intro" and HAS3D:
        for fr in video_frames(INTRO3D, 0, dur):            # finished piece: no overlays
            yield fr
        return
    if kind == "intro":
        src_it = photo_frames(path, dur, i, blur=6, dark=0.55)
    elif kind == "photo":
        src_it = photo_frames(path, dur, i)
    else:
        src_it = video_frames(path, start, dur)
    for f, a in enumerate(src_it):
        t = f / FPS
        im = Image.fromarray(np.array(a))                    # RGB, so RGBA drawing blends
        if kind != "intro":
            im.paste(SHADE, (0, 0), SHADE)
        d = ImageDraw.Draw(im, "RGBA")
        if kind == "intro":
            intro_overlay(d, t, dur)
        else:
            brand(d, chap)
            delay = 2.4 if "ch" in ex else 0.3
            if "lt" in ex:
                lower_third(d, ex["lt"], t, dur, delay)
            if "chips" in ex:
                chips(d, ex["chips"], t, 1.0)
            if "subs" in ex:
                subtitle(d, ex["subs"], t)
            if "ch" in ex:
                chapter_card(d, ex["ch"], t)
        yield np.asarray(im.convert("RGB"))


def timeline():
    t, out, chap = 0.0, [], 0
    for i, s in enumerate(SHOTS):
        chap = s[4].get("ch", chap)
        out.append((t, chap))
        t += s[3] - XF / FPS
    return out, t + XF / FPS


# ------------------------------------------------------------------ music
def music(total):
    n = int(total * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    bpm = 96
    beat = 60 / bpm
    bar = 4 * beat
    # C - G - Am - F, hopeful and steady
    prog = [(130.81, (261.63, 329.63, 392.0)), (98.0, (246.94, 293.66, 392.0)),
            (110.0, (261.63, 329.63, 440.0)), (87.31, (261.63, 349.23, 440.0))]
    nb = int(total / bar) + 1
    for b in range(nb):
        root, ch = prog[b % 4]
        t0 = b * bar
        i0, i1 = int(t0 * SR), min(n, int((t0 + bar + 1.2) * SR))
        tt = t[i0:i1] - t0
        env = np.clip(tt / 0.5, 0, 1) * np.exp(-np.clip(tt - bar, 0, None) / 0.35)
        for f in ch:                                       # soft pad
            for h, g in ((1, 0.5), (2, 0.16), (3, 0.06)):
                out[i0:i1] += g * env * np.sin(2 * np.pi * f * h * tt + h)
        lvl = 0.0 if b < 2 else 1.0
        for k in range(8):                                 # bass on the eighths
            s0 = t0 + k * beat / 2
            j0, j1 = int(s0 * SR), min(n, int((s0 + 0.28) * SR))
            u = t[j0:j1] - s0
            out[j0:j1] += 0.55 * lvl * np.exp(-u / 0.12) * np.sin(2 * np.pi * root * u)
        arp = list(ch) + [ch[1] * 2]
        for k in range(16):                                # pluck arpeggio
            s0 = t0 + k * beat / 4
            j0, j1 = int(s0 * SR), min(n, int((s0 + 0.35) * SR))
            u = t[j0:j1] - s0
            f = arp[k % 4] * (2 if k % 8 >= 4 else 1)
            out[j0:j1] += 0.16 * np.exp(-u / 0.08) * (np.sin(2 * np.pi * f * u) + 0.3 * np.sin(4 * np.pi * f * u))
        if b >= 4:
            for k in range(4):                             # kick + offbeat hat
                s0 = t0 + k * beat
                j0, j1 = int(s0 * SR), min(n, int((s0 + 0.25) * SR))
                u = t[j0:j1] - s0
                out[j0:j1] += 0.9 * np.exp(-u / 0.07) * np.sin(2 * np.pi * (48 + 90 * np.exp(-u / 0.03)) * u)
                h0 = int((s0 + beat / 2) * SR)
                h1 = min(n, h0 + int(0.05 * SR))
                if h0 < n:
                    out[h0:h1] += 0.06 * np.random.default_rng(k + b).standard_normal(h1 - h0) * np.exp(-np.arange(h1 - h0) / SR / 0.015)
    out = np.tanh(out / np.abs(out).max() * 1.6) * 0.62
    fade = np.minimum(1, np.minimum(t / 1.5, (total - t) / 3.0))
    return out * np.clip(fade, 0, 1)


def clip_audio(path, start, dur):
    b = subprocess.run([FF, "-v", "error", "-ss", "%.3f" % start, "-i", path, "-t", "%.3f" % dur, "-ac", "1", "-ar", str(SR),
                        "-af", "highpass=f=90,loudnorm=I=-16:TP=-1.5", "-f", "f32le", "-"], capture_output=True).stdout
    return np.frombuffer(b, np.float32).astype(np.float64)


def soundtrack(starts, total, path):
    mus = music(total)
    n = len(mus)
    voice = np.zeros(n)
    duck = np.ones(n)
    for (t0, _), (kind, src, start, dur, ex) in zip(starts, SHOTS):
        if "audio" not in ex:
            continue
        a = clip_audio(os.path.join(DOC, *src), start, dur) * ex["audio"]
        i0 = int(t0 * SR)
        a = a[: max(0, n - i0)]
        ramp = np.minimum(1, np.minimum(np.arange(len(a)) / (0.15 * SR), (len(a) - np.arange(len(a))) / (0.3 * SR)))
        voice[i0:i0 + len(a)] += a * ramp
        duck[i0:i0 + len(a)] = np.minimum(duck[i0:i0 + len(a)], 0.22)
    k = int(0.35 * SR)
    c = np.concatenate(([0.0], np.cumsum(np.pad(duck, (k // 2, k - k // 2), mode="edge"))))
    duck = (c[k:] - c[:-k])[:n] / k                    # moving average, O(n)
    if INTRO_LAND:
        t = np.arange(n) / SR
        tl = INTRO_LAND
        # music sits low under the opening and opens up on the landing beat
        mus = mus * np.where(t < tl, 0.25 + 0.2 * np.clip(t / tl, 0, 1), np.minimum(1, 0.45 + (t - tl) / 0.4))
        g = np.random.default_rng(3)
        rise = (t > tl - 1.6) & (t < tl)                     # whoosh riser into the landing
        u = (t[rise] - (tl - 1.6)) / 1.6
        noise = np.convolve(g.standard_normal(rise.sum()), np.ones(6) / 6, mode="same")
        voice[rise] += 0.22 * u ** 2.5 * noise + 0.08 * u ** 2 * np.sin(2 * np.pi * (180 + 700 * u ** 2) * (t[rise] - tl))
        hit = (t >= tl) & (t < tl + 1.8)                     # sub boom + crack on impact
        u = t[hit] - tl
        voice[hit] += 0.9 * np.exp(-u / 0.55) * np.sin(2 * np.pi * (38 * u + 70 * 0.05 * (1 - np.exp(-u / 0.05))))
        voice[hit] += 0.35 * np.exp(-u / 0.06) * g.standard_normal(hit.sum())
    mix = np.tanh((mus * duck + voice * 0.95) * 1.1) * 0.82          # soft limiter: no clipped peaks
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())


# ------------------------------------------------------------------ main
def main():
    os.makedirs(J("build", "rekap"), exist_ok=True)
    starts, total = timeline()
    wav = J("build", "rekap", "soundtrack.wav")
    soundtrack(starts, total, wav)
    out = J("build", "rekap", "NovaBand_Rekap_Dokumentasi%s.mp4" % ("_preview" if PREVIEW else ""))
    enc = subprocess.Popen([FF, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H), "-r", str(FPS),
                            "-i", "-", "-i", wav, "-c:v", "libx264", "-preset", "veryfast" if PREVIEW else "medium",
                            "-crf", "28" if PREVIEW else "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                            "-movflags", "+faststart", "-shortest", out], stdin=subprocess.PIPE)
    tail = []
    for i, shot in enumerate(SHOTS):
        last = i == len(SHOTS) - 1
        n = int(round(shot[3] * FPS))
        buf = []
        for f, fr in enumerate(shot_frames(i, shot, starts[i][1])):
            if f < len(tail):
                w = (f + 1) / (len(tail) + 1)
                fr = (tail[f].astype(np.float32) * (1 - w) + fr.astype(np.float32) * w).astype(np.uint8)
            if not last and f >= n - XF:
                buf.append(fr)
                continue
            enc.stdin.write(np.ascontiguousarray(fr).tobytes())
        tail = buf
        print("%2d/%d  %-6s %4.1fs  @%5.1fs" % (i + 1, len(SHOTS), shot[0], shot[3], starts[i][0]), flush=True)
    enc.stdin.close()
    enc.wait()
    print(out, "%.1f s" % total)


if __name__ == "__main__":
    main()
