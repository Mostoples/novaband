// Nova-Band <-> web app protocol. The same JSON lines travel over
//   * Bluetooth LE: written to the CMD characteristic, telemetry notified on TELEM
//   * USB (Web Serial): one JSON object per line, 115200 baud
// so the app has a single parser whichever way it is connected.
//
// app -> band   {"cmd":"hello","name":"Dela","age":17,"hrmax":203,"rest":60,"weight":52,"alert":190,"t":1790000000,"tz":420}
//               {"cmd":"time","t":<unix s>,"tz":<minutes east of UTC>}
//               {"cmd":"run","a":"start"|"pause"|"stop"}
//               {"cmd":"msg","text":"Coach: ease off","level":"info"|"warn"|"good"}
//               {"cmd":"page","i":0..3}   {"cmd":"bright","v":0..255}
//               {"cmd":"alert","hr":185}  {"cmd":"hr","v":151}   {"cmd":"ready","v":78}
//               {"cmd":"ping"}  (USB keep-alive, every 3 s)
// band -> app   {"t":"m","hr":142,"sp":98,"cad":166,"pace":332,"dist":2.41,"sec":812,"kcal":210,
//                "load":47,"rdy":82,"z":3,"bat":87,"usb":1,"run":1,"pz":0,"stp":4213,"demo":1}   (1 Hz)
//               {"t":"info","name":"NovaBand-EB60","fw":"1.0.0","w":320,"h":170}              (on hello)
//               {"t":"ack","cmd":"run"}
#pragma once
#include <stddef.h>

#include "model.h"
#include "ui.h"

namespace proto {

struct Env {
  Model* model;
  Ui* ui;
  const char* deviceName;
  void (*setBrightness)(int v);          // may be null (simulator)
  float (*uptime)();                     // seconds
};

// Handles one command line; writes a reply into `reply` (may be empty). Returns reply length.
int handle(const char* json, size_t len, const Env& env, char* reply, size_t n);
int telemetry(const Model& m, char* out, size_t n);

}  // namespace proto
