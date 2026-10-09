#pragma GCC optimize("O2")
#include "ui.h"

#include <math.h>
#include <stdio.h>
#include <string.h>

using namespace gfx;

namespace {
const uint16_t WHITE = hex(0xFFFFFF), CREAM = hex(0xF3E3D3), ROSE = hex(0xC9A3A3),
               WINE = hex(0x7B2021), WINE_HI = hex(0xE04A57), PULSE = hex(0xFF6B7A),
               INK = hex(0x160A0E), GREEN = hex(0x3BE07A), BLUE = hex(0x5AB4FF),
               AMBER = hex(0xFFB347), RED = hex(0xFF4D5E), BLACK = 0;
const uint16_t ZONE_C[6] = {0, hex(0x8FA3B8), hex(0x3BA7FF), hex(0x3BE07A), hex(0xFFB347), hex(0xFF4D5E)};
const char* ZONE_N[6] = {"", "RECOVERY", "ENDURANCE", "AEROBIC", "THRESHOLD", "MAXIMUM"};
const char* PAGE_N[4] = {"LIVE", "RUN", "READINESS", "LINK"};

inline float clamp01(float v) { return v < 0 ? 0 : (v > 1 ? 1 : v); }
inline float easeOut(float t) { t = clamp01(t); return 1 - (1 - t) * (1 - t) * (1 - t); }
inline float easeInOut(float t) { t = clamp01(t); return t * t * (3 - 2 * t); }
inline float easeBack(float t) {
  t = clamp01(t);
  const float c1 = 1.5f, c3 = c1 + 1;
  return 1 + c3 * powf(t - 1, 3) + c1 * powf(t - 1, 2);
}
inline uint8_t A8(float v) { return (uint8_t)(clamp01(v) * 255.f); }

// deterministic bokeh specks: far (behind the cards) and near (in front of them)
struct Speck { float x, y, r, v, a; uint16_t c; };
Speck far_[18], near_[6];

void seedSpecks() {
  uint32_t s = 12345;
  auto rnd = [&s]() { s = s * 1664525u + 1013904223u; return (s >> 8) / 16777216.f; };
  const uint16_t pal[4] = {ROSE, CREAM, WINE_HI, hex(0xFFD1C4)};
  for (auto& p : far_) p = {rnd() * 460, rnd() * 170, 1.5f + rnd() * 3.5f, 2 + rnd() * 5, .25f + rnd() * .35f, pal[(int)(rnd() * 4) & 3]};
  for (auto& p : near_) p = {rnd() * 640, rnd() * 170, 12 + rnd() * 14, 5 + rnd() * 6, .10f + rnd() * .08f, pal[(int)(rnd() * 4) & 3]};
}
}  // namespace

void Ui::begin(const Assets* a, Model* m) {
  A_ = a; M_ = m;
  fLabel_ = a->font(A::F_LABEL); fSmall_ = a->font(A::F_SMALL); fBody_ = a->font(A::F_BODY);
  fTitle_ = a->font(A::F_TITLE); fBrand_ = a->font(A::F_BRAND); fBig_ = a->font(A::F_BIG);
  seedSpecks();
  hrShown_ = m->m.hr;
}

void Ui::setLink(Link l, const char* detail) {
  if (l != link_) {
    if (l == Link::Ble) toast("App connected - Bluetooth", GREEN);
    else if (l == Link::Usb) toast("App connected - USB", GREEN);
    else if (link_ == Link::Ble || link_ == Link::Usb) toast("App disconnected", AMBER);
  }
  link_ = l;
  snprintf(linkDetail_, sizeof linkDetail_, "%s", detail ? detail : "");
}
void Ui::setDeviceName(const char* n) { snprintf(devName_, sizeof devName_, "%s", n); }
void Ui::toast(const char* text, uint16_t accent) {
  snprintf(toast_, sizeof toast_, "%s", text);
  toastAccent_ = accent ? accent : WINE_HI;
  toastT_ = 0;
}
void Ui::goPage(int p) {
  if (p < 0) p = 0;
  if (p >= PAGES) p = PAGES - 1;
  if (p != target_) pageEnterT_[p] = t_;
  if (p == 2 && target_ != 2) readyShown_ = 0;   // the ring sweeps in every visit
  target_ = p;
}

