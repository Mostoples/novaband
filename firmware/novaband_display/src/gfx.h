// Nova-Band display — software renderer for a 320 x 170 RGB565 frame.
// Portable C++ (no Arduino headers): the same code draws on the ESP32-S3 and
// in the PC simulator (firmware/sim), so every frame can be checked as a PNG.
#pragma once
#include <stdint.h>
#include <stddef.h>

namespace gfx {

constexpr int W = 320, H = 170;

inline uint16_t rgb(uint8_t r, uint8_t g, uint8_t b) {
  return (uint16_t)(((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3));
}
inline uint16_t hex(uint32_t c) { return rgb(c >> 16, (c >> 8) & 0xFF, c & 0xFF); }

// dst = src*a + dst*(1-a), a in 0..255. Classic 565 trick: spread G into the
// high half-word so R, G, B blend in one multiply.
inline uint16_t blend(uint16_t dst, uint16_t src, uint32_t a) {
  if (a >= 252) return src;
  if (a < 4) return dst;
  uint32_t a5 = (a + 4) >> 3;
  uint32_t s = (src | ((uint32_t)src << 16)) & 0x07E0F81F;
  uint32_t d = (dst | ((uint32_t)dst << 16)) & 0x07E0F81F;
  uint32_t r = ((((s - d) * a5) >> 5) + d) & 0x07E0F81F;
  return (uint16_t)(r | (r >> 16));
}
// additive (light) blend, saturating per channel
inline uint16_t add(uint16_t dst, uint16_t src, uint32_t a) {
  uint32_t r = ((dst >> 11) & 31) + ((((src >> 11) & 31) * a) >> 8);
  uint32_t g = ((dst >> 5) & 63) + ((((src >> 5) & 63) * a) >> 8);
  uint32_t b = (dst & 31) + (((src & 31) * a) >> 8);
  if (r > 31) r = 31;
  if (g > 63) g = 63;
  if (b > 31) b = 31;
  return (uint16_t)((r << 11) | (g << 5) | b);
}
inline uint16_t scale(uint16_t c, uint32_t k) {  // k 0..256
  uint32_t r = (((c >> 11) & 31) * k) >> 8, g = (((c >> 5) & 63) * k) >> 8, b = ((c & 31) * k) >> 8;
  return (uint16_t)((r << 11) | (g << 5) | b);
}

// ---------------------------------------------------------------- fonts
struct Glyph { uint16_t w, h; int16_t xo, yo; uint16_t adv; uint32_t off; };
struct Font {
  uint16_t first, count, line, ascent;
  const Glyph* glyphs;
  const uint8_t* alpha;      // 8-bit coverage
};

// ---------------------------------------------------------------- sprites
struct Image { int w, h; const uint16_t* px; };                          // opaque RGB565
struct Sprite { int w, h; const uint16_t* px; const uint8_t* a; };        // RGB565 + A8

class Canvas {
 public:
  uint16_t* fb = nullptr;                     // row y lives at fb + y * W
  int cx0 = 0, cy0 = 0, cx1 = W, cy1 = H;     // clip rect (exclusive max)
  int by0 = 0, by1 = H;                       // the band this canvas owns

  // Draw only rows [y0, y1) into `buf` (a band-sized buffer). fb is offset so
  // that absolute y still indexes correctly; every primitive clips to the band.
  // Two bands let both ESP32-S3 cores draw one frame at the same time.
  void band(uint16_t* buf, int y0, int y1) { fb = buf - y0 * W; by0 = y0; by1 = y1; noclip(); }
  void clip(int x0, int y0, int x1, int y1);
  void noclip() { cx0 = 0; cy0 = by0; cx1 = W; cy1 = by1; }

  void fill(uint16_t c);
  void rect(int x, int y, int w, int h, uint16_t c, uint8_t a = 255);
  void vgradient(int x, int y, int w, int h, uint16_t top, uint16_t bot, uint8_t a0, uint8_t a1);
  // anti-aliased rounded rectangle; 'a' is the fill opacity
  void rrect(float x, float y, float w, float h, float r, uint16_t c, uint8_t a);
  // 1 px AA outline of a rounded rect, alpha fading from top (at) to bottom (ab)
  void rrectStroke(float x, float y, float w, float h, float r, uint16_t c, uint8_t at, uint8_t ab);
  void circle(float cx, float cy, float r, uint16_t c, uint8_t a);
  void glow(float cx, float cy, float r, uint16_t c, uint8_t a);            // soft additive disc
  void ring(float cx, float cy, float r0, float r1, float a0, float a1, uint16_t c, uint8_t a, bool caps);
  void line(float x0, float y0, float x1, float y1, float w, uint16_t c, uint8_t a);

  void image(const Image& im, int sx, int sy, int dx, int dy, int w, int h);  // copy a region
  void imageFade(const Image& im, int dx, int dy, uint8_t a);                // blend a whole image
  void sprite(const Sprite& s, int dx, int dy, uint8_t a = 255);
  void spriteScaled(const Sprite& s, float cx, float cy, float k, uint8_t a = 255);
  void darken(int x, int y, int w, int h, uint16_t k);                        // multiply by k/256
  // --- fast paths (see gfx.cpp): these carry the per-frame load on the ESP32-S3
  void upscale2x(const uint16_t* src, int sw, int sh, int sx);                // half-res image -> full frame, bilinear
  void glassShade(float x, float y, float w, float h, float r);               // rounded rect darkened to 3/8 + ink
  void wave(const float* ys, int n, int x0, float hw, uint16_t c, uint8_t a, int floorY, uint8_t fillA);
  void shadeTop(int h, uint16_t k0);                                          // darken the top h rows, fading out

  int text(const Font& f, const char* s, int x, int y, uint16_t c, uint8_t a = 255, int track = 0);
  static int textWidth(const Font& f, const char* s, int track = 0);

 private:
  inline void px(int x, int y, uint16_t c, uint32_t a) {
    if (x < cx0 || y < cy0 || x >= cx1 || y >= cy1) return;
    uint16_t* p = fb + y * W + x;
    *p = blend(*p, c, a);
  }
};

float fastAtan2(float y, float x);   // radians, ~0.005 rad error

}  // namespace gfx
