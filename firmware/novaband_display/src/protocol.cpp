#include "protocol.h"

#include <ArduinoJson.h>
#include <stdio.h>
#include <string.h>

#include "gfx.h"

namespace proto {

int telemetry(const Model& md, char* out, size_t n) {
  const Metrics& m = md.m;
  return snprintf(out, n,
                  "{\"t\":\"m\",\"hr\":%d,\"sp\":%d,\"cad\":%d,\"pace\":%d,\"dist\":%.2f,\"sec\":%d,"
                  "\"kcal\":%d,\"load\":%d,\"rdy\":%d,\"z\":%d,\"bat\":%d,\"usb\":%d,\"run\":%d,\"pz\":%d,"
                  "\"stp\":%lu,\"demo\":%d}",
                  (int)(m.hr + .5f), (int)(m.spo2 + .5f), (int)(m.cadence + .5f), (int)m.pace, m.dist,
                  (int)m.elapsed, (int)m.kcal, (int)m.load, m.readiness, m.zone, m.battery, m.usbPower,
                  m.running, m.paused, (unsigned long)m.steps, md.demo ? 1 : 0);
}

static void setTime(Model& m, JsonVariantConst doc, float up) {
  if (!doc["t"].is<long long>() && !doc["t"].is<double>()) return;
  double t = doc["t"].as<double>();
  if (t > 1e11) t /= 1000.0;                       // accept milliseconds too
  int tz = doc["tz"] | 0;                          // minutes east of UTC (WIB = 420)
  m.epochOffset = (int64_t)t + tz * 60 - (int64_t)up;
  m.timeValid = true;
}

int handle(const char* json, size_t len, const Env& env, char* reply, size_t n) {
  JsonDocument doc;
  if (deserializeJson(doc, json, len)) return snprintf(reply, n, "{\"t\":\"err\",\"e\":\"json\"}");
  const char* cmd = doc["cmd"] | "";
  Model& m = *env.model;
  Ui& ui = *env.ui;
  float up = env.uptime ? env.uptime() : 0;

  if (!strcmp(cmd, "hello")) {
    Profile& p = m.profile;
    if (doc["name"].is<const char*>()) snprintf(p.name, sizeof p.name, "%s", doc["name"].as<const char*>());
    p.age = doc["age"] | p.age;
    p.hrMax = doc["hrmax"] | (220 - p.age);
    p.hrRest = doc["rest"] | p.hrRest;
    p.weight = doc["weight"] | p.weight;
    p.alertHr = doc["alert"] | p.alertHr;
    setTime(m, doc.as<JsonVariantConst>(), up);
    char t[48];
    snprintf(t, sizeof t, "Hi %s - synced", p.name);
    ui.toast(t, gfx::hex(0x3BE07A));
    return snprintf(reply, n, "{\"t\":\"info\",\"name\":\"%s\",\"fw\":\"1.0.0\",\"w\":320,\"h\":170}", env.deviceName);
  }
  if (!strcmp(cmd, "ping")) return snprintf(reply, n, "{\"t\":\"pong\"}");
  if (!strcmp(cmd, "time")) setTime(m, doc.as<JsonVariantConst>(), up);
  else if (!strcmp(cmd, "run")) {
    const char* a = doc["a"] | "";
    if (!strcmp(a, "start")) { if (!m.m.running) m.start(); else if (m.m.paused) m.pause(); ui.toast("Run started from app", gfx::hex(0xFF4D5E)); }
    else if (!strcmp(a, "pause")) { if (m.m.running && !m.m.paused) m.pause(); ui.toast("Paused", gfx::hex(0xFFB347)); }
    else if (!strcmp(a, "stop")) { m.stop(); ui.toast("Run saved", gfx::hex(0x3BE07A)); }
    ui.goPage(1);
  } else if (!strcmp(cmd, "msg")) {
    const char* lv = doc["level"] | "info";
    uint16_t c = !strcmp(lv, "warn") ? gfx::hex(0xFFB347) : !strcmp(lv, "good") ? gfx::hex(0x3BE07A) : gfx::hex(0x5AB4FF);
    ui.toast(doc["text"] | "", c);
  } else if (!strcmp(cmd, "page")) ui.goPage(doc["i"] | 0);
  else if (!strcmp(cmd, "bright")) { if (env.setBrightness) env.setBrightness(doc["v"] | 200); }
  else if (!strcmp(cmd, "alert")) m.profile.alertHr = doc["hr"] | m.profile.alertHr;
  else if (!strcmp(cmd, "hr")) m.setRealHr(doc["v"] | m.m.hr, up);
  else if (!strcmp(cmd, "ready")) m.m.readiness = doc["v"] | m.m.readiness;
  else return snprintf(reply, n, "{\"t\":\"err\",\"e\":\"cmd\"}");
  return snprintf(reply, n, "{\"t\":\"ack\",\"cmd\":\"%s\"}", cmd);
}

}  // namespace proto
