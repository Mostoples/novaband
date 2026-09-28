# Nova-Band — Web Apps (HTML · CSS · JS native)

**Live:** <https://novaband-id.web.app> · aplikasi di <https://novaband-id.web.app/app.html>

**Nova-Band: An AIoT-Driven Upper-Arm Wearable for Real-Time Physiological
Monitoring and Running Performance** — ISIF 2026, SMA Negeri 1 Surakarta.

Isi situs mengikuti materi terakhir di `ppt/NovaBand ISIF.pdf`.

| Halaman | Isi |
|---|---|
| `index.html` | Company profile: hero, kolaborator, Meet the Problem, rumusan masalah & tujuan, State of the Art, The Solution, Hardware Operation (PPG & IMU), produk 3D interaktif, IoT dashboard, timeline, hasil uji, pasar (TAM/SAM/SOM + proyeksi BEP), kemitraan, kesimpulan, showreel, tim |
| `app.html` | Dashboard pelari mengikuti mockup aplikasi di deck: Beranda, Aktivitas, Performa, Komunitas, Perangkat, Akun |

## Desain: white & clean

- Latar putih bersih; aksen **merah deck** `#7b2021`, wine tergelap `#4b070f`,
  rose `#c9a3a3` untuk motif titik, krem `#f3e3d3` — semua diambil dari deck.
- Poppins (sama dengan deck) + Fraunces italic untuk kata aksen.
- Kartu datar dengan border tipis dan bayangan lembut; tidak ada neumorphism lagi.
- Mode gelap tetap tersedia lewat toggle (disimpan di `localStorage`), tapi
  tampilan standarnya terang.
- Di ponsel, sidebar aplikasi berubah menjadi tab bar bawah seperti mockup.

## Struktur

```
novaband/
├── index.html · app.html · firebase.json
├── css/style.css            design system
├── js/
│   ├── main.js              tema, navigasi, reveal, counter, meter, grafik BEP, showreel
│   ├── three-scene.js       gelombang titik (hero) + viewer GLB (Produk)
│   ├── app.js               simulasi fisiologis + dashboard
│   ├── app-home.js          widget Beranda (grafik HR 24 jam, langkah, kalori, jarak)
│   └── firebase-init.js     bootstrap Firebase (opsional, non-blocking)
├── assets/                  semua dibangkitkan script — lihat assets/README.md
├── blender/
│   ├── novaband_model.py    model perangkat -> assets/novaband.glb
│   ├── novaband_assets.py   pustaka 46 aset 3D (Cycles, GPU)
│   └── novaband_reel3d.py   3 shot 3D untuk video
├── tools/
│   ├── pack-assets.py       render Blender -> WebP web
│   ├── make-showreel.py     kompositor video (PIL -> ffmpeg)
│   ├── contact-sheet.py     lembar review aset
│   └── shoot.py             QA visual: screenshot semua halaman & panel
├── ppt/                     materi sumber (TIDAK ikut ter-deploy)
└── build/                   keluaran antara (TIDAK ikut ter-deploy)
```

## Pipeline Blender (CLI)

```bash
B="C:\Program Files\Blender Foundation\Blender 4.0\blender.exe"

"$B" -b -P blender/novaband_model.py -- --no-render     # GLB untuk viewer 3D
"$B" -b -P blender/novaband_assets.py                    # 46 aset -> build/assets3d/
python tools/pack-assets.py                              # -> assets/3d/*.webp
"$B" -b -P blender/novaband_reel3d.py                    # 3 shot -> build/reel/
python tools/make-showreel.py                            # -> assets/novaband-showreel.*
```

- Semua geometri dibangun dari primitif di dalam script (tidak ada `.blend`
  biner), jadi hasilnya bisa diulang persis.
- Proporsi modul mengikuti foto produk di deck: 36 × 28 × 9 mm, memanjang
  searah strap, LED tersusun di sumbu panjangnya.
- Warna brand dikonversi sRGB → linear, dan render memakai view transform
  "Standard" supaya merahnya tidak bergeser jadi cokelat atau pink.
- Ikon di-render dengan *shadow catcher* di atas latar transparan;
  `pack-assets.py` memudarkan bayangan yang menyentuh tepi frame.

## Showreel

~39 detik, 1920×1080, 30 fps. Adegan: judul → orbit perangkat (LED berdenyut
1,5 Hz) → modul terurai 5 lapis → di lengan → alur PPG → sensor IMU → hasil uji
→ pasar → penutup dengan URL. Shot 3D dari Blender; tipografi, ikon, dan
transisi disusun oleh `tools/make-showreel.py`, lalu di-encode ke MP4 (H.264)
dan WebM (VP9).

