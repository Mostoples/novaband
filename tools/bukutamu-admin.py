"""
Buku tamu pameran Nova-Band — alat tim (butuh login admin: gcloud atau `firebase login`).

    python tools/bukutamu-admin.py kode ["Nama acara"]   # buat/ganti kode acara rahasia + poster QR
    python tools/bukutamu-admin.py ekspor               # CSV kontak + foto -> data/bukutamu/<tanggal>/
    python tools/bukutamu-admin.py hapus-uji            # hapus entri yang namanya diawali "UJI COBA"

Data:
  bukutamu_config/acara   {kode, acara}            tidak bisa dibaca browser (dipakai aturan Firestore)
  bukutamu_publik/{uid}   {nama, instansi, foto, acara, dibuat}        tampil di /hadir/ dan landing page
  bukutamu_privat/{uid}   {nama, hp, instagram, instansi, setuju, kode, acara, dibuat}   hanya admin
Semua keluaran berisi data pribadi: disimpan di data/ (tidak masuk git, tidak ikut deploy).
"""
import base64
import csv
import datetime as dt
import importlib.util
import json
import os
import secrets
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "bukutamu")
PROJECT = "novaband-id"
SITE = "https://novaband-id.web.app"
DOCS = "https://firestore.googleapis.com/v1/projects/%s/databases/(default)/documents" % PROJECT

spec = importlib.util.spec_from_file_location("kx", os.path.join(ROOT, "tools", "kuesioner-export.py"))
KX = importlib.util.module_from_spec(spec)
spec.loader.exec_module(KX)                       # token() + val(): same admin login as the questionnaire export
TOKEN = None


