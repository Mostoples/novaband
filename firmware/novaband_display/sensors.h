// Nova-Band — real sensors on their own I2C bus (Wire1), read by a FreeRTOS task.
//
//   MAX30102  PPG   0x57  -> heart rate (beat detection on IR) + SpO2 (ratio of ratios)
//   MLX90614  IR    0x5A  -> skin temperature (object temperature)
//   GY-50     gyro  0x69  -> cadence: L3G4200D, |w| peaks once per step for an upper-arm swing
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
  volatile bool hasMax = false, hasMlx = false, hasGyro = false;
};
inline Data data;

namespace {

MAX30105 ppg;
uint8_t gyroAddr = 0;

// ---- MAX30102: HR from beats, SpO2 from AC/DC of red vs IR
struct Ppg {
  float rates[4] = {0}; int rateN = 0, rateI = 0;
  uint32_t lastBeat = 0;
  float dcR = 0, dcI = 0, acR = 0, acI = 0;
  uint32_t nextSpo2 = 0;
  float spo2 = 0;

  void reset() { rateN = rateI = 0; lastBeat = 0; dcR = dcI = acR = acI = 0; spo2 = 0; }

  void sample(uint32_t red, uint32_t ir, uint32_t now) {
    const bool on = ir > 20000;                    // tissue on the sensor
    data.finger = on;
    if (!on) { reset(); data.hrAt = data.spo2At = 0; return; }

    if (checkForBeat((long)ir)) {
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

void task(void*) {
  uint32_t mlxAt = 0;
  TickType_t wake = xTaskGetTickCount();
  for (;;) {
    uint32_t now = millis();
    if (data.hasMax) {
      ppg.check();
      while (ppg.available()) {
        ppgState.sample(ppg.getFIFORed(), ppg.getFIFOIR(), millis());
        ppg.nextSample();
      }
    }
    if (data.hasGyro) {
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

  data.hasMax = ppg.begin(Wire1, I2C_SPEED_STANDARD);
  if (data.hasMax)
    ppg.setup(0x3C, 4, 2, 400, 411, 4096);         // LED 12 mA, avg 4, red+IR, 400 sps -> 100 Hz, 18-bit

  Wire1.beginTransmission(ADDR_MLX);
  data.hasMlx = Wire1.endTransmission() == 0;

  data.hasGyro = gyroInit();

  Serial.printf("# sensors: MAX30102 %s, MLX90614 %s, GY-50 %s\n", data.hasMax ? "ok" : "--",
                data.hasMlx ? "ok" : "--", data.hasGyro ? "ok" : "--");
  if (data.hasMax || data.hasMlx || data.hasGyro)
    xTaskCreatePinnedToCore(task, "sensors", 4096, nullptr, 1, nullptr, 1);
}

}  // namespace sensors