// ------------------------------------------------------------------ input
void Ui::touch(bool down, int x, int y) {
  if (booting()) return;
  if (down && !down_) {
    down_ = true; dragging_ = false;
    downX_ = lastX_ = (float)x; downY_ = (float)y; downPage_ = dragTarget_ = pageF_; downT_ = lastT_ = t_; velX_ = 0;
  } else if (down && down_) {
    float dx = x - downX_;
    if (!dragging_ && fabsf(dx) > 5) dragging_ = true;
    if (dragging_) {
      float p = downPage_ - dx / (float)W;
      if (p < 0) p *= .35f;                                  // rubber band at the ends
      if (p > PAGES - 1) p = (PAGES - 1) + (p - (PAGES - 1)) * .35f;
      dragTarget_ = p; pageV_ = 0;
      float dtt = t_ - lastT_;
      if (dtt > 0.001f) velX_ = .6f * velX_ + .4f * ((x - lastX_) / dtt);
      lastX_ = (float)x; lastT_ = t_;
    }
  } else if (!down && down_) {
    down_ = false;
    if (dragging_) {
      dragging_ = false;
      float proj = pageF_ - velX_ / W * .30f;               // a flick carries to the next page
      int p = (int)lroundf(proj);
      int from = (int)lroundf(downPage_);                   // at most one page per swipe
      if (p > from + 1) p = from + 1;
      if (p < from - 1) p = from - 1;
      goPage(p);
      pageV_ = fmaxf(-5.f, fminf(5.f, -velX_ / W));
    } else if (t_ - downT_ < .4f && target_ == 1) {
      buttonNext(true);                                     // tap on RUN = start / pause
    }
  }
}

void Ui::buttonNext(bool longPress) {
  if (booting()) { skipBoot(); return; }
  if (!longPress) { goPage((target_ + 1) % PAGES); return; }
  Metrics& m = M_->m;
  if (!m.running) { M_->start(); toast("Run started", RED); }
  else { M_->pause(); toast(m.paused ? "Paused" : "Resumed", m.paused ? AMBER : GREEN); }
}
void Ui::buttonPrev(bool longPress) {
  if (booting()) { skipBoot(); return; }
  if (!longPress) { goPage((target_ + PAGES - 1) % PAGES); return; }
  if (M_->m.running) { M_->stop(); toast("Run saved", GREEN); }
}

// ------------------------------------------------------------------ update
void Ui::update(float dt) {
  t_ += dt;
  bootT_ += dt;
  if (bootT_ >= BOOT_END - .5f && introT_ < 0) introT_ = 0;
  if (introT_ >= 0) introT_ += dt;
  if (M_->beats != lastBeats_) { lastBeats_ = M_->beats; beatT_ = 0; } else beatT_ += dt;
  hrShown_ += (M_->m.hr - hrShown_) * (1 - expf(-dt * 5));
  readyShown_ += (M_->m.readiness - readyShown_) * (1 - expf(-dt * 3.2f));
  loadShown_ += (M_->m.load - loadShown_) * (1 - expf(-dt * 3));
  toastT_ += dt;

  if (dragging_) pageF_ += (dragTarget_ - pageF_) * (1 - expf(-dt * 28));   // ~35 ms lag hides the panel's report jitter
  if (!dragging_) {                    // damped spring toward the target page, in sub-steps
    const float k = 260.f, c = 2 * sqrtf(k) * .92f;
    float h = dt / 4;
    for (int i = 0; i < 4; i++) {
      float acc = -k * (pageF_ - target_) - c * pageV_;
      pageV_ += acc * h;
      pageF_ += pageV_ * h;
    }
  }
  bool high = M_->m.hr > M_->profile.alertHr;
  if (high && alertT_ == 0) toast("Heart rate above your limit", RED);
  alertT_ = high ? alertT_ + dt : 0;
}

