// Nova-Band — real sensors on their own I2C bus (Wire1), read by a FreeRTOS task.
//
//   MAX30102  PPG   0x57  -> heart rate (beat detection on IR) + SpO2 (ratio of ratios)
//   MLX90614  IR    0x5A  -> skin temperature (object temperature)
//   MPU6050   IMU   0x68/69 -> steps + cadence: peak detection on the accelerometer magnitude
//   GY-50     gyro  0x69  -> fallback when there is no MPU6050: |w| peaks once per step for an upper-arm swing
//
// Wire (touch, GPIO 17/18) is left alone. Wire1 runs at 100 kHz because the
// MLX90614 is only specified to 100 kHz. Every sensor is optional: a missing
// one is skipped and the model keeps simulating that value.
//
// The task only writes `sensors::data`; loop() copies fresh values into the
// model (see applySensors in novaband_display.ino), so Model stays single-threaded.
#pragma once
#include <Arduino.h>
#include <MAX30105.h>
#include <Wire.h>
#include <heartRate.h>

#include "pedo_gyro.h"

namespace sensors {

static const int PIN_SDA = 10, PIN_SCL = 11;
static const uint8_t ADDR_MLX = 0x5A;
static const uint32_t VALID_MS = 4000;             // a reading older than this is dropped

struct Data {
  volatile float hr = 0, spo2 = 0, temp = 0, cadence = 0;
  volatile uint32_t hrAt = 0, spo2At = 0, tempAt = 0, cadAt = 0;   // millis() of the last good value, 0 = none
  volatile bool finger = false;
  volatile uint32_t beats = 0;                     // heartbeats detected so far
  static constexpr int WAVE_N = 160;
  float wave[WAVE_N] = {0};                        // normalised PPG, 50 Hz
  volatile uint32_t waveN = 0;                     // samples written so far
  struct Sec { uint16_t w, sd; uint8_t pk, st; };  // per detik: |w| maks (x10), deviasi (x100), puncak lolos ambang, langkah terhitung
  static constexpr int RING_N = 600;               // 10 menit
  Sec ring[RING_N] = {};
  volatile uint32_t ringN = 0;
  char gdbg[120] = "";                           // debug: register mentah GY-50
  volatile float wSd = 0;                          // debug: deviasi standar |w| (0 = sensor macet)
  volatile float wPeakRt = 0;                      // |w| tertinggi dalam ~2 dtk terakhir (untuk cloud)
  volatile float wPeak = 0;                        // debug: |w| tertinggi (deg/s) sejak terakhir dibaca
  volatile uint32_t wPeaks = 0;                    // debug: jumlah puncak |w| yang lolos ambang (sebelum gerbang)
  volatile uint32_t simUntil = 0;                  // uji: sinyal jalan sintetis sampai millis() ini (perintah serial "simwalk N")
  volatile uint32_t steps = 0;                     // validated steps since boot (the model diffs this)
  volatile bool hasMax = false, hasMlx = false, hasGyro = false, hasMpu = false;
};
inline Data data;

namespace {

MAX30105 ppg;
uint8_t gyroAddr = 0, mpuAddr = 0;

// ---- MAX30102: HR from beats, SpO2 from AC/DC of red vs IR
struct Ppg {
  float rates[4] = {0}; int rateN = 0, rateI = 0;
  uint32_t lastBeat = 0;
  float dcR = 0, dcI = 0, acR = 0, acI = 0;
  uint32_t nextSpo2 = 0;
  float spo2 = 0;

  bool odd = false;
  void pushWave(float v) {                         // every 2nd sample: 100 Hz -> 50 Hz
    odd = !odd;
    if (!odd) return;
    data.wave[data.waveN % Data::WAVE_N] = v;
    data.waveN = data.waveN + 1;
  }
  void reset() { rateN = rateI = 0; lastBeat = 0; dcR = dcI = acR = acI = 0; spo2 = 0; }