## QA visual

```bash
python -m http.server 5174 --bind 127.0.0.1
python tools/shoot.py            # index, app (6 panel), mobile, dark -> build/shots/
```

> Error "MIME type text/plain" untuk `firebase-init.js` hanya muncul di
> server Python lokal di Windows; Firebase Hosting menyajikannya sebagai
> `text/javascript`.

## Deployment

```bash
firebase deploy --only hosting --project novaband-id
```

`ppt/`, `build/`, `blender/`, `tools/`, berkas `.md`, `.pdf`, dan `.ttf`
dikecualikan dari upload.

> **Soal API key Firebase:** key web memang dirancang ikut terkirim ke browser.
> Yang melindungi project adalah security rules Firestore/Storage dan
> pembatasan API key di Google Cloud console.

## Deck presentasi (PowerPoint, neumorphism)

Hasil: `ppt/NovaBand_Deck_Neumorph.pptx` (+ `.pdf`) — 27 slide, struktur mengikuti
`AQUENT_Deck_Neumorph.pdf`. Folder `ppt/` dan `deck/` tidak ikut ter-deploy.

```bash
B="C:\Program Files\Blender Foundation\Blender 4.0\blender.exe"
"$B" -b -P blender/deck_anim.py            # 42 loop animasi -> build/deck/anim/
# model produk detail (modul melengkung, jendela optik, strap anyaman + keeper):
for s in hero front arm exploded; do "$B" -b -P blender/novaband_hero.py -- --shot $s --samples 256 --out "$PWD/build/hero/final"; done
cp build/hero/final/hero.png build/assets3d/device-hero.png   # dst. untuk front / arm -> device-on-arm / exploded -> device-exploded
"$B" -b -P blender/novaband_hero.py -- --shot spin --samples 96 --spin-dir "$PWD/build/deck/anim/device-spin"
python tools/pack-gifs.py                  # -> deck/assets/anim/*.gif
python tools/prep-deck-assets.py           # foto deck, render statis, mockup ponsel
cd deck && npm install && node build-deck.js && cd ..
python deck/animate-deck.py                # dedup media + Morph + animasi masuk
```

- **Aset animasi (Blender CLI):** 38 ikon dengan gerak masing-masing (jantung
  berdetak, cincin giroskop berputar, lonceng berayun, pegas mengembang…),
  perangkat berputar, 2 ornamen melayang, dan 2 dekorasi sudut (cincin berputar,
  gelombang titik hidup). Semua loop mulus: gerak adalah fungsi periodik waktu.
- **Kenapa GIF:** satu-satunya animasi yang diputar PowerPoint sendiri, di editor
  dan slide show, tanpa klik. GIF dikomposit tepat di atas warna permukaan
  neumorphic `#EEE8E9`, dan paletnya dijamin memuat warna itu persis — jadi
  GIF menyatu dengan slide tanpa tepi kotak. Syaratnya: GIF hanya diletakkan di
  permukaan rata, tidak menimpa bayangan.
- **Neumorphism di PowerPoint:** satu shape hanya bisa punya satu bayangan luar,
  jadi setiap permukaan timbul adalah dua shape identik (bayangan gelap ke
  kanan-bawah, sorotan putih ke kiri-atas). Semua tetap shape native — bisa diedit.
- **Hidup:** transisi Morph antar-slide (fallback Fade di PowerPoint lama) dengan
  elemen berulang bernama `!!…` yang meluncur antar-slide, plus animasi masuk
  "fade up" bertahap yang berjalan otomatis saat slide dibuka.
- **Grafik native:** MAPE (bar), SUS (doughnut), proyeksi 2026–2030 (line).
- `animate-deck.py` juga memperbaiki dua bug keluaran pptxgenjs (tag penutup
  `innerShdw` yang salah, garis kosong) dan menggabungkan media duplikat
  (108 MB → 34 MB).

## Purwarupa: LILYGO T-Display-S3 Touch

### Casing (LibreCAD + FreeCAD)

```bash
python hardware/casing/sketch_dxf.py                      # sketsa DXF (LibreCAD) -> out/novaband_case_sketch.dxf
"C:/Program Files/LibreCAD/LibreCAD.exe" dxf2pdf -p 420x297 -s 2 -c -o hardware/casing/out/novaband_case_sketch.pdf hardware/casing/out/novaband_case_sketch.dxf
"C:/Program Files/FreeCAD 1.1/bin/freecadcmd.exe" hardware/casing/case_freecad.py   # -> STL (tutup, baki, tombol) + STEP
```