float Ui::intro(int idx) const {
  if (introT_ < 0) return 0;
  return easeOut((introT_ - idx * .07f) / .5f);
}

// ------------------------------------------------------------------ render
void Ui::render(Canvas& c) {
  c.noclip();                                               // (resets to the canvas band)
  if (bootT_ < BOOT_END - .5f) { drawBoot(c, bootT_, 255); return; }
  drawWorld(c);
  for (int i = 0; i < PAGES; i++) {
    int ox = (int)lroundf((i - pageF_) * W);
    if (ox > -W && ox < W) drawPage(c, i, ox);
  }
  // near specks: large, soft, fast — the out-of-focus foreground
  for (auto& p : near_) {
    float x = fmodf(p.x - pageF_ * 420 + t_ * p.v + 6400, 640) - 160;
    float y = p.y + sinf(t_ * .3f + p.x) * 6;
    c.glow(x, y, p.r, p.c, A8(p.a));
  }
  if (alertT_ > 0) {                                        // pulsing red edge
    float k = .55f + .45f * sinf(alertT_ * 6.f);
    c.vgradient(0, 0, W, 22, RED, RED, A8(.55f * k), 0);
    c.vgradient(0, H - 22, W, 22, RED, RED, 0, A8(.55f * k));
  }
  drawStatus(c);
  drawToast(c);
  if (bootT_ < BOOT_END) drawBoot(c, BOOT_END - .5f, A8(1 - easeInOut((bootT_ - (BOOT_END - .5f)) / .5f)));
}

void Ui::drawBoot(Canvas& c, float tb, uint8_t alpha) {
  int n = A_->frames(A::SPLASH);
  int f = (int)(tb * 25);
  if (f >= n) f = n - 1;
  Image im = A_->image(A::SPLASH, f);
  if (alpha >= 255) c.image(im, 0, 0, 0, 0, W, H);
  else c.imageFade(im, 0, 0, alpha);
  float ga = alpha / 255.f;
  // wordmark: letters rise in one by one while the tracking closes up
  const char* word = "NOVA-BAND";
  float tr = 5 * (1 - easeOut((tb - .95f) / 1.1f)) + 1;
  int x = 16;
  for (int i = 0; word[i]; i++) {
    char s[2] = {word[i], 0};
    float e = easeBack((tb - (.95f + i * .06f)) / .45f);
    float a = clamp01((tb - (.95f + i * .06f)) / .3f) * ga;
    c.text(fBrand_, s, x, 92 + (int)((1 - e) * 12), word[i] == '-' ? WINE_HI : WHITE, A8(a));
    x += Canvas::textWidth(fBrand_, s) + (int)tr;
  }
  float la = easeOut((tb - 1.7f) / .5f);
  c.rect(17, 101, (int)(118 * la), 2, WINE_HI, A8(.9f * ga));
  c.text(fSmall_, "AIoT upper-arm wearable", 17, 119, ROSE, A8(clamp01((tb - 1.55f) / .5f) * ga));
  c.text(fLabel_, "ISIF 2026  |  SMAN 1 SURAKARTA", 17, 158, CREAM, A8(clamp01((tb - 2.1f) / .5f) * .75f * ga), 1);
}

void Ui::drawWorld(Canvas& c) {
  Image bg = A_->image(A::BG);                              // half resolution, 240 x 85
  const int span = bg.w * 2 - W;                             // parallax travel, full-res px
  float sx = pageF_ * span / (PAGES - 1);
  if (sx < 0) sx = 0;
  if (sx > span) sx = (float)span;
  c.upscale2x(bgPx_ ? bgPx_ : bg.px, bg.w, bg.h, (int)sx);
  for (auto& p : far_) {                                    // far specks drift up slowly
    float x = fmodf(p.x - pageF_ * 30 + 4600, 460) - 70;
    float y = fmodf(p.y - t_ * p.v + 1700, 190) - 10;
    c.glow(x, y, p.r * 2.2f, p.c, A8(p.a * (.7f + .3f * sinf(t_ * 1.3f + p.x))));
  }
}

