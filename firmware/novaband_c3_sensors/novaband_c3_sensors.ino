// Nova-Band — tes sensor di ESP32-C3: MAX30102 (0x57) + MLX90614 (0x5A) di satu bus I2C.
//   SDA = GPIO 8, SCL = GPIO 9, semua sensor di 3V3.
// Terkirim ke Firebase Realtime Database: /devices/{uid}/live (lihat cloud.h, kredensial di secrets.h).
// Serial 115200. Library: "SparkFun MAX3010x Pulse and Proximity Sensor Library".
// Board: ESP32C3 Dev Module, USB CDC On Boot = Enabled.
#include <Wire.h>
#include <MAX30105.h>
#include <heartRate.h>

#include <ArduinoOTA.h>

#include "cloud.h"   // WiFi + Firebase Realtime Database

static const int PIN_SDA = 8, PIN_SCL = 9;
static const uint8_t ADDR_MLX = 0x5A;
static const int PIN_LINK = 3;                       // dari GPIO 12 jam LilyGo (+ pull-down 100k ke GND)
static const uint32_t LINK_GRACE_MS = 8000;           // tunggu jam selesai boot sebelum menilai LOW
static const uint32_t LINK_LOW_MS = 3000;             // LOW selama ini = jam mati

MAX30105 ppg;
bool hasMax = false, hasMlx = false;
uint32_t lastPrint = 0, lastMlx = 0;
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

// ---- MAX30102: detak jantung, SpO2, dan arus LED otomatis (tanpa kalibrasi manual)
//  * Jari terdeteksi dari IR (> 20000); saat jari dilepas semua penghitung di-reset, jadi interval beat
//    lama tidak pernah dipakai lagi.
//  * Deteksi beat sendiri (bukan checkForBeat SparkFun, yang menolak sinyal beramplitudo besar): puncak
//    sinyal "volume darah" (baseline lambat - IR yang di-low-pass), ambang = 50% amplitudo puncak
//    terakhir (menyesuaikan sendiri), jeda minimal 300 ms. Waktu dihitung dari nomor sampel (100 Hz),
//    bukan millis(), jadi interval tidak terpengaruh jitter loop.
//  * HR = median 5 interval beat terakhir (satu beat nyasar tidak menggeser angka), hanya 40..200 bpm.
//  * SpO2 = polinomial referensi Maxim dari R = (AC/DC merah)/(AC/DC IR); tampil setelah jari menempel
//    >= 8 dtk dan >= 5 beat. INDIKATIF, bukan alat medis.
//  * Arus LED disesuaikan tiap 1 dtk supaya DC IR tetap di 60k..180k (maks 262k = jenuh):
//    kulit gelap/terang atau jari tipis/tebal tidak perlu pengaturan manual.
static const uint32_t FINGER_IR = 20000;
uint8_t ledAmp = 0x3C;                              // ~12 mA awal
struct Ppg {
  float rates[5] = {0}; int rateN = 0, rateI = 0;
  uint32_t lastBeat = 0, fingerAt = 0, nextAgc = 0, nextSpo2 = 0;
  float dcR = 0, dcI = 0, acR = 0, acI = 0, spo2 = 0, bpm = 0;
  int beats = 0;
  bool finger = false;
  float base = 0, lp = 0, prev = 0, prev2 = 0, amp = 0;
  uint32_t tick = 0, lastPeakTick = 0;          // tick = nomor sampel; 1 sampel = 10 ms

  void reset() { rateN = rateI = beats = 0; lastBeat = 0; base = lp = prev = prev2 = amp = 0; lastPeakTick = 0; dcR = dcI = acR = acI = 0; spo2 = bpm = 0; }
  float median() {
    float t[5]; for (int i = 0; i < rateN; i++) t[i] = rates[i];
    for (int i = 1; i < rateN; i++) for (int j = i; j > 0 && t[j] < t[j - 1]; j--) { float x = t[j]; t[j] = t[j - 1]; t[j - 1] = x; }
    return t[rateN / 2];
  }
  void sample(uint32_t red, uint32_t ir, uint32_t now) {
    bool on = ir > FINGER_IR;
    if (!on) { if (finger) reset(); finger = false; fingerAt = 0; return; }
    if (!finger) { finger = true; fingerAt = now; }

    tick++;
    if (!base) base = lp = ir;
    base += (ir - base) * .005f;                                  // baseline ~2 dtk
    lp += (ir - lp) * .25f;                                       // low-pass ~4 Hz
    float v = base - lp;                                          // volume darah naik -> IR turun -> v naik
    bool peak = prev > prev2 && prev >= v && prev > fmaxf(15.f, amp * .5f) && (!lastPeakTick || tick - lastPeakTick > 30);
    if (peak) {
      beats++;
      if (lastPeakTick) {
        float b = 6000.f / (tick - lastPeakTick);                  // 60000 ms / (selisih * 10 ms)
        if (b >= 40 && b <= 200) {
          rates[rateI] = b; rateI = (rateI + 1) % 5; if (rateN < 5) rateN++;
          if (rateN >= 3) bpm = median();
        }
      }
      lastPeakTick = tick;
      lastBeat = now;
      amp += (prev - amp) * .3f;                                  // amplitudo puncak, ikut naik/turun
    }
    amp *= .999f;
    prev2 = prev; prev = v;
    if (lastBeat && now - lastBeat > 4000) { bpm = 0; rateN = rateI = 0; lastBeat = 0; }

    if (!dcR) { dcR = red; dcI = ir; }
    dcR += (red - dcR) * .02f; dcI += (ir - dcI) * .02f;           // rata-rata lambat (DC)
    float dr = red - dcR, di = ir - dcI;
    acR += (dr * dr - acR) * .01f; acI += (di * di - acI) * .01f;  // RMS selisih (AC)
    if (now >= nextSpo2) {
      nextSpo2 = now + 1000;
      if (now - fingerAt >= 8000 && beats >= 5 && acR > 1 && acI > 1 && dcR > 0 && dcI > 0) {
        float R = (sqrtf(acR) / dcR) / (sqrtf(acI) / dcI);
        float v = constrain(-45.060f * R * R + 30.354f * R + 94.845f, 70.f, 100.f);
        spo2 = spo2 ? spo2 * .85f + v * .15f : v;
      }
    }
  }
  // dipanggil tiap 1 dtk: jaga DC IR di jendela sehat dengan menyetel arus LED merah+IR
  void agc(uint32_t now) {
    if (now < nextAgc) return;
    nextAgc = now + 1000;
    if (!finger || dcI <= 0) return;
    int a = ledAmp;
    if (dcI > 180000 && a > 0x10) a = max(0x10, a * 3 / 4);
    else if (dcI < 60000 && a < 0x7F) a = min(0x7F, a * 5 / 4 + 1);
    if (a != ledAmp) { ledAmp = a; ppg.setPulseAmplitudeRed(a); ppg.setPulseAmplitudeIR(a); }
  }
};
Ppg ppgState;

