# Wiring Nova-Band — T-Display-S3 + MAX30102 + GY-50 + MLX90614

Ketiga sensor memakai **satu bus I²C sendiri (`Wire1`)** di GPIO 10 dan 11. Bus
touch bawaan board (GPIO 17/18) tidak disentuh. Semua sensor di **3V3**, bukan 5 V.

## 1. Tabel wiring

| Sinyal | T-Display-S3 | MAX30102 | GY-50 (L3G4200D) | MLX90614 (GY-906) |
|---|---|---|---|---|
| Daya | **3V3** | VIN | VCC | VIN |
| Ground | **GND** | GND | GND | GND |
| I²C data | **GPIO 10** | SDA | SDA | SDA |
| I²C clock | **GPIO 11** | SCL | SCL | SCL |
| Interrupt / DRDY | — | INT (tidak dipakai) | INT1, INT2 (tidak dipakai) | — |
| Pilih alamat | — | — | SDO → 3V3 (0x69) atau GND (0x68) | — |

## 2. Alamat I²C

| Perangkat | Alamat | Bus |
|---|---|---|
| CST816 (touch, bawaan) | 0x15 | `Wire` — GPIO 18 / 17 |
| MAX30102 | 0x57 | `Wire1` — GPIO 10 / 11 |
| GY-50 (L3G4200D) | 0x69 (SDO=3V3) atau 0x68 (SDO=GND) | `Wire1` |
| MLX90614 | 0x5A | `Wire1` |

Tidak ada alamat yang bentrok. Firmware mencoba 0x69 lalu 0x68 untuk GY-50.

## 3. Diagram

```
                      ┌────────────── T-Display-S3 ──────────────┐
 LiPo 3.7 V ──JST──►  │                                          │
                      │  3V3 ─────┬───────┬────────┬──► VIN/VCC   │
                      │  GND ─────┼───┬───┼───┬────┼──► GND       │
                      │  IO10 ────┼───┼───┼───┼────┼──► SDA       │
                      │  IO11 ────┼───┼───┼───┼────┼──► SCL       │
                      └───────────┼───┼───┼───┼────┼─────────────┘
                                  │   │   │   │    │
                             MAX30102  GY-50   MLX90614
                              (0x57)  (0x69)    (0x5A)
```

Semua SDA disambung ke IO10 yang sama, semua SCL ke IO11 yang sama (topologi bus, bukan satu-satu).

## 4. Fungsi tiap sensor di firmware

| Sensor | Yang dibaca | Dipakai untuk |
|---|---|---|
| MAX30102 | IR + Red, 100 Hz | detak jantung (deteksi puncak), SpO₂ (rasio AC/DC) |
| MLX90614 | suhu objek, 2 Hz | suhu kulit → field `tmp` di telemetri |
| GY-50 | gyro 3 sumbu, 100 Hz | kadensi (puncak |ω| = 1 langkah) → langkah |

Kalau sensor tidak terdeteksi saat boot, nilainya tetap simulasi (`demo`).
Status boot tercetak di serial: `# sensors: MAX30102 ok, MLX90614 ok, GY-50 ok`.

## 5. Catatan pemasangan

- **Pull-up:** tiap modul sudah punya pull-up SDA/SCL. Tiga modul paralel itu wajar; kalau bus
  error, lepas pull-up pada satu-dua modul.
- **MAX30102** harus menempel ke kulit tanpa tekanan berlebih dan tanpa cahaya luar. Di lengan
  atas, sinyal lebih lemah daripada di jari; naikkan arus LED (`0x3C` di `sensors.h`) bila perlu.
- **MLX90614** diarahkan ke kulit dari jarak dekat (beberapa mm). Ini suhu kulit, bukan suhu inti.
- **GY-50** dipasang kaku pada band. Kadensi dihitung dari ayunan lengan atas, jadi perlu diuji
  saat lari sungguhan. GY-50 hanya gyro, tanpa akselerometer.
- **SpO₂** memakai rumus empiris (`110 − 25·R`), belum dikalibrasi. Jangan dipakai sebagai angka medis.
- Pin bebas yang masih tersisa: 1, 2, 3, 12, 13, 43, 44.
- Jangan pakai GPIO 15, 38, 0, 14: dipakai power periferal, backlight, dan tombol.