void Ui::glass(Canvas& c, float x, float y, float w, float h, int idx) {
  float e = intro(idx);
  y += (1 - e) * 18;
  if (e > .995f) c.glassShade(x, y, w, h, 11);             // settled: the fast integer path
  else c.rrect(x, y, w, h, 11, INK, A8(.62f * e));         // during the intro: fades in
  c.rrectStroke(x, y, w, h, 11, WHITE, A8(.30f * e), A8(.05f * e));
}

void Ui::drawPage(Canvas& c, int i, int ox) {
  switch (i) {
    case 0: pageLive(c, ox); break;
    case 1: pageRun(c, ox); break;
    case 2: pageReady(c, ox); break;
    default: pageLink(c, ox); break;
  }
}

// ------------------------------------------------------------------ LIVE
void Ui::pageLive(Canvas& c, int ox) {
  const Metrics& m = M_->m;
  char buf[32];
  float e0 = intro(0), e1 = intro(1);
  int dy0 = (int)((1 - e0) * 18), dy1 = (int)((1 - e1) * 18);
  glass(c, 8 + ox, 24, 150, 134, 0);
  glass(c, 164 + ox, 24, 148, 134, 1);

  c.text(fLabel_, "HEART RATE", 19 + ox, 40 + dy0, ROSE, A8(e0), 1);
  if (M_->demo) c.text(fLabel_, "DEMO", 26 + ox, 120 + dy0, AMBER, A8(.75f * e0), 1);
  if (M_->real && !M_->hrOk) c.text(fLabel_, "NO SIGNAL", 19 + ox, 58 + dy0, AMBER, A8(.85f * e0), 1);
  if (M_->real && M_->tempOk) {
    snprintf(buf, sizeof buf, "%.1f C", m.temp);
    c.text(fLabel_, buf, 150 + ox - Canvas::textWidth(fLabel_, buf), 58 + dy0, CREAM, A8(.8f * e0));
  }
  float pulse = expf(-beatT_ * 9.f);
  c.glow(44 + ox, 84 + dy0, 30 + 8 * pulse, WINE_HI, A8((.22f + .35f * pulse) * e0));
  int hf = (int)(pulse * (A_->frames(A::HEART) - .01f));   // pre-scaled beat frames
  Sprite heart = A_->sprite(A::HEART, hf);
  c.sprite(heart, 44 + ox - heart.w / 2, 84 + dy0 - heart.h / 2, A8(e0));
  if (M_->real && !M_->hrOk) snprintf(buf, sizeof buf, "--"); else snprintf(buf, sizeof buf, "%d", (int)lroundf(hrShown_));
  c.text(fBig_, buf, 74 + ox, 103 + dy0, WHITE, A8(e0), -2);
  c.text(fLabel_, "BPM", 77 + ox, 117 + dy0, ROSE, A8(e0), 1);
  if (M_->real && !M_->spo2Ok) snprintf(buf, sizeof buf, "SpO2 --"); else snprintf(buf, sizeof buf, "SpO2 %d%%", (int)lroundf(m.spo2));
  c.text(fLabel_, buf, 150 + ox - Canvas::textWidth(fLabel_, buf), 40 + dy0, CREAM, A8(.8f * e0));
  // zone chip, filled to %HRmax inside the zone scale 50..100 %
  int z = m.zone;
  float pct = clamp01((hrShown_ / M_->profile.hrMax - .5f) / .5f);
  c.rrect(16 + ox, 128 + dy0, 134, 20, 10, ZONE_C[z], A8(.22f * e0));
  c.rrect(16 + ox, 128 + dy0, 20 + 114 * pct, 20, 10, ZONE_C[z], A8(.55f * e0));
  if (M_->real && !M_->hrOk) snprintf(buf, sizeof buf, "Z-  --"); else snprintf(buf, sizeof buf, "Z%d  %s", z, ZONE_N[z]);
  int tw = Canvas::textWidth(fLabel_, buf, 1);
  c.text(fLabel_, buf, 16 + ox + (134 - tw) / 2, 142 + dy0, WHITE, A8(e0), 1);

  // PPG wave
  c.text(fLabel_, "PPG  LIVE", 175 + ox, 40 + dy1, ROSE, A8(e1), 1);
  c.circle(292 + ox, 36 + dy1, 3, GREEN, A8((.55f + .45f * pulse) * e1));
  const int x0 = 172 + ox, wy = 50 + dy1, ww = 132, wh = 56, N = Model::PPG_N;
  float lo = 1e9f, hi = -1e9f;
  for (int k = N - ww; k < N; k++) {
    float v = M_->ppg[(M_->ppgHead + k) % N];
    lo = fminf(lo, v); hi = fmaxf(hi, v);
  }
  float span = fmaxf(hi - lo, .2f);
  for (int g = 1; g < 4; g++) c.rect(x0, wy + g * wh / 4, ww, 1, WHITE, A8(.06f * e1));
  float ys[160];
  for (int k = 0; k < ww; k++) {
    float v = M_->ppg[(M_->ppgHead + N - ww + k) % N];
    ys[k] = wy + wh - 4 - (v - lo) / span * (wh - 8);
  }
  c.wave(ys, ww, x0, 2.4f, PULSE, A8(.16f * e1), wy + wh, A8(.20f * e1));   // glow + fill
  c.wave(ys, ww, x0, .95f, PULSE, A8(e1), 0, 0);                            // the trace
  float px = (float)(x0 + ww - 1), py = ys[ww - 1];
  c.glow(px, py, 9, PULSE, A8(.8f * e1));
  c.circle(px, py, 2.2f, WHITE, A8(e1));
  // cadence + steps
  c.sprite(A_->sprite(A::IC_FOOTSTEPS), 173 + ox, 116 + dy1, A8(e1));
  if (M_->real && !M_->cadOk) snprintf(buf, sizeof buf, "--"); else snprintf(buf, sizeof buf, "%d", (int)lroundf(m.cadence));
  int w = c.text(fBody_, buf, 199 + ox, 134 + dy1, WHITE, A8(e1));
  c.text(fLabel_, "spm", 202 + ox + w, 134 + dy1, ROSE, A8(e1));
  snprintf(buf, sizeof buf, "%lu", (unsigned long)m.steps);
  tw = Canvas::textWidth(fBody_, buf);
  c.text(fBody_, buf, 303 + ox - tw, 134 + dy1, WHITE, A8(e1));
  c.text(fLabel_, "STEPS", 303 + ox - Canvas::textWidth(fLabel_, "STEPS", 1), 148 + dy1, ROSE, A8(.8f * e1), 1);
  c.text(fLabel_, "CADENCE", 175 + ox, 148 + dy1, ROSE, A8(.8f * e1), 1);
}

