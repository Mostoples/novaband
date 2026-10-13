# Panduan Teknisi — Nova-Band

Dokumen ini untuk teknisi yang melanjutkan pengerjaan purwarupa Nova-Band:
firmware di LILYGO T-Display-S3 Touch, casing cetak 3D, aplikasi web (PWA),
serta aset 3D, deck dan video. Penjelasan pipeline lengkap ada di
[README.md](../README.md).

## 1. Peta repositori

| Folder | Isi |
|---|---|
| `firmware/novaband_display/` | Firmware ESP32-S3 (Arduino). `src/` = kode UI portabel (gfx, ui, model, protocol) |
| `firmware/sim/` | Simulator PC (MSVC) — menjalankan kode UI yang sama, menulis frame ke gambar |
| `firmware/prebuilt/` | Biner siap flash (bootloader, partisi, aplikasi, aset layar) |
| `firmware/flash.ps1` | Build + flash sekali jalan |
| `hardware/casing/` | Parameter casing, sketsa LibreCAD (DXF/PDF), model FreeCAD (STL/STEP) di `out/` |
| `index.html`, `app.html`, `js/`, `css/`, `sw.js`, `manifest.webmanifest` | Situs + aplikasi web (PWA), di-deploy ke Firebase Hosting |
| `js/band-link.js` | Koneksi ke band: Web Bluetooth + Web Serial |
| `blender/` | Semua model & render 3D (Blender CLI, tanpa file .blend) |
| `tools/` | Skrip Python: paket aset firmware, Sketchfab, kompositor video, QA |
| `deck/` | Generator deck PowerPoint (pptxgenjs) |
| `ppt/` | Materi sumber deck ISIF + PDF deck hasil |

Tidak ikut di git (dibuat ulang lewat pipeline): `build/` (render, unduhan
Sketchfab, backup firmware pabrik), `node_modules/`, file `.pptx` hasil.

## 2. Perangkat lunak yang dibutuhkan

| Keperluan | Alat | Versi yang dipakai |
|---|---|---|
| Flash saja | Arduino CLI + core `esp32:esp32` (menyediakan esptool) | core 3.3.7 |
| Build firmware | + library **ArduinoJson** | 7.4.x |
| Simulator UI | Visual Studio 2022 (C++ desktop) | MSVC 19.x |
| Casing | LibreCAD, FreeCAD, Python + `ezdxf`, `PyMuPDF` | LibreCAD 2.2, FreeCAD 1.1 |
| Aset 3D / video | Blender, ffmpeg | Blender 4.0, ffmpeg 6+ |
| Aset firmware | Python + `numpy`, `Pillow`, `qrcode` | Python 3.12 |
| Deck | Node.js + `npm install` di `deck/` | Node 20 |
| Uji BLE dari laptop | Python + `bleak` | — |
| Deploy web | Firebase CLI (akses ke project `novaband-id`) | — |

## 3. Tugas yang paling sering

### Flash board (tanpa build)

```powershell
powershell -ExecutionPolicy Bypass -File firmware\flash.ps1 -Prebuilt
```

Colokkan T-Display-S3 lewat USB-C. Port dicari otomatis (atau `-Port COM11`).
Jika gagal masuk mode download: tahan **BOOT**, tekan **RST**, lepas BOOT, ulangi.

### Ubah firmware, build, flash

```powershell
arduino-cli lib install ArduinoJson
powershell -ExecutionPolicy Bypass -File firmware\flash.ps1 -AppOnly   # build aset + firmware, flash aplikasi saja
```

Opsi board (sudah ada di skrip):
`esp32:esp32:esp32s3:CDCOnBoot=cdc,FlashSize=16M,PSRAM=opi,PartitionScheme=custom`.
Partisi ada di `firmware/novaband_display/partitions.csv`
(aplikasi 3 MB, aset layar 12 MB di `0x310000`).