  void sample(uint32_t red, uint32_t ir, uint32_t now) {
    const bool on = ir > 20000;                    // tissue on the sensor
    data.finger = on;
    if (!on) { reset(); data.hrAt = data.spo2At = 0; pushWave(0); return; }

    if (checkForBeat((long)ir)) {
      data.beats = data.beats + 1;
      if (lastBeat) {
        float bpm = 60000.f / (now - lastBeat);
        if (bpm > 40 && bpm < 210) {
          rates[rateI] = bpm; rateI = (rateI + 1) % 4; if (rateN < 4) rateN++;
          float s = 0; for (int i = 0; i < rateN; i++) s += rates[i];
          data.hr = s / rateN; data.hrAt = now;
        }
      }
      lastBeat = now;
    }

    // slow mean (DC) and RMS of the deviation (AC), both channels
    if (!dcR) { dcR = red; dcI = ir; }
    dcR += (red - dcR) * .02f; dcI += (ir - dcI) * .02f;
    float dr = red - dcR, di = ir - dcI;
    acR += (dr * dr - acR) * .01f; acI += (di * di - acI) * .01f;
    pushWave(constrain((dcI - ir) / (2.5f * sqrtf(fmaxf(acI, 1.f))), -1.5f, 1.5f));   // blood volume = less IR back
    if (now >= nextSpo2) {
      nextSpo2 = now + 1000;
      if (acR > 1 && acI > 1 && dcR > 0 && dcI > 0) {
        float r = (sqrtf(acR) / dcR) / (sqrtf(acI) / dcI);
        float s = constrain(110.f - 25.f * r, 80.f, 100.f);   // empirical, not calibrated
        spo2 = spo2 ? spo2 * .8f + s * .2f : s;
        data.spo2 = spo2; data.spo2At = now;
      }
    }
    if (lastBeat && now - lastBeat > VALID_MS) { data.hrAt = 0; rateN = 0; }
  }
};
Ppg ppgState;

// ---- MLX90614
bool mlxRead(float& c) {
  Wire1.beginTransmission(ADDR_MLX);
  Wire1.write(0x07);                               // RAM: Tobj1
  if (Wire1.endTransmission(false) != 0) return false;
  if (Wire1.requestFrom((int)ADDR_MLX, 3) != 3) return false;
  uint8_t lo = Wire1.read(), hi = Wire1.read();
  Wire1.read();                                    // PEC, not checked
  if (hi & 0x80) return false;                     // error flag
  c = ((hi << 8) | lo) * 0.02f - 273.15f;
  return c > -20 && c < 100;
}

// ---- MPU6050 pedometer
// Same idea as the usual open-source ESP32/Arduino pedometers (magnitude of the accelerometer,
// gravity removed, peak = step, refractory time), plus an adaptive threshold (half of the recent
// peak height) and a "4 steps in a row" gate so a single arm movement is not counted as walking.
bool mpuWrite(uint8_t reg, uint8_t v) {
  Wire1.beginTransmission(mpuAddr); Wire1.write(reg); Wire1.write(v);
  return Wire1.endTransmission() == 0;
}
bool mpuInit() {
  for (uint8_t a : {(uint8_t)0x68, (uint8_t)0x69}) {
    mpuAddr = a;
    Wire1.beginTransmission(a); Wire1.write(0x75);
    if (Wire1.endTransmission(false) != 0 || Wire1.requestFrom((int)a, 1) != 1) continue;
    uint8_t id = Wire1.read();
    if (id != 0x68 && id != 0x70 && id != 0x72 && id != 0x98) continue;   // MPU6050/6500/9250 and clones
    return mpuWrite(0x6B, 0x01)                    // wake, PLL clock
        && mpuWrite(0x1A, 0x03)                    // DLPF 44 Hz
        && mpuWrite(0x1C, 0x10);                   // +-8 g, 4096 LSB/g
  }
  mpuAddr = 0;
  return false;
}
bool mpuRead(float& g) {
  Wire1.beginTransmission(mpuAddr); Wire1.write(0x3B);
  if (Wire1.endTransmission(false) != 0 || Wire1.requestFrom((int)mpuAddr, 6) != 6) return false;
  int16_t v[3];
  for (auto& x : v) { uint8_t h = Wire1.read(), l = Wire1.read(); x = (int16_t)((h << 8) | l); }
  float ax = v[0] / 4096.f, ay = v[1] / 4096.f, az = v[2] / 4096.f;
  g = sqrtf(ax * ax + ay * ay + az * az);
  return true;
}

struct Pedometer {
  float dc = 1, lp = 0, prev = 0, prev2 = 0, amp = .3f, cad = 0;
  uint32_t lastStep = 0;
  int streak = 0, pending = 0;
  void sample(float mag, uint32_t now) {
    dc += (mag - dc) * .02f;                       // gravity / slow drift
    lp += ((mag - dc) - lp) * .4f;                 // ~6 Hz low-pass
    if (prev > prev2 && prev >= lp && prev > fmaxf(.12f, amp * .5f) && now - lastStep > 240) {
      uint32_t dt = now - lastStep;
      bool chain = lastStep && dt < 1500;          // 40..250 steps/min
      lastStep = now;
      amp += (prev - amp) * .25f;
      if (!chain) { streak = 1; pending = 1; }
      else {
        streak++;
        float c = 60000.f / dt;
        cad = cad ? cad * .7f + c * .3f : c;
        if (streak < 4) pending++;
        else {
          data.steps = data.steps + pending + 1; pending = 0;   // commit the buffered steps once the gate opens
          data.cadence = cad; data.cadAt = now;
        }
      }
    }
    amp = fmaxf(amp * .9997f, .1f);
    prev2 = prev; prev = lp;
    if (lastStep && now - lastStep > 2000) { streak = pending = 0; cad = 0; data.cadAt = 0; lastStep = 0; }
  }
};
Pedometer pedState;

// ---- GY-50 (L3G4200D)
bool gyroWrite(uint8_t reg, uint8_t v) {
  Wire1.beginTransmission(gyroAddr); Wire1.write(reg); Wire1.write(v);
  return Wire1.endTransmission() == 0;
}
bool gyroInit() {
  for (uint8_t a : {(uint8_t)0x69, (uint8_t)0x68}) {
    gyroAddr = a;
    Wire1.beginTransmission(a); Wire1.write(0x0F);
    if (Wire1.endTransmission(false) != 0 || Wire1.requestFrom((int)a, 1) != 1) continue;
    if (Wire1.read() != 0xD3) continue;            // WHO_AM_I
    // power-cycle chip (bangunkan paksa), tunggu turn-on 250 ms, BDU mati (keluaran selalu diperbarui), 2000 dps
    gyroWrite(0x20, 0x00); delay(50);
    gyroWrite(0x24, 0x80); delay(20);              // CTRL_REG5: BOOT (muat ulang memori internal)
    delay(100);
    gyroWrite(0x24, 0x00);
    bool ok = gyroWrite(0x23, 0x20) && gyroWrite(0x22, 0x08) && gyroWrite(0x20, 0x0F);   // 2000 dps, DRDY int, 100 Hz XYZ on
    delay(300);
    return ok;
  }
  gyroAddr = 0;
  return false;
}
// Offset nol (zero-rate) GY-50 ~17 deg/s per unit: dibuang otomatis, tanpa kalibrasi manual.
//  - saat boot: rata-rata 1 dtk (diterima kalau deviasinya kecil, artinya jam diam)
//  - berjalan: tiap kali hampir diam (|w| < 3 deg/s selama 0,5 dtk) bias digeser pelan ke pembacaan
float gBias[3] = {0, 0, 0};
int gQuiet = 0;
bool gyroRaw(float* g) {
  Wire1.beginTransmission(gyroAddr); Wire1.write(0x28 | 0x80);   // auto-increment
  if (Wire1.endTransmission(false) != 0 || Wire1.requestFrom((int)gyroAddr, 6) != 6) return false;
  int16_t v[3];
  for (auto& x : v) { uint8_t l = Wire1.read(), h = Wire1.read(); x = (int16_t)((h << 8) | l); }
  for (int i = 0; i < 3; i++) g[i] = v[i] * .07f;                // 70 mdps/LSB at 2000 dps
  return true;
}
void gyroBiasInit() {
  float sum[3] = {0}, sq[3] = {0}; int n = 0;
  for (int i = 0; i < 100; i++) {
    float g[3];
    if (gyroRaw(g)) { n++; for (int k = 0; k < 3; k++) { sum[k] += g[k]; sq[k] += g[k] * g[k]; } }
    delay(10);
  }
  if (n < 50) return;
  bool still = true;
  for (int k = 0; k < 3; k++) { float m = sum[k] / n, sd = sqrtf(fmaxf(sq[k] / n - m * m, 0)); if (sd > 2.f) still = false; }
  if (still) for (int k = 0; k < 3; k++) gBias[k] = sum[k] / n;
  Serial.printf("# gyro bias %s: %.1f %.1f %.1f deg/s\n", still ? "dipakai" : "diabaikan (jam bergerak saat boot)", sum[0] / n, sum[1] / n, sum[2] / n);
}
uint32_t gSameAt = 0; float gLast[3] = {0, 0, 0};
volatile bool gFrozen = false;                      // keluaran persis sama > 3 dtk = sensor tidak sampling
bool gyroRead(float& dps) {
  float g[3];
  if (!gyroRaw(g)) return false;
  uint32_t nowMs = millis();
  if (g[0] != gLast[0] || g[1] != gLast[1] || g[2] != gLast[2]) { gSameAt = nowMs; gFrozen = false; }
  else if (nowMs - gSameAt > 3000) gFrozen = true;
  for (int k = 0; k < 3; k++) gLast[k] = g[k];
  float c[3], m2 = 0;
  for (int k = 0; k < 3; k++) { c[k] = g[k] - gBias[k]; m2 += c[k] * c[k]; }
  dps = sqrtf(m2);
  if (dps < 3.f) { if (++gQuiet >= 50) for (int k = 0; k < 3; k++) gBias[k] += (g[k] - gBias[k]) * .02f; }
  else gQuiet = 0;
  return true;
}

// Penghitung langkah giroskop lengan atas (inti di pedo_gyro.h, diuji di firmware/tools/pedo_test.cpp);
// di sini hanya statistik diagnosis per detik + menyalin hasil ke `data`.
struct Cadence {
  GyroPedo core;
  uint32_t rtAt = 0;
  float rtMax = 0, rtSum = 0, rtSq = 0; int rtN = 0;
  float sMax = 0, sSum = 0, sSq = 0; int sN = 0;     // jendela 1 dtk untuk ring
  uint32_t secAt = 0, lastPk = 0, lastSt = 0;
  void sample(float w, uint32_t now) {
    if (w > data.wPeak) data.wPeak = w;
    if (now - rtAt > 2000) {
      float mean = rtN ? rtSum / rtN : 0;
      data.wPeakRt = rtMax; data.wSd = sqrtf(fmaxf(rtN ? rtSq / rtN - mean * mean : 0, 0));
      rtMax = 0; rtSum = rtSq = 0; rtN = 0; rtAt = now;
    }
    if (w > rtMax) rtMax = w;
    rtSum += w; rtSq += w * w; rtN++;
    if (w > sMax) sMax = w;
    sSum += w; sSq += w * w; sN++;
    core.sample(w, now);
    data.wPeaks = core.peaks;
    data.steps = core.steps;
    if (core.cadAt) { data.cadence = core.cadence; data.cadAt = core.cadAt; } else data.cadAt = 0;
    if (now - secAt >= 1000) {                     // satu baris statistik per detik, tetap tercatat walau WiFi putus
      float m = sN ? sSum / sN : 0, sd = sqrtf(fmaxf(sN ? sSq / sN - m * m : 0, 0));
      Data::Sec& e = data.ring[data.ringN % Data::RING_N];
      e.w = (uint16_t)fminf(sMax * 10, 65000); e.sd = (uint16_t)fminf(sd * 100, 65000);
      e.pk = (uint8_t)min<uint32_t>(core.peaks - lastPk, 255); e.st = (uint8_t)min<uint32_t>(core.steps - lastSt, 255);
      lastPk = core.peaks; lastSt = core.steps;
      data.ringN = data.ringN + 1;
      sMax = sSum = sSq = 0; sN = 0; secAt = now;
    }
  }
};
Cadence cadState;

// Debug: register kunci GY-50 + data mentah; dipanggil dari task sensor (satu-satunya pemakai Wire1).
void gyroDebug(uint32_t now) {
  static uint32_t at = 0;
  if (now - at < 1000) return;
  at = now;
  uint8_t r[8] = {0}; const uint8_t regs[8] = {0x0F, 0x20, 0x21, 0x22, 0x23, 0x24, 0x26, 0x27};
  for (int i = 0; i < 8; i++) {
    Wire1.beginTransmission(gyroAddr); Wire1.write(regs[i]);
    if (Wire1.endTransmission(false) == 0 && Wire1.requestFrom((int)gyroAddr, 1) == 1) r[i] = Wire1.read();
  }
  uint8_t o[6] = {0};
  Wire1.beginTransmission(gyroAddr); Wire1.write(0x28 | 0x80);
  if (Wire1.endTransmission(false) == 0 && Wire1.requestFrom((int)gyroAddr, 6) == 6) for (auto& b : o) b = Wire1.read();
  snprintf(data.gdbg, sizeof data.gdbg, "WHO=%02X C1=%02X C2=%02X C3=%02X C4=%02X C5=%02X T=%02X ST=%02X OUT=%02X%02X %02X%02X %02X%02X",
           r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], o[1], o[0], o[3], o[2], o[5], o[4]);
}

volatile bool stopReq = false, stopped = false;

void task(void*) {
  uint32_t mlxAt = 0, probeAt = 0, reinitAt = 0;
  TickType_t wake = xTaskGetTickCount();
  for (;;) {
    if (stopReq) { stopped = true; vTaskDelay(pdMS_TO_TICKS(50)); continue; }
    uint32_t now = millis();
    if (data.hasMax) {
      ppg.check();
      while (ppg.available()) {
        ppgState.sample(ppg.getFIFORed(), ppg.getFIFOIR(), millis());
        ppg.nextSample();
      }
    }
    // Pulih otomatis, tanpa upload ulang: sensor langkah yang baru disolder terdeteksi sendiri (tiap 3 dtk),
    // dan giroskop yang macet (keluaran persis sama > 3 dtk) di-power-cycle ulang (maks tiap 5 dtk).
    if (!data.hasMpu && !data.hasGyro && now - probeAt >= 3000) {
      probeAt = now;
      data.hasMpu = mpuInit();
      if (!data.hasMpu && gyroInit()) { gyroBiasInit(); data.hasGyro = true; }
      if (data.hasMpu || data.hasGyro) Serial.printf("# sensor langkah terdeteksi: %s\n", data.hasMpu ? "MPU6050" : "GY-50");
    }
    if (data.simUntil && (int32_t)(data.simUntil - now) > 0) {   // uji jalur lengkap tanpa sensor fisik
      static float ph = 0; ph += 2 * M_PI * 0.92f * .01f;       // ~110 langkah/menit, ayun lengan atas
      cadState.sample(fabsf(60.f * cosf(ph)) + fabsf(0.4f * sinf(ph * 37.f)), now);
    } else if (data.hasMpu) {
      float g;
      if (mpuRead(g)) pedState.sample(g, now);
    } else if (data.hasGyro) {
      float w;
      if (gyroRead(w)) cadState.sample(w, now);
      gyroDebug(now);
      if (gFrozen && now - reinitAt >= 5000) {
        reinitAt = now;
        bool ok = gyroInit();
        Serial.printf("# GY-50 macet (keluaran beku) -> init ulang: %s (cek daya modul / solder)\n", ok ? "ok" : "gagal");
        if (!ok) data.hasGyro = false;               // hilang dari bus: probe lagi tiap 3 dtk
        gSameAt = now; gFrozen = false;
      }
    }
    if (data.hasMlx && now - mlxAt >= 500) {
      mlxAt = now;
      float c;
      if (mlxRead(c)) { data.temp = data.tempAt ? data.temp * .6f + c * .4f : c; data.tempAt = now; }
    }
    vTaskDelayUntil(&wake, pdMS_TO_TICKS(10));
  }
}

}  // namespace