// ------------------------------------------------------------------ RUN
void Ui::pageRun(Canvas& c, int ox) {
  const Metrics& m = M_->m;
  char v[16];
  struct Tile { const char* label; int icon; const char* unit; };
  const Tile tiles[4] = {{"TIME", A::IC_STOPWATCH, ""}, {"PACE", A::IC_GAUGE, "/km"},
                         {"DISTANCE", A::IC_MAP_PIN, "km"}, {"ENERGY", A::IC_FLAME, "kcal"}};
  for (int i = 0; i < 4; i++) {
    int x = (i & 1 ? 164 : 8) + ox, y = i < 2 ? 24 : 92;
    int w = i & 1 ? 148 : 150;
    glass(c, (float)x, (float)y, (float)w, 62, i);
    int s = (int)m.elapsed;
    switch (i) {
      case 0: snprintf(v, sizeof v, "%02d:%02d", s / 60, s % 60); break;
      case 1:
        if (m.pace > 60 && m.running && !m.paused) snprintf(v, sizeof v, "%d:%02d", (int)m.pace / 60, (int)m.pace % 60);
        else snprintf(v, sizeof v, "-:--");
        break;
      case 2:
        snprintf(v, sizeof v, "%.2f", m.dist);
        break;
      default: snprintf(v, sizeof v, "%d", (int)m.kcal); break;
    }
    c.sprite(A_->sprite(tiles[i].icon), x + 10, y + 9);
    c.text(fLabel_, tiles[i].label, x + 38, y + 24, ROSE, 255, 1);
    int tw = c.text(fTitle_, v, x + 12, y + 53, WHITE);
    if (*tiles[i].unit) c.text(fSmall_, tiles[i].unit, x + 16 + tw, y + 53, ROSE);
  }
  // centre pill: what a tap will do
  const char* hint = !m.running ? "TAP TO START" : (m.paused ? "PAUSED - TAP" : nullptr);
  if (hint) {
    float p = .75f + .25f * sinf(t_ * 3.2f);
    int tw = Canvas::textWidth(fLabel_, hint, 1);
    int bx = 160 + ox - (tw + 24) / 2;
    c.rrect((float)bx, 78, (float)tw + 24, 20, 10, m.paused ? AMBER : WINE_HI, A8(.92f));
    c.text(fLabel_, hint, bx + 12, 92, WHITE, A8(p), 1);
  }
}