Log serial (baris diawali `#`): `arduino-cli monitor -p COM11 -c baudrate=115200`.
Setiap 5 detik muncul `# fps …  render … ms  heap …`.

Jika `asset_ids.h` berubah (menambah/mengurangi aset), aset **dan** aplikasi
harus di-flash bersama — firmware menolak paket aset yang tidak cocok (layar merah
anggur + pesan di serial).

### Cek UI tanpa board

```bat
firmware\sim\build.bat
firmware\sim\sim.exe firmware\prebuilt\assets.bin build\sim 30
```

Menghasilkan 750 frame (25 detik skenario: boot, hello dari aplikasi, geser
halaman, mulai lari, koneksi BLE, pesan pelatih, alarm HR). Baris terakhir
mencetak `band mismatches 0` — render dua pita harus identik dengan render penuh.

### Cetak casing

1. Ukur board dengan jangka sorong, ubah angka `BOARD_*`, `GLASS_*`, `BTN_*`
   di `hardware/casing/case_params.py` bila berbeda.
2. `python hardware/casing/sketch_dxf.py` (gambar kerja LibreCAD) dan
   `freecadcmd hardware/casing/case_freecad.py` (STL/STEP).
3. Cetak PETG/ASA, layer 0,2 mm, kedua bagian menghadap bawah pada sambungan,
   tanpa support. Tombol: berdiri tegak.
4. Rakit: board ke baki → tutup tombol ke lubangnya → tutup → 4 × M2×8
   self-tapping dari bawah. Strap 38–40 mm lewat terowongan bawah.

### Aplikasi web

```bash
python tools/serve.py 5175          # server lokal dengan MIME benar (wajib untuk service worker)
firebase deploy --only hosting --project novaband-id
```

Web Bluetooth/Web Serial butuh HTTPS atau `localhost`. Safari iOS tidak
mendukung keduanya — di iPhone hanya mode simulasi.

Uji BLE ujung-ke-ujung dari laptop: `python tools/ble_test.py`.

## 4. Pin T-Display-S3 yang dipakai

| Fungsi | GPIO |
|---|---|
| LCD data D0–D7 | 39, 40, 41, 42, 45, 46, 47, 48 |
| LCD WR / RD / DC / CS / RST | 8 / 9 / 7 / 6 / 5 |
| Backlight (PWM) | 38 |
| Power periferal (**harus HIGH**) | 15 |
| Touch CST816 SDA / SCL / INT / RST | 18 / 17 / 16 / 21 |
| Tombol BOOT / KEY | 0 / 14 |
| ADC baterai (pembagi 1:2) | 4 |
| Bebas untuk sensor (mis. PPG MAX30102 via I²C/Qwiic) | 1, 2, 3, 10–13, 43, 44 |

## 5. Hal yang perlu diketahui

- **Detak jantung masih simulasi.** Board tidak punya sensor PPG. Layar dan
  telemetri menandainya `DEMO` / `"demo":1`. Untuk sensor sungguhan: baca sensor
  di `loop()` lalu panggil `model.setRealHr(bpm, uptime())` (lihat
  `src/model.h`); aplikasi juga bisa mengirim `{"cmd":"hr","v":...}`.
- **Arah sentuh.** Mengikuti contoh LILYGO (swap XY + mirror X). Jika geser
  terbalik, ubah `TOUCH_FLIP_X` di `novaband_display.ino`. Koordinat mentah
  dicetak di serial sebagai `# touch raw`.
- **Performa.** Target 60 fps. Dua core menggambar dua pita layar. Hindari
  `sqrtf`/pembagian per piksel di `gfx.cpp` (FPU ESP32-S3 tanpa sqrt hardware);
  ukur dengan log `# fps`.
- **UUID BLE** dan format pesan ada di `src/protocol.h` dan harus sama dengan
  `js/band-link.js`.
