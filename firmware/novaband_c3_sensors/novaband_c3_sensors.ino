// Nova-Band — tes sensor di ESP32-C3: MAX30102 (0x57) + MLX90614 (0x5A) di satu bus I2C.
//   SDA = GPIO 8, SCL = GPIO 9, semua sensor di 3V3.
// Terkirim ke Firebase Realtime Database: /devices/{uid}/live (lihat cloud.h, kredensial di secrets.h).
// Serial 115200. Library: "SparkFun MAX3010x Pulse and Proximity Sensor Library".
// Board: ESP32C3 Dev Module, USB CDC On Boot = Enabled.
#include <Wire.h>
#include <MAX30105.h>
#include <heartRate.h>

#include "cloud.h"   // WiFi + Firebase Realtime Database

static const int PIN_SDA = 8, PIN_SCL = 9;
static const uint8_t ADDR_MLX = 0x5A;
static const int PIN_LINK = 3;                       // dari GPIO 12 jam LilyGo (+ pull-down 100k ke GND)
static const uint32_t LINK_GRACE_MS = 8000;           // tunggu jam selesai boot sebelum menilai LOW
static const uint32_t LINK_LOW_MS = 3000;             // LOW selama ini = jam mati

MAX30105 ppg;
bool hasMax = false, hasMlx = false;
float bpm = 0;
uint32_t lastBeat = 0, lastPrint = 0, lastMlx = 0;
float tempC = NAN;

bool mlxRead(float& c) {
  Wire.beginTransmission(ADDR_MLX);
  Wire.write(0x07);                                // RAM: Tobj1
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom((int)ADDR_MLX, 3) != 3) return false;
  uint8_t lo = Wire.read(), hi = Wire.read();
  Wire.read();                                     // PEC
  if (hi & 0x80) return false;
  c = ((hi << 8) | lo) * 0.02f - 273.15f;
  return c > -20 && c < 100;
}

void scan() {
  Serial.print("# i2c scan:");
  int n = 0;
  for (uint8_t a = 1; a < 127; a++) {
    Wire.beginTransmission(a);
    if (Wire.endTransmission() == 0) { Serial.printf(" 0x%02X", a); n++; }
  }
  Serial.println(n ? "" : " (tidak ada perangkat - cek kabel SDA/SCL/daya)");
}

// Jam mati (GPIO 3 LOW): matikan LED MAX30102 dan WiFi, lalu deep sleep. Bangun lagi saat GPIO 3 HIGH.
void sleepUntilWatchOn() {
  Serial.println("# jam mati -> ESP32-C3 deep sleep");
  Serial.flush();
  if (hasMax) ppg.shutDown();
  WiFi.disconnect(true, false);
  WiFi.mode(WIFI_OFF);
  esp_deep_sleep_enable_gpio_wakeup(1ULL << PIN_LINK, ESP_GPIO_WAKEUP_GPIO_HIGH);
  esp_deep_sleep_start();
}

void linkCheck(uint32_t now) {
  static uint32_t lowSince = 0;
  if (now < LINK_GRACE_MS) return;
  if (digitalRead(PIN_LINK)) { lowSince = 0; return; }
  if (!lowSince) lowSince = now;
  if (now - lowSince >= LINK_LOW_MS) sleepUntilWatchOn();
}

// Konfigurasi MAX30102 (LED ~12 mA, avg 4, red+IR). Dipanggil saat boot dan saat pemulihan.
bool maxStart() {
  if (!ppg.begin(Wire, I2C_SPEED_STANDARD)) return false;
  ppg.setup(0x3C, 4, 2, 400, 411, 4096);
  return true;
}

// Bus I2C yang terganggu bisa membuat konfigurasi gagal (LED 0 mA -> IR selalu 0): reset + konfigurasi ulang.
void maxWatchdog(uint32_t now) {
  static uint32_t lastGood = 0, lastTry = 0;
  if (!hasMax) {
    if (now - lastTry >= 5000) { lastTry = now; hasMax = maxStart(); if (hasMax) Serial.println("# MAX30102 terdeteksi (percobaan ulang)"); }
    return;
  }
  if (ppg.getIR() > 0) { lastGood = now; return; }
  if (now - lastGood < 3000 || now - lastTry < 3000) return;
  lastTry = now;
  ppg.softReset();
  delay(100);
  Serial.printf("# MAX30102 IR=0 terus -> reset & konfigurasi ulang: %s\n", maxStart() ? "ok" : "gagal");
}

void setup() {
  pinMode(PIN_LINK, INPUT_PULLDOWN);
  Serial.begin(115200);
  delay(1500);
  Wire.begin(PIN_SDA, PIN_SCL, 100000);
  Wire.setTimeOut(20);
  scan();

  hasMax = maxStart();
  Wire.beginTransmission(ADDR_MLX);
  hasMlx = Wire.endTransmission() == 0;
  Serial.printf("# MAX30102 %s, MLX90614 %s\n", hasMax ? "ok" : "--", hasMlx ? "ok" : "--");
  cloud::begin("NovaBand-C3");
}

void loop() {
  uint32_t now = millis();
  linkCheck(now);
  maxWatchdog(now);
  uint32_t ir = 0;

  if (hasMax) {
    ppg.check();
    while (ppg.available()) {
      ir = ppg.getFIFOIR();
      if (ir > 20000 && checkForBeat((long)ir)) {
        if (lastBeat) {
          float b = 60000.f / (now - lastBeat);
          if (b > 40 && b < 210) bpm = bpm ? bpm * .7f + b * .3f : b;
        }
        lastBeat = now;
      }
      ppg.nextSample();
    }
    if (now - lastBeat > 4000) bpm = 0;
  }

  if (hasMlx && now - lastMlx >= 500) {
    lastMlx = now;
    float c;
    if (mlxRead(c)) tempC = c;
  }

  if (now - lastPrint >= 1000) {
    lastPrint = now;
    uint32_t irNow = hasMax ? ppg.getIR() : 0;
    bool finger = hasMax && irNow > 20000;
    Serial.printf("IR=%lu jari=%s BPM=%.0f Suhu=%.1fC wifi=%s cloud=%s(%d)\n", (unsigned long)irNow, finger ? "ya" : "tidak",
                  bpm, tempC, cloud::status.wifi ? "ok" : "--", cloud::status.lastOk ? "ok" : "--", cloud::status.lastCode);
    char j[200];
    snprintf(j, sizeof j, "{\"t\":\"m\",\"hr\":%d,\"ir\":%lu,\"finger\":%d,\"tmp\":%.1f,\"mx\":%d,\"ml\":%d}", (int)(bpm + .5f),
             (unsigned long)irNow, finger, isnan(tempC) ? 0.f : tempC, hasMax, hasMlx);   // mx/ml = sensor terdeteksi
    cloud::publish(j);
  }
}