// ------------------------------------------------------------------ READINESS
void Ui::pageReady(Canvas& c, int ox) {
  const Metrics& m = M_->m;
  char buf[24];
  glass(c, 8 + ox, 24, 150, 134, 0);
  glass(c, 164 + ox, 24, 148, 134, 1);
  c.text(fLabel_, "READINESS", 19 + ox, 40, ROSE, 255, 1);
  float cx = 83 + ox, cy = 96, r0 = 36, r1 = 46;
  const float A0 = -2.356f, SWEEP = 4.712f;                  // 270 deg gauge, gap at the bottom
  float v = clamp01(readyShown_ / 100.f);
  uint16_t col = readyShown_ >= 75 ? GREEN : readyShown_ >= 50 ? AMBER : RED;
  c.ring(cx, cy, r0, r1, A0, A0 + SWEEP, WHITE, 26, true);
  c.ring(cx, cy, r0, r1, A0, A0 + SWEEP * v, col, 255, true);
  float ea = A0 + SWEEP * v;
  c.glow(cx + sinf(ea) * 41, cy - cosf(ea) * 41, 12, col, 120);
  if (M_->real) snprintf(buf, sizeof buf, "--"); else snprintf(buf, sizeof buf, "%d", (int)lroundf(readyShown_));
  int tw = Canvas::textWidth(fTitle_, buf);
  c.text(fTitle_, buf, (int)cx - tw / 2, (int)cy + 8, WHITE);
  tw = Canvas::textWidth(fLabel_, "/ 100", 1);
  c.text(fLabel_, "/ 100", (int)cx - tw / 2, (int)cy + 22, ROSE, 200, 1);

  const char* head = M_->real ? "No data yet" : m.readiness >= 75 ? "Go for tempo" : m.readiness >= 50 ? "Easy run today" : "Rest day";
  c.text(fBody_, head, 175 + ox, 50, WHITE);
  c.text(fSmall_, M_->real ? "Needs HRV + sleep" : m.readiness >= 75 ? "Well recovered" : "Recovery in progress", 175 + ox, 66, ROSE);
  struct Row { const char* k; char v[12]; float f; uint16_t c; } rows[3] = {
      {"HRV", "", .68f, BLUE}, {"SLEEP", "", 7.67f / 9.f, hex(0xB28DFF)}, {"LOAD", "", clamp01(loadShown_ / 150.f), AMBER}};
  if (M_->real) { snprintf(rows[0].v, 12, "--"); snprintf(rows[1].v, 12, "--"); rows[0].f = rows[1].f = 0; }
  else { snprintf(rows[0].v, 12, "68 ms"); snprintf(rows[1].v, 12, "7h 40m"); }
  snprintf(rows[2].v, 12, "%d", (int)lroundf(loadShown_));
  for (int i = 0; i < 3; i++) {
    int y = 88 + i * 23;
    c.text(fLabel_, rows[i].k, 175 + ox, y, ROSE, 255, 1);
    int w = Canvas::textWidth(fLabel_, rows[i].v);
    c.text(fLabel_, rows[i].v, 302 + ox - w, y, WHITE);
    float grow = easeOut((t_ - pageEnterT_[2] - i * .08f) / .6f);
    c.rrect(175 + ox, y + 5, 127, 5, 2.5f, WHITE, 30);
    c.rrect(175 + ox, y + 5, 127 * rows[i].f * grow, 5, 2.5f, rows[i].c, 230);
  }
}