- **Firmware pabrik** LILYGO tersimpan di mesin pengembang
  (`build/firmware-backup/original_16MB.bin`), tidak di git; LILYGO juga
  menyediakannya di repo resmi T-Display-S3.

## 6. Aturan kerja di repo

- Kerjakan di branch (`fitur/…`, `perbaikan/…`), buka Pull Request ke `main`.
- **Jangan commit rahasia.** Token Sketchfab disimpan di
  `build/sketchfab/.token` (di-ignore). Kunci web Firebase di
  `js/firebase-init.js` memang publik; keamanannya lewat rules Firestore.
- Jangan commit hasil render besar atau `.pptx` hasil; lampirkan di GitHub
  Release bila perlu dibagikan.
- Aset Sketchfab berlisensi CC-BY: setiap aset baru wajib tercatat di
  `credits.json` (otomatis lewat `tools/sketchfab.py get`) dan di slide kredit.
- Setelah mengubah firmware, perbarui `firmware/prebuilt/` agar rekan tanpa
  toolchain tetap bisa flash versi terbaru.

## 7. Maskot Nova: animasi, aplikasi, dan video penjelasan

Nova (cheetah, `blender/mascot.py`) dianimasikan lewat kode, tanpa file .blend.

| Langkah | Perintah | Hasil |
|---|---|---|
| Render 8 klip (idle, wave, run, talk, flex, thumbs, cheer, alert) | `python blender/mascot_anim.py --anim all --samples 24` | `build/mascot_anim/<klip>/f_####.png` |
| Klip untuk aplikasi | `python tools/make-mascot-webp.py` | `assets/mascot/nova-<klip>.webm` (VP9 transparan) + `.webp` (cadangan Safari) |
| Narasi suara | `python tools/nova-voice.py` | `build/nova_vo/*.mp3` (edge-tts, suara id-ID; butuh internet) |
| Video penjelasan | `python tools/make-nova-explainer.py` | `assets/nova-explainer.{mp4,webm}` + poster |

- Render Blender 4.0 kadang crash di tengah klip; driver otomatis mengulang dan
  melanjutkan dari frame terakhir. Jalankan render panjang sebagai proses
  terpisah, jangan dua driver sekaligus (frame saling menimpa).
- Naskah narasi ada di `SCRIPT` dalam `tools/nova-voice.py`; ubah di sana lalu
  jalankan ulang dengan `--force`, kemudian render ulang videonya.
- Di aplikasi, perilaku Nova diatur `js/app-nova.js` (membaca `window.NovaState`):
  melambai saat dibuka, berlari saat sesi berjalan, gestur stop saat ada
  peringatan detak jantung, melompat saat sesi selesai. Tampilan imersif ada di
  `css/app-future.css` (dimuat hanya oleh `app.html`).

## 8. AI Buddy (chat dengan Nova) + suara Pocket TTS

- Tombol bulat Nova di kanan bawah `app.html` membuka chat (`js/nova-buddy.js`, `css/nova-buddy.css`).
  Otak: pencocok intent di perangkat (`assets/buddy/intents.json`, ID + EN, 28 intent) yang
  membaca data live `window.NovaState`; bisa memulai/menjeda sesi. Pertanyaan darurat
  (nyeri dada, sesak napas, mau pingsan) selalu dicek lebih dulu → arahkan berhenti + 112/119.
- Suara: **Bahasa Inggris** → Kyutai Pocket TTS di laptop:
  `pip install pocket-tts` lalu `python tools/nova-tts-server.py` (port 8765, CPU, unduh model saat
  pertama jalan). Aplikasi mendeteksinya otomatis (label "Voice: Pocket TTS").
  **Bahasa Indonesia** → suara bawaan HP/browser (Pocket TTS belum punya model Indonesia).
- Saat sesi berjalan Nova bicara sendiri: peringatan bila HR > ambang (maks. tiap 45 dtk) dan setiap 1 km.
- Tidak ada LLM cloud; teks hanya dikirim ke server Pocket TTS lokal.
