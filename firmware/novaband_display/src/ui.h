// Nova-Band — on-device interface (320 x 170, landscape, touch + 2 buttons).
//
//   boot     Blender splash (rack focus onto the band) + animated wordmark,
//            then a cross-fade into the pages with a staggered card intro.
//   pages    LIVE  heart rate, 3D heart beating on every pulse, PPG wave
//            RUN   time, pace, distance, cadence (tap / long-press to run)
//            READY readiness ring, HRV / sleep / load
//            LINK  3D band turntable, pairing state, QR to the web app
//
// Depth: three layers move at different speeds when you swipe — the gym
// bokeh far behind (slow), the glass cards (1:1) and large out-of-focus
// specks in front (fast) — so the screen reads as a lens with shallow depth
// of field. Page motion is a damped spring driven by the finger.
#pragma once
#include "assets.h"
#include "gfx.h"
#include "model.h"

enum class Link { None, Advertising, Ble, Usb };

class Ui {
 public:
  static constexpr int PAGES = 4;
  void begin(const Assets* a, Model* m);
  void update(float dt);
  void render(gfx::Canvas& c);

  // input (screen coordinates)
  void touch(bool down, int x, int y);
  void buttonNext(bool longPress);
  void buttonPrev(bool longPress);

  // from the link layer
  void setLink(Link l, const char* detail = "");
  void toast(const char* text, uint16_t accent = 0);
  void setDeviceName(const char* n);
  void goPage(int p);
  void skipBoot() { bootT_ = 99; }
  void setBackground(const uint16_t* halfRes) { bgPx_ = halfRes; }   // bg copy in fast RAM

  bool booting() const { return bootT_ < BOOT_END; }
  float time() const { return t_; }
  int page() const { return target_; }

 private:
  static constexpr float BOOT_END = 3.7f;      // splash 2.4 s + hold + cross-fade
  const Assets* A_ = nullptr;
  const uint16_t* bgPx_ = nullptr;
  Model* M_ = nullptr;
  gfx::Font fLabel_, fSmall_, fBody_, fTitle_, fBrand_, fBig_;

  float t_ = 0, bootT_ = 0;
  // paging spring
  float pageF_ = 0, pageV_ = 0;
  int target_ = 0;
  bool dragging_ = false, down_ = false;
  float downX_ = 0, downY_ = 0, downPage_ = 0, downT_ = 0, lastX_ = 0, lastT_ = 0, velX_ = 0;
  // smoothed values shown on screen
  float hrShown_ = 0, readyShown_ = 0, loadShown_ = 0;
  uint32_t lastBeats_ = 0;
  float beatT_ = 10;          // seconds since the last heartbeat
  float introT_ = -1;         // card intro after boot
  float pageEnterT_[PAGES] = {0};
  // link + toast
  Link link_ = Link::None;
  char linkDetail_[40] = "";
  char devName_[24] = "NovaBand";
  char toast_[64] = "";
  uint16_t toastAccent_ = 0;
  float toastT_ = 99;
  float alertT_ = 0;

  void drawBoot(gfx::Canvas& c, float tb, uint8_t alpha);
  void drawWorld(gfx::Canvas& c);
  void drawPage(gfx::Canvas& c, int i, int ox);
  void pageLive(gfx::Canvas& c, int ox);
  void pageRun(gfx::Canvas& c, int ox);
  void pageReady(gfx::Canvas& c, int ox);
  void pageLink(gfx::Canvas& c, int ox);
  void drawStatus(gfx::Canvas& c);
  void drawToast(gfx::Canvas& c);
  void glass(gfx::Canvas& c, float x, float y, float w, float h, int idx);
  float intro(int idx) const;       // 0..1 staggered card entrance
};