// ------------------------------------------------------------------ LINK
void Ui::pageLink(Canvas& c, int ox) {
  glass(c, 8 + ox, 24, 150, 134, 0);
  glass(c, 164 + ox, 24, 148, 134, 1);
  int nf = A_->frames(A::SPIN);
  float pos = fmodf(t_ * 14.f, (float)nf);                   // 36 turntable frames = 10 deg each
  int f = (int)pos;
  float fr = pos - f;
  c.glow(83 + ox, 82, 50, WINE, 70);
  c.sprite(A_->sprite(A::SPIN, f), 31 + ox, 28);
  c.sprite(A_->sprite(A::SPIN, (f + 1) % nf), 31 + ox, 28, A8(fr));   // cross-fade to the next frame: smooth at 60 fps
  int tw = Canvas::textWidth(fBody_, devName_);
  c.text(fBody_, devName_, 83 + ox - tw / 2, 142, WHITE);
  const char* sub = linkDetail_[0] ? linkDetail_ : "Scan the QR for the app";
  tw = Canvas::textWidth(fLabel_, sub);
  c.text(fLabel_, sub, 83 + ox - tw / 2, 154, ROSE);

  const char* st;
  uint16_t sc;
  float blink = 1;
  switch (link_) {
    case Link::Ble: st = "WEB BLUETOOTH"; sc = GREEN; break;
    case Link::Usb: st = "USB  WEB SERIAL"; sc = GREEN; break;
    case Link::Advertising: st = "READY TO PAIR"; sc = BLUE; blink = .45f + .55f * (sinf(t_ * 4) * .5f + .5f); break;
    default: st = "OFFLINE"; sc = ROSE; break;
  }
  c.circle(178 + ox, 37, 3.2f, sc, A8(blink));
  c.text(fLabel_, st, 187 + ox, 41, WHITE, 255, 1);
  // QR code to the PWA, 3 px per module on a white tile
  const AssetEntry& q = A_->e(A::QR);
  const uint8_t* mod = A_->bytes(A::QR);
  int n = q.w, px = 3, box = n * px + 8;
  int bx = 164 + ox + (148 - box) / 2, by = 49;
  c.rrect((float)bx, (float)by, (float)box, (float)box, 6, WHITE, 255);
  for (int yy = 0; yy < n; yy++)
    for (int xx = 0; xx < n; xx++)
      if (mod[yy * n + xx]) c.rect(bx + 4 + xx * px, by + 4 + yy * px, px, px, INK);
}

