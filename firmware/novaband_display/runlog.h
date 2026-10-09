// Nova-Band — perekam lari di ESP. Tiap lari (start -> stop) dirangkum jadi satu rekaman dan
// dititipkan ke cloud::saveRun(), yang mengantre di NVS lalu mengirimnya ke
// /devices/{role}/runs/{id} di Realtime Database. Bentuk rekaman = bentuk riwayat di web
// (js/app.js saveActivity): at, sec, dist, steps, kcal, hrAvg, hrMax, splits[], hr[].
#pragma once
#include <Arduino.h>
#include <time.h>

#include "cloud.h"
#include "src/model.h"

namespace runlog {

static constexpr int HR_N = 64, SPLIT_N = 40;

struct Rec {
  bool active = false;
  int lastSec = -1;
  float dist = 0, kcal = 0;
  uint32_t steps = 0;
  int sec = 0, n = 0, step = 1, bucketSum = 0, bucketN = 0;   // hr[] is decimated: `step` seconds per point
  uint8_t hr[HR_N];
  uint16_t splits[SPLIT_N];
  int nSplits = 0, hrCnt = 0, hrMax = 0, lastSplitSec = 0;
  uint32_t hrSum = 0;
};
static Rec r;

static void addHr(int v) {
  r.bucketSum += v; r.bucketN++;
  if (r.bucketN < r.step) return;
  r.hr[r.n++] = (uint8_t)(r.bucketSum / r.bucketN);
  r.bucketSum = r.bucketN = 0;
  if (r.n == HR_N) {                                   // penuh: gabung berpasangan, resolusi jadi separuh
    for (int i = 0; i < HR_N / 2; i++) r.hr[i] = (uint8_t)((r.hr[2 * i] + r.hr[2 * i + 1]) / 2);
    r.n = HR_N / 2; r.step *= 2;
  }
}

static long long nowEpoch(const Model& md) {
  if (md.timeValid) return md.clockNow();              // waktu dari HP (sudah termasuk zona)
  time_t t = time(nullptr);                            // atau NTP dari WiFi
  return t > 1700000000 ? (long long)t + md.tzMin * 60LL : 0;
}

static void finish(const Model& md) {
  r.active = false;
  if (r.sec < 10) return;                              // terlalu pendek, bukan lari
  long long end = nowEpoch(md);
  long long at = end ? (end - r.sec) * 1000LL : 0;
  char id[24];
  if (at) snprintf(id, sizeof id, "%lld", at);
  else snprintf(id, sizeof id, "u%lu", (unsigned long)esp_random());   // jam belum tahu waktu: id acak, tetap unik
  static char js[900];
  int o = snprintf(js, sizeof js, "{\"at\":%lld,\"sec\":%d,\"dist\":%.3f,\"steps\":%lu,\"kcal\":%d,\"hrAvg\":%d,\"hrMax\":%d,\"src\":\"esp\",\"splits\":[",
                   at, r.sec, r.dist, (unsigned long)r.steps, (int)(r.kcal + .5f), r.hrCnt ? (int)(r.hrSum / r.hrCnt) : 0, r.hrMax);
  for (int i = 0; i < r.nSplits; i++) o += snprintf(js + o, sizeof js - o, "%s%u", i ? "," : "", r.splits[i]);
  o += snprintf(js + o, sizeof js - o, "],\"hr\":[");
  for (int i = 0; i < r.n && o < (int)sizeof js - 8; i++) o += snprintf(js + o, sizeof js - o, "%s%u", i ? "," : "", r.hr[i]);
  snprintf(js + o, sizeof js - o, "]}");
  Serial.printf("# lari selesai: %d s, %.2f km -> antre ke RTDB (%s)\n", r.sec, r.dist, id);
  cloud::saveRun(id, js);
}

// Panggil sesering mungkin dari loop(); murah kalau tidak ada lari.
inline void tick(const Model& md) {
  const Metrics& m = md.m;
  if (m.running && !r.active) { r = Rec(); r.active = true; }
  if (!r.active) return;
  if (!m.running) { finish(md); return; }              // berhenti: pakai nilai terakhir yang tercatat
  if (m.paused) return;
  int sec = (int)m.elapsed;
  if (sec == r.lastSec) return;
  r.lastSec = sec; r.sec = sec;
  r.dist = m.dist; r.kcal = m.kcal; r.steps = m.steps;
  int hr = (!md.real || md.hrOk) ? (int)(m.hr + .5f) : 0;
  addHr(hr);
  if (hr > 0) { r.hrSum += hr; r.hrCnt++; if (hr > r.hrMax) r.hrMax = hr; }
  if (m.dist >= r.nSplits + 1 && r.nSplits < SPLIT_N) { r.splits[r.nSplits++] = (uint16_t)(sec - r.lastSplitSec); r.lastSplitSec = sec; }
}

}  // namespace runlog
