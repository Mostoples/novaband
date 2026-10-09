// Uji algoritma langkah giroskop dengan sinyal simulasi lengan atas (g++ -O2 -I../novaband_display pedo_test.cpp)
#include <cstdio>
#include <cstdlib>
#include <random>
#include <vector>
#include "pedo_gyro.h"

static std::mt19937 rng(42);
static float gauss(float sd) { return std::normal_distribution<float>(0, sd)(rng); }

struct Result { uint32_t steps; int expect; };

// jalan/lari: ayun sinusoidal f (siklus/dtk), amplitudo puncak wp (deg/s), asimetri maju/mundur, derau, bias dibuang
static Result gait(const char* name, float f, float wp, float asym, float noise, float secs, float jitter = 0.f) {
  GyroPedo p; double t = 0; uint32_t ms = 0;
  int N = (int)(secs * 100);
  double ph = 0;
  for (int i = 0; i < N; i++) {
    ms = (uint32_t)(i * 10);
    double ff = f * (1 + jitter * (gauss(1.f) * .3f));
    ph += 2 * M_PI * ff * .01;
    double c = cos(ph);
    double amp = c > 0 ? 1.0 : asym;                  // ayun mundur lebih lemah
    float wx = (float)(wp * c * amp) + gauss(noise);
    float wy = (float)(wp * .25 * sin(2 * ph)) + gauss(noise);   // gerak siku / harmonik kedua
    float wz = (float)(wp * .15 * cos(ph + 1)) + gauss(noise);
    p.sample(sqrtf(wx * wx + wy * wy + wz * wz), ms);
    t += .01;
  }
  int expect = (int)(2 * f * secs);                   // 2 langkah per siklus ayun
  printf("%-34s hitung=%4u  harapan~%4d  selisih=%+5.1f%%  puncak=%u\n", name, p.steps, expect,
         100.0 * ((double)p.steps - expect) / (expect ? expect : 1), p.peaks);
  return {p.steps, expect};
}

// gerakan lengan acak (lambai/ketik/garuk): semburan 0,3-0,8 dtk tak beraturan
static uint32_t randomMotion(const char* name, float secs, float wp, float gapMin, float gapMax) {
  GyroPedo p; int N = (int)(secs * 100); int i = 0;
  std::uniform_real_distribution<float> U(0, 1);
  while (i < N) {
    int gap = (int)((gapMin + U(rng) * (gapMax - gapMin)) * 100);
    for (int k = 0; k < gap && i < N; k++, i++) p.sample(fabsf(gauss(.6f)) + 1.f, i * 10);
    int len = (int)((.3f + U(rng) * .5f) * 100); float a = wp * (.4f + U(rng) * .6f);
    for (int k = 0; k < len && i < N; k++, i++) p.sample(a * fabsf(sinf(3.14159f * k / len)) + fabsf(gauss(.6f)), i * 10);
  }
  printf("%-34s hitung=%4u  harapan   0\n", name, p.steps);
  return p.steps;
}

// glitch: lonjakan 1500 deg/s selama 0,3 dtk di detik ke-1, lalu jalan 110 spm 30 dtk; harapan ~55 langkah (+-tahan awal)
static void glitchThenWalk() {
  GyroPedo p; double ph = 0; uint32_t firstStep = 0;
  for (int i = 0; i < 3000; i++) {
    uint32_t ms = i * 10; float w;
    if (i >= 100 && i < 130) w = 1500.f;
    else { ph += 2 * M_PI * .92 * .01; w = fabsf(60.f * cosf(ph)) + fabsf(gauss(.5f)); }
    uint32_t before = p.steps; p.sample(w, ms);
    if (!firstStep && p.steps > before) firstStep = ms;
  }
  printf("%-34s hitung=%4u  harapan~%4d  langkah pertama di %.1f dtk setelah glitch\n", "glitch 1500dps lalu jalan", p.steps, (int)(2 * .92 * 28.7), (firstStep - 1300) / 1000.0);
}

int main() {
  printf("== langkah beraturan (lengan atas) ==\n");
  gait("diam (derau saja)", 0, 0, 1, 0.5f, 60);
  gait("jalan santai 100 spm", 0.83f, 45, 1.0f, .5f, 60);
  gait("jalan 110 spm, mundur lemah 0.5", 0.92f, 60, .5f, .5f, 60);
  gait("jalan cepat 125 spm", 1.04f, 80, .7f, .5f, 60);
  gait("jogging 150 spm", 1.25f, 180, .6f, .6f, 60);
  gait("lari 170 spm", 1.42f, 280, .5f, .8f, 60);
  gait("lari cepat 190 spm", 1.58f, 350, .6f, .8f, 60);
  gait("lari 170 spm, mundur lemah 0.35", 1.42f, 280, .35f, .8f, 60);
  gait("lari 170 spm, irama goyang", 1.42f, 280, .6f, .8f, 60, 0.35f);
  gait("jalan 103 langkah (~110 spm)", 0.92f, 60, .6f, .5f, 56);
  glitchThenWalk();
  printf("== gerakan lengan acak (harus ~0) ==\n");
  randomMotion("lambai/ketik jarang", 120, 150, .8f, 2.5f);
  randomMotion("gerak lengan sering", 120, 220, .3f, 1.0f);
  randomMotion("kerja di meja", 300, 80, .2f, 1.5f);
  return 0;
}