// ------------------------------------------------------------------ chrome
void Ui::drawStatus(Canvas& c) {
  const Metrics& m = M_->m;
  char buf[24];
  c.shadeTop(24, 110);
  int ip = (int)lroundf(pageF_);
  if (ip < 0) ip = 0;
  if (ip > PAGES - 1) ip = PAGES - 1;
  float fa = 1 - 2 * fabsf(pageF_ - ip);
  c.text(fLabel_, PAGE_N[ip], 12, 15, CREAM, A8(fa), 2);
  // clock
  if (M_->timeValid) {
    long long now = M_->clockNow();
    int mins = (int)((now / 60) % 1440);
    snprintf(buf, sizeof buf, "%02d:%02d", mins / 60, mins % 60);
  } else snprintf(buf, sizeof buf, "--:--");
  int tw = Canvas::textWidth(fSmall_, buf);
  c.text(fSmall_, buf, 308 - tw, 15, WHITE);
  // battery
  int bx = 308 - tw - 30;
  c.rrectStroke((float)bx, 5, 20, 10, 2.5f, WHITE, 200, 200);
  c.rect(bx + 20, 8, 2, 4, WHITE, 200);
  float lvl = m.battery / 100.f;
  c.rrect((float)bx + 2, 7, 16 * lvl, 6, 1.5f, m.usbPower ? GREEN : (m.battery < 20 ? RED : WHITE), 230);
  // link dot
  uint16_t lc = link_ == Link::Ble || link_ == Link::Usb ? GREEN : link_ == Link::Advertising ? BLUE : ROSE;
  float la = link_ == Link::Advertising ? .4f + .6f * (sinf(t_ * 4) * .5f + .5f) : 1;
  c.circle((float)bx - 10, 10, 3, lc, A8(la));
  // body temperature, left of the link dot
  int tempX = bx - 18;
  if (M_->real && M_->tempOk) {
    snprintf(buf, sizeof buf, "%.1f C", m.temp);
    tempX = bx - 18 - Canvas::textWidth(fSmall_, buf);
    c.text(fSmall_, buf, tempX, 15, CREAM);
  }
  // run chip
  if (m.running) {
    int s = (int)m.elapsed;
    snprintf(buf, sizeof buf, m.paused ? "PAUSED" : "REC %02d:%02d", s / 60, s % 60);
    tw = Canvas::textWidth(fLabel_, buf, 1);
    int cx = 160 - (tw + 22) / 2;
    if (cx + tw + 22 > tempX - 6) cx = tempX - 6 - (tw + 22);
    c.rrect((float)cx, 3, (float)tw + 22, 15, 7.5f, m.paused ? AMBER : RED, 215);
    c.circle((float)cx + 8, 10.5f, 2.5f, WHITE, A8(m.paused ? 1 : .5f + .5f * sinf(t_ * 6)));
    c.text(fLabel_, buf, cx + 14, 14, WHITE, 255, 1);
  }
  // page dots
  int x = 160 - (PAGES * 10 + 10) / 2;
  for (int i = 0; i < PAGES; i++) {
    float d = clamp01(1 - fabsf(pageF_ - i));
    float w = 5 + 11 * d;
    c.rrect((float)x, 162, w, 5, 2.5f, d > .5f ? WHITE : ROSE, A8(.45f + .55f * d));
    x += (int)w + 5;
  }
}

void Ui::drawToast(Canvas& c) {
  const float LIFE = 3.0f;
  if (toastT_ > LIFE + .4f || !toast_[0]) return;
  float in = easeBack(toastT_ / .45f), out = easeInOut((toastT_ - LIFE) / .4f);
  float e = in * (1 - out);
  int tw = Canvas::textWidth(fSmall_, toast_);
  float w = (float)tw + 34, x = 160 - w / 2, y = -24 + e * 48;
  c.rrect(x, y, w, 22, 11, INK, A8(.92f * clamp01(e * 2)));
  c.rrectStroke(x, y, w, 22, 11, WHITE, A8(.35f * e), A8(.08f * e));
  c.circle(x + 13, y + 11, 3.5f, toastAccent_, 255);
  c.text(fSmall_, toast_, (int)x + 23, (int)y + 16, WHITE);
}