- Semua ukuran ada di satu file: `hardware/casing/case_params.py`. Angka board
  bersifat nominal (LILYGO: 62 × 26 × 10 mm) — **ukur dengan jangka sorong
  lalu sesuaikan** sebelum mencetak.
- Pod 78 × 34 × 15,8 mm, dua bagian (tutup + baki) + 2 tutup tombol, 4 sekrup
  M2 × 8 dari bawah, terowongan strap 40 × 2,4 mm di bawah board (strap 38–40 mm).
- Cetak PETG/ASA 0,2 mm, kedua bagian menghadap ke bawah pada sambungan, tanpa support.

### Firmware (`firmware/novaband_display`)

```powershell
powershell -ExecutionPolicy Bypass -File firmware\flash.ps1      # build aset + compile + flash app & aset
powershell -File firmware\flash.ps1 -SkipBuild -AppOnly           # hanya aplikasi
```

- Layar ST7789 lewat `esp_lcd` (bus i80 8-bit, DMA). Frame dibagi dua pita
  85 baris: core 0 menggambar pita atas, core 1 pita bawah → ±62 fps.
- Aset layar dibuat di Blender (`blender/screen_assets.py`: splash rack-focus,
  latar gym bokeh dari Sketchfab, sprite band berputar) lalu dipaketkan oleh
  `tools/fw_assets.py` ke partisi `assets` (0x310000) dan di-*mmap* dari flash.
- Kedalaman: bokeh gym (lambat) · kartu kaca (1:1) · bintik buram di depan
  (cepat) bergerak dengan kecepatan berbeda saat halaman digeser.
- Halaman: LIVE (HR + jantung 3D + gelombang PPG), RUN, READINESS, LINK (QR ke aplikasi).
- Tombol: KEY (GPIO14) halaman berikutnya / tekan lama mulai-jeda lari;
  BOOT (GPIO0) halaman sebelumnya / tekan lama simpan lari.
- T-Display-S3 tidak punya sensor PPG: tanpa sensor, detak jantung
  **disimulasikan** dan layar menandainya `DEMO`.
- Simulator PC (MSVC): `firmware\sim\build.bat` lalu
  `firmware\sim\sim.exe build\fw\assets.bin build\sim 30` — kode UI yang sama
  menulis frame untuk ditinjau (dan dipakai di deck & showreel).
- Firmware pabrik tersimpan di `build/firmware-backup/original_16MB.bin`
  (`esptool --port COM11 write-flash 0 build\firmware-backup\original_16MB.bin`).

### Koneksi band ↔ aplikasi

| Jalur | Browser | Detail |
|---|---|---|
| Bluetooth LE | Chrome/Edge (Android, Windows, macOS) | Web Bluetooth; layanan standar Heart Rate `0x180D` + Battery `0x180F`, dan layanan Nova-Band `4e420001-…` |
| USB-C | Chrome/Edge desktop | Web Serial, satu objek JSON per baris |

Protokol sama di kedua jalur (`firmware/novaband_display/src/protocol.h`):
telemetri 1 Hz, gelombang PPG 50 Hz; aplikasi mengirim `hello` (profil + jam),
`run`, `msg`, `alert`, `bright`, `page`. Uji BLE dari laptop: `python tools/ble_test.py`.

### PWA

`manifest.webmanifest` + `sw.js` (shell offline, network-first untuk halaman) +
ikon di `assets/pwa/`. Tombol **Pasang** muncul saat browser menawarkan instalasi.
Server lokal dengan MIME yang benar (service worker butuh `text/javascript`):
`python tools/serve.py 5175`.

## Showreel gym (Blender Cycles + Sketchfab)

```bash
python tools/sketchfab.py search "gym interior"                  # cari aset (token di build/sketchfab/.token)
python tools/sketchfab.py get <uid> <nama>                        # unduh glTF + catat kredit
"$B" -b -P blender/reel_gym.py -- --shot all                      # 6 shot -> build/reel2/
python tools/make-showreel2.py                                    # -> assets/novaband-showreel-gym.{mp4,webm}
```

Ruang gym, pelari, treadmill dan properti adalah model Sketchfab berlisensi
CC-BY (daftar lengkap: `build/sketchfab/credits.json`, juga di slide kredit
deck). Pod purwarupa, layar firmware yang hidup, dan NovaBand adalah model kami.
