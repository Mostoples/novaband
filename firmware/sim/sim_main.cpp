// Nova-Band UI simulator: runs the exact firmware UI code on the PC and
// writes frames, so the screen can be reviewed (and reused in the deck and
// showreel) without the board.
//
//   build: firmware/sim/build.bat          run: sim.exe <assets.bin> <outdir> [fps]
//
// Plays a scripted session: boot splash -> app says hello -> swipe to RUN,
// tap to start -> READINESS -> LINK (BLE connects, coach message) -> flick
// back to LIVE -> heart-rate alert.
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <chrono>
#include <vector>

#include "../novaband_display/src/assets.h"
#include "../novaband_display/src/gfx.h"
#include "../novaband_display/src/model.h"
#include "../novaband_display/src/protocol.h"
#include "../novaband_display/src/ui.h"

static float g_up = 0;
static float uptime() { return g_up; }

static void writePPM(const char* path, const uint16_t* fb) {
  FILE* f = fopen(path, "wb");
  fprintf(f, "P6\n%d %d\n255\n", gfx::W, gfx::H);
  std::vector<uint8_t> row(gfx::W * 3);
  for (int y = 0; y < gfx::H; y++) {
    for (int x = 0; x < gfx::W; x++) {
      uint16_t c = fb[y * gfx::W + x];
      row[x * 3] = ((c >> 11) & 31) * 255 / 31;
      row[x * 3 + 1] = ((c >> 5) & 63) * 255 / 63;
      row[x * 3 + 2] = (c & 31) * 255 / 31;
    }
    fwrite(row.data(), 1, row.size(), f);
  }
  fclose(f);
}

struct Drag { float t0, dur; int x0, x1, y; };

