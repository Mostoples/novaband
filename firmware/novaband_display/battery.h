// Nova-Band — baterai Li-Po 1 sel di T-Display-S3 (pembagi 1:2 ke GPIO 4).
//
// Diporting dari modul baterai project Asawatch (touchscreen/battery.cpp), versi ringkas:
//   * MEDIAN 9 sampel tiap panggilan (burst transmit WiFi membuat tegangan ambles sesaat; median
//     membuang pencilan, rata-rata justru ikut tertarik), lalu dihaluskan.
//   * Kurva Li-Po NON-LINEAR (peta linear 3,3-4,15 V salah besar di tengah rentang).
//   * Dasar persen = MEDIAN dari minimum tiap slot 5 dtk selama 2 menit: beban singkat (WiFi, layar)
//     tidak menggesernya.
//   * Saat DICAS pin tidak mengukur sel: di board ini pin membaca rel USB (> 4,3 V) sehingga persen
//     lama "langsung 100%". Sekarang: persen dibekukan di nilai sebelum dicolok lalu naik pelan
//     (perkiraan waktu, BUKAN pengukuran) dan mentok 99%. Begitu dicabut, persen bergeser 1% per
//     3 dtk ke nilai terukur, tidak melompat.
//   * Persen terakhir disimpan di NVS, jadi reboot/brownout tidak menjatuhkan angka.
//
// KALIBRASI (sekali, dengan multimeter): ukur tegangan baterai SAAT TIDAK DICAS di konektor baterai
// (V_ukur), lihat "bv" di serial/RTDB (V_baca). DIVIDER_BARU = DIVIDER_LAMA * V_ukur / V_baca.
#pragma once
#include <Arduino.h>
#include <Preferences.h>

namespace battery {

static const int PIN = 4;
static const float DIVIDER = 2.0f;                 // Vbaterai / Vpin (dikalibrasi, lihat atas)
static const int PLUG_MV = 4300, UNPLUG_MV = 4250; // histeresis: di atas ini = USB (pin membaca rel USB)
static const float CHARGE_PCT_PER_MIN = 0.8f;      // perkiraan laju isi saat dicas (pagar, bukan pengukuran)

struct Pt { int mv, pct; };
static const Pt CURVE[] = {
  {4190, 100}, {4100, 92}, {4000, 85}, {3950, 78}, {3900, 70}, {3850, 62}, {3800, 55}, {3750, 47},
  {3700, 40},  {3650, 33}, {3600, 25}, {3550, 18}, {3500, 12}, {3450, 8},  {3400, 5},  {3300, 2},
  {3000, 0},
};
static const int CURVE_N = sizeof(CURVE) / sizeof(CURVE[0]);

inline int toPercent(int mv) {
  if (mv >= CURVE[0].mv) return 100;
  if (mv <= CURVE[CURVE_N - 1].mv) return 0;
  for (int i = 0; i < CURVE_N - 1; i++)
    if (mv <= CURVE[i].mv && mv > CURVE[i + 1].mv) {
      int dv = CURVE[i].mv - CURVE[i + 1].mv, dp = CURVE[i].pct - CURVE[i + 1].pct;
      return CURVE[i + 1].pct + ((mv - CURVE[i + 1].mv) * dp + dv / 2) / dv;
    }
  return 0;
}

namespace {
const int SLOTS = 24;                              // 24 x 5 dtk = 2 menit
Preferences prefs;
int saved = -1, pct = -1, pinMv = 0;
float emaMv = 0, prevMv = 0, chgPct = 0;
bool charging = false;
uint16_t slotMin[SLOTS];
int slotN = 0, slotI = 0, curSlotMin = 0, baseMv = 0, savedPct = -1;
uint32_t slotAt = 0, stepAt = 0, updAt = 0, saveAt = 0;

int median9(int* s) {
  for (int i = 1; i < 9; i++) for (int j = i; j > 0 && s[j] < s[j - 1]; j--) { int t = s[j]; s[j] = s[j - 1]; s[j - 1] = t; }
  return s[4];
}
void clearWindow() { slotN = slotI = 0; curSlotMin = 0; slotAt = 0; baseMv = 0; }
}  // namespace

inline void begin() {
  prefs.begin("batt", false);
  saved = prefs.getChar("pct", -1);
  analogReadResolution(12);
}

inline void save() {
  if (pct >= 0 && pct != savedPct) { prefs.putChar("pct", (int8_t)pct); savedPct = pct; }
}

// Panggil tiap ~500 ms dari loop().
inline void update() {
  uint32_t now = millis();
  int s[9];
  for (int i = 0; i < 9; i++) { s[i] = analogReadMilliVolts(PIN); delayMicroseconds(300); }
  pinMv = median9(s);
  float v = pinMv * DIVIDER;
  float dt = updAt ? (now - updAt) / 1000.f : .5f;
  updAt = now;

  bool first = emaMv == 0;
  emaMv = first ? v : emaMv * .8f + v * .2f;
  bool wasCharging = charging;
  if (!charging && (emaMv > PLUG_MV || (!first && v - prevMv >= 300))) charging = true;       // dicolok
  else if (charging && (emaMv < UNPLUG_MV || (!first && prevMv - v >= 300 && v < PLUG_MV))) charging = false;   // dicabut
  prevMv = v;

  if (charging != wasCharging || first) clearWindow();     // jendela median tidak boleh campur dua keadaan

  if (!charging) {
    // dasar = median minimum slot 5 dtk
    if (!slotAt) { slotAt = now; curSlotMin = (int)v; }
    if ((int)v < curSlotMin) curSlotMin = (int)v;
    if (now - slotAt >= 5000) {
      slotMin[slotI] = curSlotMin; slotI = (slotI + 1) % SLOTS; if (slotN < SLOTS) slotN++;
      slotAt = now; curSlotMin = (int)v;
    }
    if (slotN) {
      uint16_t t[SLOTS]; for (int i = 0; i < slotN; i++) t[i] = slotMin[i];
      for (int i = 1; i < slotN; i++) for (int j = i; j > 0 && t[j] < t[j - 1]; j--) { uint16_t x = t[j]; t[j] = t[j - 1]; t[j - 1] = x; }
      baseMv = t[slotN / 2];
    } else baseMv = (int)emaMv;
    int target = toPercent(baseMv);
    if (pct < 0) pct = (saved >= 0 && abs(saved - target) <= 10) ? saved : target;   // titik awal: simpanan kalau masih masuk akal
    else if (now - stepAt >= 3000) {                                                  // 1% per 3 dtk menuju nilai terukur
      stepAt = now;
      if (target > pct) pct++; else if (target < pct) pct--;
    }
    chgPct = pct;
  } else {
    if (pct < 0) { pct = saved >= 0 ? saved : 50; chgPct = pct; }          // boot di USB: sel tidak terukur, pakai simpanan
    chgPct += CHARGE_PCT_PER_MIN * dt / 60.f;
    int p = min(99, (int)chgPct);
    if (p > pct) pct = p;                                                  // hanya naik, mentok 99
  }
  if (now - saveAt >= 60000) { saveAt = now; save(); }
}

inline int percent() { return pct < 0 ? 0 : pct; }
inline bool isCharging() { return charging; }
inline int pinMillivolts() { return pinMv; }
inline int millivolts() { return charging ? 0 : (int)emaMv; }   // tegangan sel (0 = tidak terukur saat dicas)

}  // namespace battery
