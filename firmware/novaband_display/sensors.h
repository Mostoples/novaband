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
    return gyroWrite(0x20, 0x0F)                   // 100 Hz, normal mode, XYZ on
        && gyroWrite(0x23, 0xA0);                  // block update, 2000 dps
  }
  gyroAddr = 0;
  return false;
}
bool gyroRead(float& dps) {
  Wire1.beginTransmission(gyroAddr); Wire1.write(0x28 | 0x80);   // auto-increment
  if (Wire1.endTransmission(false) != 0 || Wire1.requestFrom((int)gyroAddr, 6) != 6) return false;
  int16_t v[3];
  for (auto& x : v) { uint8_t l = Wire1.read(), h = Wire1.read(); x = (int16_t)((h << 8) | l); }
  float gx = v[0] * .07f, gy = v[1] * .07f, gz = v[2] * .07f;    // 70 mdps/LSB at 2000 dps
  dps = sqrtf(gx * gx + gy * gy + gz * gz);
  return true;
}

// One peak of the smoothed |w| = one step (arm swing has two |w| peaks per cycle).
struct Cadence {
  float lp = 0, prev = 0, prev2 = 0, peak = 60, cad = 0;
  uint32_t lastPeak = 0;
  void sample(float w, uint32_t now) {
    lp += (w - lp) * .35f;
    if (prev > prev2 && prev >= lp && prev > fmaxf(40.f, peak * .5f) && now - lastPeak > 250) {
      if (lastPeak && now - lastPeak < 1000) {
        float c = 60000.f / (now - lastPeak);
        cad = cad ? cad * .7f + c * .3f : c;
        data.cadence = cad; data.cadAt = now;
        data.steps = data.steps + 1;
      }
      lastPeak = now;
      peak += (prev - peak) * .2f;
    }
    peak *= .9995f;
    prev2 = prev; prev = lp;
    if (lastPeak && now - lastPeak > 2500) { cad = 0; data.cadAt = 0; lastPeak = 0; }
  }
};
Cadence cadState;

volatile bool stopReq = false, stopped = false;

void task(void*) {
  uint32_t mlxAt = 0;
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
    if (data.hasMpu) {
      float g;
      if (mpuRead(g)) pedState.sample(g, now);
    } else if (data.hasGyro) {
      float w;
      if (gyroRead(w)) cadState.sample(w, now);
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
  data.hasGyro = !data.hasMpu && gyroInit();       // the MPU6050 already gives steps, and shares 0x68/0x69

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