// Konfigurasi MAX30102 (LED ~12 mA, avg 4, red+IR). Dipanggil saat boot dan saat pemulihan.
bool maxStart() {
  if (!ppg.begin(Wire, I2C_SPEED_STANDARD)) return false;
  ppg.setup(ledAmp, 4, 2, 400, 411, 4096);
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

// Update firmware lewat WiFi (casing tertutup, USB tidak terjangkau). Hanya aktif saat jam hidup & WiFi tersambung.
//   arduino-cli upload -b esp32:esp32:esp32c3:CDCOnBoot=cdc -p <IP-C3> --upload-field password=<OTA_PASS dari secrets.h> novaband_c3_sensors
// IP C3 ada di serial ("# cloud: WiFi ok <ip>") dan di RTDB: /devices/esp32c3/info/ip. Komputer harus satu jaringan.
void otaTick() {
  static bool started = false;
  if (!started) {
    if (WiFi.status() != WL_CONNECTED) return;
    ArduinoOTA.setHostname("novaband-c3");
    ArduinoOTA.setPassword(OTA_PASS);
    ArduinoOTA.onStart([]() { if (hasMax) ppg.shutDown(); Serial.println("# OTA mulai"); });
    ArduinoOTA.onEnd([]() { Serial.println("# OTA selesai, restart"); });
    ArduinoOTA.begin();
    started = true;
    Serial.printf("# OTA siap: novaband-c3 @ %s\n", WiFi.localIP().toString().c_str());
  }
  ArduinoOTA.handle();
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
  Serial.println("# fw: OTA-1 (diunggah lewat WiFi)");
  Serial.printf("# MAX30102 %s, MLX90614 %s\n", hasMax ? "ok" : "--", hasMlx ? "ok" : "--");
  cloud::begin("NovaBand-C3");
}

void loop() {
  uint32_t now = millis();
  linkCheck(now);
  otaTick();
  maxWatchdog(now);
  uint32_t ir = 0;

  if (hasMax) {
    ppg.check();
    while (ppg.available()) {
      ppgState.sample(ppg.getFIFORed(), ppg.getFIFOIR(), millis());
      ppg.nextSample();
    }
    ppgState.agc(now);
  }

  if (hasMlx && now - lastMlx >= 500) {
    lastMlx = now;
    float c;
    if (mlxRead(c)) tempC = c;
  }

  if (now - lastPrint >= 1000) {
    lastPrint = now;
    uint32_t irNow = hasMax ? ppg.getIR() : 0;
    bool finger = hasMax && ppgState.finger;
    float hr = finger ? ppgState.bpm : 0, sp = finger ? ppgState.spo2 : 0;
    Serial.printf("IR=%lu led=0x%02X jari=%s BPM=%.0f SpO2=%.0f Suhu=%.1fC wifi=%s cloud=%s(%d)\n", (unsigned long)irNow, ledAmp,
                  finger ? "ya" : "tidak", hr, sp, tempC, cloud::status.wifi ? "ok" : "--", cloud::status.lastOk ? "ok" : "--", cloud::status.lastCode);
    char j[260];
    snprintf(j, sizeof j, "{\"t\":\"m\",\"hr\":%d,\"sp\":%d,\"ir\":%lu,\"led\":%d,\"finger\":%d,\"tmp\":%.1f,\"mx\":%d,\"ml\":%d}",
             (int)(hr + .5f), (int)(sp + .5f), (unsigned long)irNow, ledAmp, finger, isnan(tempC) ? 0.f : tempC, hasMax, hasMlx);   // mx/ml = sensor terdeteksi
    cloud::publish(j);
  }
}