def call(method, url, body=None):
    global TOKEN
    TOKEN = TOKEN or KX.token()
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None, method=method,
                                 headers={"Authorization": "Bearer " + TOKEN, "Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        txt = r.read()
    return json.loads(txt) if txt else {}


def listing(col):
    rows, page = [], ""
    while True:
        r = call("GET", "%s/%s?pageSize=300%s" % (DOCS, col, "&pageToken=" + page if page else ""))
        for d in r.get("documents", []):
            f = {k: KX.val(v) for k, v in d.get("fields", {}).items()}
            f["_id"] = d["name"].rsplit("/", 1)[1]
            rows.append(f)
        page = r.get("nextPageToken")
        if not page:
            return rows


def kode(acara):
    code = secrets.token_urlsafe(9)
    call("PATCH", DOCS + "/bukutamu_config/acara",
         {"fields": {"kode": {"stringValue": code}, "acara": {"stringValue": acara}}})
    os.makedirs(OUT, exist_ok=True)
    url = "%s/bukutamu/?k=%s" % (SITE, code)
    qr_page = "%s/bukutamu/qr.html#k=%s" % (SITE, code)
    with open(os.path.join(OUT, "kode.txt"), "w", encoding="utf-8") as f:
        f.write("acara: %s\nkode: %s\nbuku tamu: %s\nposter QR: %s\ndaftar hadir: %s/hadir/\n" % (acara, code, url, qr_page, SITE))
    poster(url, acara)
    print("acara      :", acara)
    print("buku tamu  :", url)
    print("poster QR  :", qr_page)
    print("daftar hadir:", SITE + "/hadir/")
    print("disimpan   :", os.path.join(OUT, "kode.txt"), "+ poster-bukutamu.png")


def poster(url, acara):
    """A4 poster (PNG, 150 dpi) with the QR, for printing."""
    import qrcode
    from PIL import Image, ImageDraw, ImageFont
    W, H = 1240, 1754
    im = Image.new("RGB", (W, H), (26, 6, 16))
    d = ImageDraw.Draw(im)
    F = lambda n, s: ImageFont.truetype(os.path.join(ROOT, "build", "fonts", n), s)
    def ctext(y, s, f, fill):
        d.text((W // 2, y), s, font=f, fill=fill, anchor="mm")
    ctext(150, "Nova-Band", F("Poppins-ExtraBold.ttf", 70), (255, 255, 255))
    ctext(270, "BUKU TAMU", F("Poppins-ExtraBold.ttf", 130), (255, 210, 160))
    ctext(370, "Scan · isi nama · selfie bareng Nova!", F("Poppins-SemiBold.ttf", 46), (243, 227, 211))
    q = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=22, border=3)
    q.add_data(url); q.make(fit=True)
    qi = q.make_image(fill_color="#1a0610", back_color="white").convert("RGB").resize((860, 860), Image.NEAREST)
    d.rounded_rectangle((W // 2 - 470, 450, W // 2 + 470, 1390), 50, fill=(255, 255, 255))
    im.paste(qi, (W // 2 - 430, 490))
    mascot = os.path.join(ROOT, "assets", "img", "mascot-wink.webp")
    if os.path.exists(mascot):
        m = Image.open(mascot).convert("RGBA"); m.thumbnail((330, 330))
        im.paste(m, (W - m.width - 40, H - m.height - 150), m)
    ctext(1470, acara, F("Poppins-SemiBold.ttf", 44), (255, 255, 255))
    ctext(1540, "Nomor HP & Instagram tidak ditampilkan publik.", F("Poppins-Regular.ttf", 34), (215, 200, 205))
    ctext(1660, "novaband-id.web.app", F("Poppins-Bold.ttf", 44), (255, 79, 99))
    im.save(os.path.join(OUT, "poster-bukutamu.png"))


def ekspor():
    pub = {r["_id"]: r for r in listing("bukutamu_publik")}
    priv = listing("bukutamu_privat")
    day = dt.date.today().isoformat()
    out = os.path.join(OUT, day)
    os.makedirs(os.path.join(out, "foto"), exist_ok=True)
    rows = []
    for p in sorted(priv, key=lambda r: r.get("dibuat", "")):
        pb = pub.get(p["_id"], {})
        foto = ""
        if str(pb.get("foto", "")).startswith("data:image/jpeg;base64,"):
            foto = "foto/%s_%s.jpg" % (p.get("dibuat", "")[:19].replace(":", "").replace("-", ""), p["_id"][:6])
            with open(os.path.join(out, foto), "wb") as f:
                f.write(base64.b64decode(pb["foto"].split(",", 1)[1]))
        wib = dt.datetime.fromisoformat(p["dibuat"].replace("Z", "+00:00")) + dt.timedelta(hours=7) if p.get("dibuat") else None
        rows.append({"waktu (WIB)": wib.strftime("%Y-%m-%d %H:%M") if wib else "", "nama": p.get("nama", ""),
                     "instansi": p.get("instansi", ""), "hp": p.get("hp", ""), "instagram": p.get("instagram", ""),
                     "acara": p.get("acara", ""), "foto": foto})
    path = os.path.join(out, "bukutamu_%s.csv" % day)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:      # utf-8-sig: opens cleanly in Excel
        w = csv.DictWriter(f, fieldnames=["waktu (WIB)", "nama", "instansi", "hp", "instagram", "acara", "foto"])
        w.writeheader(); w.writerows(rows)
    print(len(rows), "tamu ->", path)


def hapus_uji():
    n = 0
    for col in ("bukutamu_privat", "bukutamu_publik"):
        for r in listing(col):
            if str(r.get("nama", "")).upper().startswith("UJI COBA"):
                call("DELETE", "%s/%s/%s" % (DOCS, col, r["_id"])); n += 1
    print(n, "dokumen uji dihapus")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "kode":
        kode(sys.argv[2] if len(sys.argv) > 2 else "Pameran Nova-Band · " + dt.date.today().strftime("%d %B %Y"))
    elif cmd == "ekspor":
        ekspor()
    elif cmd == "hapus-uji":
        hapus_uji()
    else:
        print(__doc__)