inline void begin() {
  Wire1.begin(PIN_SDA, PIN_SCL, 100000);
  Wire1.setTimeOut(20);

  Serial.print("# i2c scan Wire1:");                // every address that ACKs, to debug wiring
  for (uint8_t a = 1; a < 127; a++) {
    Wire1.beginTransmission(a);
    if (Wire1.endTransmission() == 0) Serial.printf(" 0x%02X", a);
  }
  Serial.println();

  data.hasMax = ppg.begin(Wire1, I2C_SPEED_STANDARD);
  if (data.hasMax)
    ppg.setup(0x3C, 4, 2, 400, 411, 4096);         // LED 12 mA, avg 4, red+IR, 400 sps -> 100 Hz, 18-bit

  Wire1.beginTransmission(ADDR_MLX);
  data.hasMlx = Wire1.endTransmission() == 0;

  data.hasMpu = mpuInit();
  data.hasGyro = !data.hasMpu && gyroInit();
  if (data.hasGyro) gyroBiasInit();       // the MPU6050 already gives steps, and shares 0x68/0x69

  Serial.printf("# sensors: MAX30102 %s, MLX90614 %s, MPU6050 %s, GY-50 %s\n", data.hasMax ? "ok" : "--",
                data.hasMlx ? "ok" : "--", data.hasMpu ? "ok" : "--", data.hasGyro ? "ok" : "--");
  if (data.hasMax || data.hasMlx || data.hasMpu || data.hasGyro)
    xTaskCreatePinnedToCore(task, "sensors", 4096, nullptr, 1, nullptr, 1);
}

// Power down every sensor (MAX30102 LEDs off, gyro power-down) before deep sleep.
inline void shutdown() {
  if (!(data.hasMax || data.hasMlx || data.hasMpu || data.hasGyro)) return;
  stopReq = true;
  for (int i = 0; i < 50 && !stopped; i++) delay(2);   // let the task finish its I2C transaction
  if (data.hasMax) ppg.shutDown();
  if (data.hasMpu) mpuWrite(0x6B, 0x40);               // sleep
  if (data.hasGyro) gyroWrite(0x20, 0x00);             // CTRL_REG1: power-down
}

}  // namespace sensors