int main(int argc, char** argv) {
  if (argc < 3) { fprintf(stderr, "usage: sim assets.bin outdir [fps]\n"); return 1; }
  FILE* f = fopen(argv[1], "rb");
  if (!f) { fprintf(stderr, "no assets\n"); return 1; }
  fseek(f, 0, SEEK_END);
  long n = ftell(f);
  fseek(f, 0, SEEK_SET);
  std::vector<uint8_t> blob(n);
  fread(blob.data(), 1, n, f);
  fclose(f);
  const char* out = argv[2];
  int fps = argc > 3 ? atoi(argv[3]) : 30;

  Assets assets;
  if (!assets.load(blob.data())) { fprintf(stderr, "asset image does not match asset_ids.h\n"); return 1; }
  Model model;
  model.m.battery = 86;
  Ui ui;
  ui.begin(&assets, &model);
  ui.setDeviceName("NovaBand-EB60");
  ui.setLink(Link::Advertising, "");
  std::vector<uint16_t> fb(gfx::W * gfx::H);
  gfx::Canvas c;
  c.fb = fb.data();
  proto::Env env{&model, &ui, "NovaBand-EB60", nullptr, uptime};
  char reply[256];

  // ---- scenario mode: sim.exe assets.bin outdir fps <live|run|ready|alert|walk> [frames]
  // A steady screen for one use case (used as the pod's screen in the use-case film).
  if (argc > 4) {
    const char* sc = argv[4];
    int n = argc > 5 ? atoi(argv[5]) : 220;
    const float dt = 1.f / fps;
    ui.skipBoot();
    const char* hello = "{\"cmd\":\"hello\",\"name\":\"Raka\",\"age\":17,\"alert\":182,\"t\":1790575200,\"tz\":420}";
    proto::handle(hello, strlen(hello), env, reply, sizeof reply);
    ui.setLink(Link::Ble, "Chrome - Pixel 8");
    bool running = !strcmp(sc, "live") || !strcmp(sc, "run") || !strcmp(sc, "alert");
    if (running) {
      model.start();
      for (int k = 0; k < 6000; k++) model.update(.1f, k * .1f);   // ~10 minutes into the run
    }
    int page = !strcmp(sc, "run") ? 1 : !strcmp(sc, "ready") ? 2 : 0;
    ui.goPage(page);
    float t0 = 600;
    for (int k = 0; k < 90; k++) { g_up = t0 + k * dt; model.update(dt, g_up); ui.update(dt); }   // settle, let toasts pass
    if (!strcmp(sc, "ready")) ui.goPage(0), ui.goPage(2);      // re-enter so the ring sweeps in on screen
    for (int i = 0; i < n; i++) {
      float t = t0 + (90 + i) * dt;
      g_up = t;
      if (!strcmp(sc, "alert")) model.setRealHr(166 + 22 * fminf(i / 70.f, 1.f), t);  // HR climbs past the 182 limit
      model.update(dt, t);
      ui.update(dt);
      ui.render(c);
      char path[512];
      snprintf(path, sizeof path, "%s/f_%04d.ppm", out, i + 1);
      writePPM(path, fb.data());
    }
    printf("scenario %s: %d frames\n", sc, n);
    return 0;
  }

  const Drag drags[] = {{6.0f, .28f, 262, 70, 90}, {10.2f, .30f, 250, 60, 90}, {13.4f, .25f, 255, 80, 90},
                        {19.0f, .12f, 70, 250, 90}, {19.6f, .12f, 70, 250, 90}, {20.2f, .12f, 70, 250, 90}};
  const float dt = 1.f / fps;
  int frames = (int)(25.f * fps);
  double renderMs = 0;
  int mismatches = 0;
  bool did[16] = {false};
  for (int i = 0; i < frames; i++) {
    float t = i * dt;
    g_up = t;
    auto once = [&](int k, float at) { if (!did[k] && t >= at) { did[k] = true; return true; } return false; };
    if (once(0, 4.2f)) {
      const char* hello = "{\"cmd\":\"hello\",\"name\":\"Dela\",\"age\":17,\"alert\":176,\"t\":1790575200,\"tz\":420}";
      proto::handle(hello, strlen(hello), env, reply, sizeof reply);
      ui.setLink(Link::Ble, "Chrome - Pixel 8");
    }
    if (once(1, 7.2f)) {                       // tap on RUN, then fast-forward 11 min of running
      ui.touch(true, 160, 90); ui.touch(false, 160, 90);
      for (int k = 0; k < 7000; k++) model.update(.1f, t + k * .1f);
    }
    if (once(2, 15.0f)) {
      const char* m = "{\"cmd\":\"msg\",\"text\":\"Coach: hold 5:30/km\",\"level\":\"info\"}";
      proto::handle(m, strlen(m), env, reply, sizeof reply);
    }
    if (once(3, 21.5f)) model.m.hr = 181;     // push past the alert limit (176)
    // finger drags
    for (auto& d : drags) {
      if (t >= d.t0 && t <= d.t0 + d.dur + dt) {
        float u = fminf((t - d.t0) / d.dur, 1.f);
        int x = (int)(d.x0 + (d.x1 - d.x0) * u);
        ui.touch(u < 1.f, x, d.y);
      }
    }
    model.update(dt, t);
    ui.update(dt);
    auto a = std::chrono::high_resolution_clock::now();
    // same two-band split as the board (top / bottom 85 rows), then compared
    // with a whole-frame render: any clipping bug shows up as a mismatch
    static std::vector<uint16_t> b0(gfx::W * gfx::H / 2), b1(gfx::W * gfx::H / 2);
    gfx::Canvas top, bot;
    top.band(b0.data(), 0, gfx::H / 2);
    bot.band(b1.data(), gfx::H / 2, gfx::H);
    ui.render(top);
    ui.render(bot);
    auto b = std::chrono::high_resolution_clock::now();
    ui.render(c);
    if (memcmp(b0.data(), fb.data(), b0.size() * 2) || memcmp(b1.data(), fb.data() + b0.size(), b1.size() * 2))
      mismatches++;
    renderMs += std::chrono::duration<double, std::milli>(b - a).count();
    char path[512];
    snprintf(path, sizeof path, "%s/f_%04d.ppm", out, i);
    writePPM(path, fb.data());
  }
  proto::telemetry(model, reply, sizeof reply);
  printf("frames %d, avg render %.2f ms (PC), band mismatches %d\n%s\n", frames, renderMs / frames, mismatches, reply);
  return 0;
}
