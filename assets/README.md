# Aset

Semua berkas di folder ini **dibangkitkan oleh script** — jangan diedit manual,
jalankan ulang script-nya.

| Folder / berkas | Sumber | Isi |
|---|---|---|
| `3d/*.webp` | `blender/novaband_assets.py` → `tools/pack-assets.py` | 46 aset 3D Blender (38 ikon, 5 render perangkat, 3 dekorasi — lihat `3d/manifest.json`) |
| `img/*.webp` | diekstrak dari `ppt/NovaBand ISIF.pdf` | foto produk, mockup aplikasi, foto tim, foto uji coba, logo mitra, 4 ilustrasi masalah |
| `novaband.glb` | `blender/novaband_model.py` | model 3D yang bisa diputar di bagian Produk |
| `novaband-showreel.{mp4,webm}` + `-poster.jpg` | `blender/novaband_reel3d.py` → `tools/make-showreel.py` | video showreel 1920×1080 |

## Pustaka aset 3D (`3d/`)

Gaya "clean clay": badan matte putih/krem dengan aksen merah gelap dari deck,
cahaya studio lembut, satu bayangan kontak. Setiap aset dinormalisasi ke bola
satuan sebelum di-frame, jadi pencahayaan dan kamera identik dan semua ikon
terasa satu keluarga.

- **Fisiologi:** heart, blood-cells, led-sensor, photodetector, chip, microcontroller
- **Sensor gerak:** accelerometer, gyroscope, magnetometer
- **Sistem & konektivitas:** smartphone, cloud, shield, bell, ai-network, bluetooth, battery, wifi-iot
- **Metrik:** bar-chart, gauge, stopwatch, flame, footsteps, moon, spring-tendon
- **Hasil & bisnis:** medal, target-tiers, coins, calendar, lightbulb, clipboard, magnifier, warning, chain-link, map-pin, globe, school, gear, user
- **Perangkat:** device-hero, device-front, device-side, device-exploded, device-on-arm
- **Dekorasi:** dots-wave (motif titik dari deck), pills, ring-glossy

Tidak semua ikon dipakai di halaman sekarang; sisanya siap dipakai untuk
fitur atau materi promosi berikutnya. Karena gambar di-*lazy load*, ikon yang
tidak dipakai tidak pernah diunduh pengunjung.

## Membangun ulang

```bash
blender -b -P blender/novaband_assets.py -- --samples 96          # semua aset
blender -b -P blender/novaband_assets.py -- --only heart,gauge    # sebagian
python tools/pack-assets.py                                       # -> assets/3d/*.webp
```
