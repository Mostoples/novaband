// hot loops: build this file for speed, not size
#pragma GCC optimize("O2")
#include "gfx.h"

#include <math.h>
#include <string.h>

namespace gfx {

static inline float clampf(float v, float lo, float hi) { return v < lo ? lo : (v > hi ? hi : v); }
static inline int imin(int a, int b) { return a < b ? a : b; }
static inline int imax(int a, int b) { return a > b ? a : b; }

float fastAtan2(float y, float x) {
  float ax = fabsf(x), ay = fabsf(y);
  float mx = ax > ay ? ax : ay, mn = ax > ay ? ay : ax;
  if (mx < 1e-9f) return 0.f;
  float a = mn / mx, s = a * a;
  float r = ((-0.0464964749f * s + 0.15931422f) * s - 0.327622764f) * s * a + a;
  if (ay > ax) r = 1.57079637f - r;
  if (x < 0) r = 3.14159274f - r;
  if (y < 0) r = -r;
  return r;
}

void Canvas::clip(int x0, int y0, int x1, int y1) {
  cx0 = imax(0, x0); cy0 = imax(by0, y0); cx1 = imin(W, x1); cy1 = imin(by1, y1);
}

void Canvas::fill(uint16_t c) {
  uint32_t cc = c | ((uint32_t)c << 16);
  uint32_t* p = (uint32_t*)(fb + by0 * W);
  for (int i = 0; i < (by1 - by0) * W / 2; i++) p[i] = cc;
}

void Canvas::rect(int x, int y, int w, int h, uint16_t c, uint8_t a) {
  int x0 = imax(x, cx0), y0 = imax(y, cy0), x1 = imin(x + w, cx1), y1 = imin(y + h, cy1);
  for (int yy = y0; yy < y1; yy++) {
    uint16_t* p = fb + yy * W;
    if (a >= 252)
      for (int xx = x0; xx < x1; xx++) p[xx] = c;
    else
      for (int xx = x0; xx < x1; xx++) p[xx] = blend(p[xx], c, a);
  }
}

void Canvas::vgradient(int x, int y, int w, int h, uint16_t top, uint16_t bot, uint8_t a0, uint8_t a1) {
  if (h <= 0) return;
  for (int j = 0; j < h; j++) {
    int yy = y + j;
    if (yy < cy0 || yy >= cy1) continue;
    uint32_t t = (uint32_t)(j * 256 / h);
    uint16_t c = blend(top, bot, t);
    uint32_t a = a0 + (((int)a1 - a0) * (int)t >> 8);
    uint16_t* p = fb + yy * W;
    for (int xx = imax(x, cx0); xx < imin(x + w, cx1); xx++) p[xx] = blend(p[xx], c, a);
  }
}

// signed distance from pixel centre to a rounded rect (negative inside)
static inline float rrSD(float px, float py, float mx, float my, float hw, float hh, float r) {
  float qx = fabsf(px - mx) - (hw - r), qy = fabsf(py - my) - (hh - r);
  float ox = qx > 0 ? qx : 0, oy = qy > 0 ? qy : 0;
  float outside = (ox > 0 && oy > 0) ? sqrtf(ox * ox + oy * oy) : (ox + oy);
  float inside = qx > qy ? qx : qy;
  if (inside > 0) inside = 0;
  return outside + inside - r;
}

void Canvas::rrect(float x, float y, float w, float h, float r, uint16_t c, uint8_t a) {
  if (w <= 0 || h <= 0 || a == 0) return;
  float hw = w * .5f, hh = h * .5f, mx = x + hw, my = y + hh;
  if (r > hw) r = hw;
  if (r > hh) r = hh;
  int y0 = imax((int)floorf(y), cy0), y1 = imin((int)ceilf(y + h), cy1);
  int x0 = imax((int)floorf(x), cx0), x1 = imin((int)ceilf(x + w), cx1);
  int cl = (int)ceilf(x + r), cr = (int)floorf(x + w - r);      // columns outside the corner boxes
  for (int yy = y0; yy < y1; yy++) {
    float py = yy + .5f;
    uint16_t* p = fb + yy * W;
    float vc = clampf(fminf(py - y + .5f, y + h - py + .5f), 0, 1);  // top / bottom edge coverage
    bool corner = fabsf(py - my) > hh - r - .5f;
    if (!corner) {
      float fl = clampf((x0 + 1.f) - x, 0, 1), fr = clampf((x + w) - (x1 - 1.f), 0, 1);
      if (x0 < x1) p[x0] = blend(p[x0], c, (uint32_t)(a * fl));
      for (int xx = x0 + 1; xx < x1 - 1; xx++) p[xx] = blend(p[xx], c, a);
      if (x1 - 1 > x0) p[x1 - 1] = blend(p[x1 - 1], c, (uint32_t)(a * fr));
      continue;
    }
    uint32_t am = (uint32_t)(a * vc);
    for (int xx = x0; xx < x1; xx++) {
      if (xx >= cl && xx < cr) {                                 // straight top/bottom run
        int e = imin(cr, x1);
        for (; xx < e; xx++) p[xx] = blend(p[xx], c, am);
        xx--;
        continue;
      }
      float cov = clampf(.5f - rrSD(xx + .5f, py, mx, my, hw, hh, r), 0, 1);
      if (cov > 0) p[xx] = blend(p[xx], c, (uint32_t)(a * cov));
    }
  }
}

void Canvas::rrectStroke(float x, float y, float w, float h, float r, uint16_t c, uint8_t at, uint8_t ab) {
  float hw = w * .5f, hh = h * .5f, mx = x + hw, my = y + hh;
  int y0 = imax((int)floorf(y), cy0), y1 = imin((int)ceilf(y + h), cy1);
  int xa = (int)floorf(x), xb = (int)ceilf(x + w);
  int cl = (int)ceilf(x + r) + 1, cr = (int)floorf(x + w - r) - 1;
  auto put = [&](int xx, int yy, float py, float al) {
    if (xx < cx0 || xx >= cx1) return;
    float sd = rrSD(xx + .5f, py, mx, my, hw, hh, r);
    float cov = clampf(1.f - fabsf(sd + .5f), 0, 1);
    if (cov > 0) fb[yy * W + xx] = blend(fb[yy * W + xx], c, (uint32_t)(al * cov));
  };
  for (int yy = y0; yy < y1; yy++) {
    float py = yy + .5f;
    float al = at + (ab - at) * ((py - y) / h);
    bool corner = fabsf(py - my) > hh - r - 1.5f;
    if (!corner) {                                   // straight sides: 2 px each
      put(xa, yy, py, al); put(xa + 1, yy, py, al);
      put(xb - 2, yy, py, al); put(xb - 1, yy, py, al);
      continue;
    }
    for (int xx = xa; xx < imin(cl, xb); xx++) put(xx, yy, py, al);
    for (int xx = imax(cr, xa); xx < xb; xx++) put(xx, yy, py, al);
    float sd = fabsf(py - my) - hh;                  // straight top / bottom run
    float cov = clampf(1.f - fabsf(sd + .5f), 0, 1);
    if (cov > 0) {
      uint32_t am = (uint32_t)(al * cov);
      uint16_t* p = fb + yy * W;
      for (int xx = imax(cl, cx0); xx < imin(cr, cx1); xx++) p[xx] = blend(p[xx], c, am);
    }
  }
}

void Canvas::circle(float cx, float cy, float r, uint16_t c, uint8_t a) {
  int y0 = imax((int)(cy - r - 1), cy0), y1 = imin((int)(cy + r + 2), cy1);
  int x0 = imax((int)(cx - r - 1), cx0), x1 = imin((int)(cx + r + 2), cx1);
  for (int yy = y0; yy < y1; yy++) {
    float dy = yy + .5f - cy;
    uint16_t* p = fb + yy * W;
    float in2 = (r - .5f) * (r - .5f), out2 = (r + .5f) * (r + .5f);
    for (int xx = x0; xx < x1; xx++) {
      float dx = xx + .5f - cx, d2 = dx * dx + dy * dy;
      if (d2 >= out2) continue;
      if (r > .5f && d2 <= in2) { p[xx] = blend(p[xx], c, a); continue; }   // no sqrt inside
      float cov = clampf(r + .5f - sqrtf(d2), 0, 1);
      if (cov > 0) p[xx] = blend(p[xx], c, (uint32_t)(a * cov));
    }
  }
}

// soft additive disc: (1 - d^2/r^2)^2 falloff from a 64-entry table
static uint8_t GLOW_LUT[65];
static bool glowInit = false;
void Canvas::glow(float cx, float cy, float r, uint16_t c, uint8_t a) {
  if (!glowInit) {
    for (int i = 0; i <= 64; i++) { float t = 1.f - i / 64.f; GLOW_LUT[i] = (uint8_t)(255 * t * t); }
    glowInit = true;
  }
  if (r < 1 || a == 0) return;
  int icx = (int)lroundf(cx), icy = (int)lroundf(cy), ir = (int)ceilf(r);
  int y0 = imax(icy - ir, cy0), y1 = imin(icy + ir + 1, cy1);
  int x0 = imax(icx - ir, cx0), x1 = imin(icx + ir + 1, cx1);
  int r2 = (int)(r * r);
  if (r2 < 1) r2 = 1;
  uint32_t inv = (64u << 16) / (uint32_t)r2;               // d^2 -> table index (16.16)
  for (int yy = y0; yy < y1; yy++) {
    int dy = yy - icy, dy2 = dy * dy;
    if (dy2 >= r2) continue;
    uint16_t* p = fb + yy * W;
    for (int xx = x0; xx < x1; xx++) {
      int dx = xx - icx, d2 = dx * dx + dy2;
      if (d2 >= r2) continue;
      uint32_t w = GLOW_LUT[((uint32_t)d2 * inv) >> 16];
      p[xx] = add(p[xx], c, (w * a) >> 8);
    }
  }
}

// Arc between radii r0..r1 from angle a0 to a1 (radians, clockwise from 12
// o'clock). The angular test uses the two end rays as half-planes (cross
// products, no atan2): a sweep <= 180 deg is their intersection, a longer one
// their union. Square roots only in the 1 px radial anti-aliasing bands.
void Canvas::ring(float cx, float cy, float r0, float r1, float a0, float a1, uint16_t c, uint8_t a, bool caps) {
  const float TAU = 6.2831853f, PI = 3.14159265f;
  float sweep = a1 - a0;
  if (sweep < 0.001f) return;
  bool full = sweep >= TAU - 1e-3f;
  float u0x = sinf(a0), u0y = -cosf(a0), u1x = sinf(a1), u1y = -cosf(a1);
  bool wide = sweep > PI;
  int y0 = imax((int)(cy - r1 - 1), cy0), y1 = imin((int)(cy + r1 + 2), cy1);
  int x0 = imax((int)(cx - r1 - 1), cx0), x1 = imin((int)(cx + r1 + 2), cx1);
  float lo2 = (r0 - .5f) * (r0 - .5f), hi2 = (r1 + .5f) * (r1 + .5f);
  float in0 = (r0 + .5f) * (r0 + .5f), in1 = (r1 - .5f) * (r1 - .5f);
  for (int yy = y0; yy < y1; yy++) {
    float dy = yy + .5f - cy;
    uint16_t* p = fb + yy * W;
    for (int xx = x0; xx < x1; xx++) {
      float dx = xx + .5f - cx, d2 = dx * dx + dy * dy;
      if (d2 <= lo2 || d2 >= hi2) continue;
      float cov = 1.f;
      if (d2 < in0 || d2 > in1) {
        float d = sqrtf(d2);
        cov = clampf(fminf(d - r0 + .5f, r1 - d + .5f), 0, 1);
      }
      if (!full) {
        float s0 = u0x * dy - u0y * dx;           // > 0: clockwise of the start ray
        float s1 = dx * u1y - dy * u1x;           // > 0: counter-clockwise of the end ray
        float ang = wide ? fmaxf(s0, s1) : fminf(s0, s1);
        float ac = clampf(ang + .5f, 0, 1);
        if (ac <= 0) continue;
        cov *= ac;
      }
      if (cov > 0) p[xx] = blend(p[xx], c, (uint32_t)(a * cov));
    }
  }
  if (caps && !full) {
    float rm = (r0 + r1) * .5f, rc = (r1 - r0) * .5f;
    circle(cx + u0x * rm, cy + u0y * rm, rc - .5f, c, a);
    circle(cx + u1x * rm, cy + u1y * rm, rc - .5f, c, a);
  }
}

void Canvas::line(float x0, float y0, float x1, float y1, float w, uint16_t c, uint8_t a) {
  float hw = w * .5f;
  int bx0 = imax((int)(fminf(x0, x1) - hw - 1), cx0), bx1 = imin((int)(fmaxf(x0, x1) + hw + 2), cx1);
  int by0 = imax((int)(fminf(y0, y1) - hw - 1), cy0), by1 = imin((int)(fmaxf(y0, y1) + hw + 2), cy1);
  float vx = x1 - x0, vy = y1 - y0, L2 = vx * vx + vy * vy;
  for (int yy = by0; yy < by1; yy++) {
    uint16_t* p = fb + yy * W;
    for (int xx = bx0; xx < bx1; xx++) {
      float px = xx + .5f - x0, py = yy + .5f - y0;
      float t = L2 > 0 ? clampf((px * vx + py * vy) / L2, 0, 1) : 0;
      float ex = px - vx * t, ey = py - vy * t;
      float cov = clampf(hw + .5f - sqrtf(ex * ex + ey * ey), 0, 1);
      if (cov > 0) p[xx] = blend(p[xx], c, (uint32_t)(a * cov));
    }
  }
}

void Canvas::image(const Image& im, int sx, int sy, int dx, int dy, int w, int h) {
  for (int j = 0; j < h; j++) {
    int yy = dy + j, syy = sy + j;
    if (yy < cy0 || yy >= cy1 || syy < 0 || syy >= im.h) continue;
    int xa = imax(dx, cx0), xb = imin(dx + w, cx1);
    int s0 = sx + (xa - dx);
    if (s0 < 0) { xa -= s0; s0 = 0; }
    if (s0 + (xb - xa) > im.w) xb = xa + (im.w - s0);
    if (xb > xa) memcpy(fb + yy * W + xa, im.px + syy * im.w + s0, (xb - xa) * 2);
  }
}

void Canvas::imageFade(const Image& im, int dx, int dy, uint8_t a) {
  for (int j = 0; j < im.h; j++) {
    int yy = dy + j;
    if (yy < cy0 || yy >= cy1) continue;
    const uint16_t* s = im.px + j * im.w;
    uint16_t* p = fb + yy * W;
    for (int i = 0; i < im.w; i++) {
      int xx = dx + i;
      if (xx >= cx0 && xx < cx1) p[xx] = blend(p[xx], s[i], a);
    }
  }
}

void Canvas::sprite(const Sprite& s, int dx, int dy, uint8_t a) {
  for (int j = 0; j < s.h; j++) {
    int yy = dy + j;
    if (yy < cy0 || yy >= cy1) continue;
    const uint16_t* sc = s.px + j * s.w;
    const uint8_t* sa = s.a + j * s.w;
    uint16_t* p = fb + yy * W;
    for (int i = 0; i < s.w; i++) {
      int xx = dx + i;
      uint32_t al = sa[i];
      if (!al || xx < cx0 || xx >= cx1) continue;
      p[xx] = blend(p[xx], sc[i], (al * a) >> 8);
    }
  }
}

// bilinear resample around (cx, cy): colour channels and alpha both filtered
void Canvas::spriteScaled(const Sprite& s, float cx, float cy, float k, uint8_t a) {
  float dw = s.w * k, dh = s.h * k;
  int x0 = imax((int)(cx - dw * .5f), cx0), x1 = imin((int)(cx + dw * .5f + 1), cx1);
  int y0 = imax((int)(cy - dh * .5f), cy0), y1 = imin((int)(cy + dh * .5f + 1), cy1);
  float inv = 1.f / k;
  for (int yy = y0; yy < y1; yy++) {
    float v = (yy + .5f - (cy - dh * .5f)) * inv - .5f;
    int vi = (int)floorf(v);
    float fv = v - vi;
    if (vi < -1 || vi >= s.h) continue;
    uint16_t* p = fb + yy * W;
    for (int xx = x0; xx < x1; xx++) {
      float u = (xx + .5f - (cx - dw * .5f)) * inv - .5f;
      int ui = (int)floorf(u);
      float fu = u - ui;
      if (ui < -1 || ui >= s.w) continue;
      float acc = 0, r = 0, g = 0, b = 0;
      for (int q = 0; q < 4; q++) {
        int su = ui + (q & 1), sv = vi + (q >> 1);
        if (su < 0 || sv < 0 || su >= s.w || sv >= s.h) continue;
        float wgt = ((q & 1) ? fu : 1 - fu) * ((q >> 1) ? fv : 1 - fv);
        float al = s.a[sv * s.w + su] * wgt;
        uint16_t c = s.px[sv * s.w + su];
        acc += al;
        r += ((c >> 11) & 31) * al; g += ((c >> 5) & 63) * al; b += (c & 31) * al;
      }
      if (acc < 1.f) continue;
      uint16_t c = (uint16_t)(((int)(r / acc) << 11) | ((int)(g / acc) << 5) | (int)(b / acc));
      p[xx] = blend(p[xx], c, (uint32_t)(acc * a / 255.f));
    }
  }
}

void Canvas::darken(int x, int y, int w, int h, uint16_t k) {
  int x0 = imax(x, cx0), y0 = imax(y, cy0), x1 = imin(x + w, cx1), y1 = imin(y + h, cy1);
  for (int yy = y0; yy < y1; yy++)
    for (int xx = x0; xx < x1; xx++) fb[yy * W + xx] = scale(fb[yy * W + xx], k);
}

// Half-resolution image -> whole frame, bilinear 2x. Output pixel X samples the
// source at X/2 - 1/4, so every output is a fixed 3:1 mix per axis
// (weights 9,3,3,1 / 16). Pixels are "spread" (G moved to the high half-word)
// so the weighted sums run in one 32-bit add chain with room to spare.
static inline uint32_t spread(uint16_t p) { return (p | ((uint32_t)p << 16)) & 0x07E0F81F; }
void Canvas::upscale2x(const uint16_t* src, int sw, int sh, int sx) {
  uint32_t v[W / 2 + 4];
  int k0 = (sx >> 1) - 1;                                  // first source column needed
  const int n = W / 2 + 3;
  for (int Y = cy0; Y < cy1; Y++) {
    int sy = Y >> 1, ra = sy, rb = (Y & 1) ? sy + 1 : sy - 1;
    if (rb < 0) rb = 0;
    if (rb >= sh) rb = sh - 1;
    if (ra >= sh) ra = sh - 1;
    const uint16_t* A = src + ra * sw;                     // weight 3
    const uint16_t* B = src + rb * sw;                     // weight 1
    for (int i = 0; i < n; i++) {
      int k = k0 + i;
      if (k < 0) k = 0;
      if (k >= sw) k = sw - 1;
      uint32_t a3 = spread(A[k]);
      v[i] = (a3 << 1) + a3 + spread(B[k]);                // vertical 3:1, weight sum 4
    }
    uint16_t* o = fb + Y * W;
    int X = 0, k = ((sx) >> 1) - k0;                       // k: nearer source column of X = 0
    if (sx & 1) {                                          // odd start: one right-hand sample first
      uint32_t s = ((v[k] << 1) + v[k] + v[k + 1]) >> 4 & 0x07E0F81F;
      o[X++] = (uint16_t)(s | (s >> 16));
      k++;
    }
    for (; X + 1 < W; X += 2, k++) {                       // even (left mix) + odd (right mix)
      uint32_t c3 = (v[k] << 1) + v[k];
      uint32_t e = (v[k - 1] + c3) >> 4 & 0x07E0F81F;
      uint32_t d = (c3 + v[k + 1]) >> 4 & 0x07E0F81F;
      o[X] = (uint16_t)(e | (e >> 16));
      o[X + 1] = (uint16_t)(d | (d >> 16));
    }
    if (X < W) {
      uint32_t e = (v[k - 1] + (v[k] << 1) + v[k]) >> 4 & 0x07E0F81F;
      o[X] = (uint16_t)(e | (e >> 16));
    }
  }
}

// dst * 3/8 + ink, two pixels per 32-bit word
static inline uint32_t shade2(uint32_t p) {
  return ((p >> 2) & 0x39E739E7u) + ((p >> 3) & 0x18E318E3u) + 0x08410841u;
}
static inline uint16_t shade1(uint16_t p) { return (uint16_t)shade2(p); }

void Canvas::glassShade(float x, float y, float w, float h, float r) {
  float hw = w * .5f, hh = h * .5f, mx = x + hw, my = y + hh;
  int y0 = imax((int)floorf(y), cy0), y1 = imin((int)ceilf(y + h), cy1);
  int x0 = imax((int)floorf(x), cx0), x1 = imin((int)ceilf(x + w), cx1);
  int cl = (int)ceilf(x + r), cr = (int)floorf(x + w - r);
  for (int yy = y0; yy < y1; yy++) {
    float py = yy + .5f;
    uint16_t* p = fb + yy * W;
    bool corner = fabsf(py - my) > hh - r - .5f;
    int a = x0, b = x1;
    if (corner) {                                          // AA only in the corner boxes
      for (int xx = x0; xx < imin(cl, x1); xx++) {
        float cov = clampf(.5f - rrSD(xx + .5f, py, mx, my, hw, hh, r), 0, 1);
        if (cov > 0) p[xx] = blend(p[xx], shade1(p[xx]), (uint32_t)(255 * cov));
      }
      for (int xx = imax(cr, x0); xx < x1; xx++) {
        float cov = clampf(.5f - rrSD(xx + .5f, py, mx, my, hw, hh, r), 0, 1);
        if (cov > 0) p[xx] = blend(p[xx], shade1(p[xx]), (uint32_t)(255 * cov));
      }
      a = imax(cl, x0); b = imin(cr, x1);
      float vc = clampf(fminf(py - y + .5f, y + h - py + .5f), 0, 1);
      if (vc < .99f) {
        for (int xx = a; xx < b; xx++) p[xx] = blend(p[xx], shade1(p[xx]), (uint32_t)(255 * vc));
        continue;
      }
    }
    if (a < b && (a & 1)) { p[a] = shade1(p[a]); a++; }
    if (a < b && (b & 1)) { b--; p[b] = shade1(p[b]); }
    uint32_t* q = (uint32_t*)(p + a);
    for (int i = 0, n = (b - a) >> 1; i < n; i++) q[i] = shade2(q[i]);
  }
}

// A waveform drawn column by column: each column fills the vertical span the
// curve crosses there, with soft ends; no per-pixel square roots. Optional
// fill under the curve fading out toward floorY.
void Canvas::wave(const float* ys, int n, int x0, float hw, uint16_t c, uint8_t a, int floorY, uint8_t fillA) {
  for (int i = 0; i < n; i++) {
    int xx = x0 + i;
    if (xx < cx0 || xx >= cx1) continue;
    float yc = ys[i], yp = i ? ys[i - 1] : yc, yn = i + 1 < n ? ys[i + 1] : yc;
    float lo = fminf(yc, fminf((yp + yc) * .5f, (yn + yc) * .5f)) - hw;
    float hi = fmaxf(yc, fmaxf((yp + yc) * .5f, (yn + yc) * .5f)) + hw;
    if (fillA && floorY > (int)hi) {
      int ya = imax((int)hi, cy0), yb = imin(floorY, cy1);
      uint32_t span = (uint32_t)(floorY - (int)hi);
      for (int yy = ya; yy < yb; yy++) {
        uint32_t al = (uint32_t)fillA * (uint32_t)(floorY - yy) / span;
        fb[yy * W + xx] = blend(fb[yy * W + xx], c, al);
      }
    }
    int ya = imax((int)floorf(lo), cy0), yb = imin((int)ceilf(hi), cy1);
    for (int yy = ya; yy < yb; yy++) {
      float py = yy + .5f;
      float cov = clampf(fminf(py - lo + .5f, hi - py + .5f), 0, 1);
      if (cov > 0) fb[yy * W + xx] = blend(fb[yy * W + xx], c, (uint32_t)(a * cov));
    }
  }
}

void Canvas::shadeTop(int h, uint16_t k0) {
  for (int yy = cy0; yy < h && yy < cy1; yy++) {
    uint32_t k = 256 - (uint32_t)(256 - k0) * (h - yy) / h;
    uint16_t* p = fb + yy * W;
    for (int xx = 0; xx < W; xx++) p[xx] = scale(p[xx], k);
  }
}

int Canvas::textWidth(const Font& f, const char* s, int track) {
  int w = 0;
  for (; *s; s++) {
    int i = (uint8_t)*s - f.first;
    if (i < 0 || i >= f.count) continue;
    w += f.glyphs[i].adv + track;
  }
  return w - (w ? track : 0);
}

// y is the baseline
int Canvas::text(const Font& f, const char* s, int x, int y, uint16_t c, uint8_t a, int track) {
  int x0 = x;
  for (; *s; s++) {
    int i = (uint8_t)*s - f.first;
    if (i < 0 || i >= f.count) continue;
    const Glyph& g = f.glyphs[i];
    const uint8_t* al = f.alpha + g.off;
    int gx = x + g.xo, gy = y + g.yo;
    for (int j = 0; j < g.h; j++) {
      int yy = gy + j;
      if (yy < cy0 || yy >= cy1) continue;
      uint16_t* p = fb + yy * W;
      for (int k = 0; k < g.w; k++) {
        int xx = gx + k;
        uint32_t v = al[j * g.w + k];
        if (!v || xx < cx0 || xx >= cx1) continue;
        p[xx] = blend(p[xx], c, (v * a) >> 8);
      }
    }
    x += g.adv + track;
  }
  return x - x0;
}

}  // namespace gfx
