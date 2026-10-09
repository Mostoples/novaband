// Nova-Band — penghitung langkah dari giroskop (lengan atas), tanpa dependensi Arduino supaya bisa
// diuji di komputer (firmware/tools/pedo_test.cpp).
//
// Ayunan lengan atas saat jalan/lari: satu siklus ayun = 2 langkah, dan |w| (norma 3 sumbu) punya
// DUA puncak per siklus (ayun maju dan mundur) -> 1 puncak = 1 langkah.
//   * puncak = maksimum lokal |w| yang sudah di-low-pass (~6 Hz), di atas ambang adaptif
//     (30% dari selubung puncak terakhir, minimum 6 deg/s di atas derau)
//   * jeda minimum antar puncak 200 ms (<= 300 langkah/menit), dan >= 45% dari jeda sebelumnya
//     (membuang puncak ganda dari harmonik kedua)
//   * gerbang pola jalan: 5 puncak beruntun (jarak <= 1100 ms) baru dihitung. Jeda boleh selang-seling
//     pendek/panjang (ayun maju dan mundur tak sama kuat): tiap jeda dicocokkan dengan jeda sebelumnya
//     ATAU jeda dua langkah sebelumnya (selisih < 35% / < 25%), dan 4 jeda terakhir harus berpola
//     ganjil-genap yang stabil. Puncak awal ditahan lalu dilepas bersama. Gerakan acak tidak lolos.
//   * selubung puncak meluruh (setengah dalam ~4,6 dtk) dan pengaruh lonjakan dibatasi, jadi jalan santai
//     setelah lari, atau setelah glitch sensor, tetap terdeteksi dalam hitungan detik
#pragma once
#include <math.h>
#include <stdint.h>

struct GyroPedo {
  // keluaran
  uint32_t steps = 0, peaks = 0;
  float cadence = 0;               // langkah/menit (dihaluskan)
  uint32_t cadAt = 0;              // ms terakhir cadence valid, 0 = belum/kedaluwarsa
  // keadaan
  float lp = 0, prev = 0, prev2 = 0, env = 30;
  uint32_t lastPeak = 0, lastDt = 0;
  int streak = 0, pending = 0;
  float cad = 0;
  uint32_t d[4] = {0, 0, 0, 0};    // 4 jeda terakhir (ms)
  int dn = 0;

  void sample(float w, uint32_t now) {
    lp += (w - lp) * .35f;
    uint32_t sinceLast = now - lastPeak;
    uint32_t minGap = lastDt ? (uint32_t)(lastDt * .45f) : 200;
    if (minGap < 200) minGap = 200;
    bool isPeak = prev > prev2 && prev >= lp && prev > fmaxf(6.f, env * .30f) && sinceLast > minGap;
    if (isPeak) {
      peaks++;
      uint32_t dt = sinceLast;
      bool chain = lastPeak && dt < 1100;
      bool regular = !lastDt || (dt * 100 < lastDt * 135 && dt * 135 > lastDt * 100) ||
                     (dn >= 2 && dt * 100 < d[1] * 125 && dt * 125 > d[1] * 100) ||   // cocok dengan jeda 2 langkah lalu
                     (dn < 2 && dt * 100 < lastDt * 180 && dt * 180 > lastDt * 100);   // awal pola: belum ada pembanding 2 langkah
      lastPeak = now;
      if (!chain) { streak = 1; pending = 1; lastDt = 0; dn = 0; }
      else if (!regular) { streak = 2; pending = 2; lastDt = dt; dn = 1; d[0] = dt; }
      else {
        lastDt = dt;
        streak++;
        for (int i = 3; i > 0; i--) d[i] = d[i - 1];
        d[0] = dt; if (dn < 4) dn++;
        float c = 60000.f / dt;
        cad = cad ? cad * .7f + c * .3f : c;
        bool steady = true;
        if (dn >= 4) {                                                // pola ganjil-genap stabil: d0~d2 dan d1~d3
          auto close = [](uint32_t a, uint32_t b) { uint32_t hi = a > b ? a : b, lo = a > b ? b : a; return hi * 100 <= lo * 125; };
          steady = close(d[0], d[2]) && close(d[1], d[3]);
        }
        if (streak < 5 || !steady) { if (streak < 5) pending++; else { pending++; } }
        else { steps += pending + 1; pending = 0; cadence = cad; cadAt = now; }
      }
      float pv = prev < env * 2.5f ? prev : env * 2.5f;           // lonjakan (glitch/benturan) tidak boleh mendorong selubung
      if (pv > 400.f) pv = 400.f;
      env += (pv - env) * .2f;
    }
    env *= .9985f;                                              // setengah dalam ~4,6 dtk
    prev2 = prev; prev = lp;
    if (lastPeak && now - lastPeak > 2000) { streak = pending = 0; lastDt = 0; dn = 0; cad = 0; cadAt = 0; lastPeak = 0; }
  }
};
