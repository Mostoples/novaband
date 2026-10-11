// Nova-Band — WiFi + Firebase Realtime Database (REST over HTTPS), shared by every ESP.
//
// Salinan identik ada di novaband_display/cloud.h dan novaband_c3_sensors/cloud.h (Arduino hanya
// membaca folder sketch). Ubah satu, salin ke yang lain.
//
// Alur: WiFi -> NTP (perlu untuk memeriksa sertifikat TLS) -> sign-in email/password
// (identitytoolkit) -> PUT /devices/{role}/live.json?auth=<idToken> tiap 2 detik.
// Token diperbarui otomatis lewat refresh token. Semua jalan di task FreeRTOS sendiri,
// jadi loop()/render tidak pernah menunggu jaringan.
//
// Data di RTDB (satu node per perangkat, kuncinya = CLOUD_ROLE = bagian depan email akun):
//   /devices/esplilygo/info   nama, peran, IP, MAC            (sekali per koneksi)
//   /devices/esplilygo/live   telemetri jam + ts + rssi + up  (tiap 2 detik)
//   /devices/esplilygo/runs/<id>  rekaman satu lari (id = waktu mulai, ms) — lihat saveRun()
//   /devices/esp32c3/info     idem
//   /devices/esp32c3/live     telemetri sensor C3
// Perangkat boleh juga MEMBACA node perangkat lain (watch()): jam membaca /devices/esp32c3/live
// supaya HR/SpO2/suhu dari MAX30102 + MLX90614 di C3 tampil di jam.
// Tiap perangkat hanya menulis dua daun miliknya (PUT .../info dan .../live), tidak pernah ke
// /devices, jadi data perangkat lain tidak pernah tertimpa.
#pragma once
#include <Arduino.h>
#include <ArduinoJson.h>
#include <HTTPClient.h>
#include <NetworkClientSecure.h>
#include <Preferences.h>
#include <WiFi.h>
#include <time.h>

#include "secrets.h"   // WIFI_SSID, WIFI_PASS, CLOUD_EMAIL, CLOUD_PASS, CLOUD_ROLE

namespace cloud {

static const char* API_KEY = "AIzaSyB6JPBKeHo4lVuRHx91yS6NdvIqxWIJuT0";   // kunci web Firebase, bukan rahasia
static const char* DB_URL = "https://novaband-id-default-rtdb.asia-southeast1.firebasedatabase.app";
static const uint32_t SEND_MS = 2000;

struct Status {
  volatile bool wifi = false, authed = false, lastOk = false;
  volatile int lastCode = 0;
  volatile uint32_t sent = 0, failed = 0;
};
inline Status status;

// Telemetri sensor perangkat lain (ESP32-C3) yang dibaca dari RTDB lewat watch(). Ditulis task cloud,
// dibaca loop(). `seenAt` = millis() saat penghitung `up` perangkat itu terakhir berubah (0 = belum
// pernah) - tidak bergantung jam, jadi data basi terdeteksi kalau perangkat itu mati/tidur.
struct Remote {
  volatile float hr = 0, spo2 = 0, temp = 0;
  volatile bool finger = false, hasMax = false, hasMlx = false;
  volatile uint32_t seenAt = 0, upSeen = 0;
};
inline Remote remote;

namespace {

extern "C" const uint8_t rootca_bundle_start[] asm("_binary_x509_crt_bundle_start");
extern "C" const uint8_t rootca_bundle_end[] asm("_binary_x509_crt_bundle_end");

constexpr int RUN_SLOTS = 3;                          // lari yang belum terkirim, disimpan di NVS (tahan mati listrik/offline)
Preferences prefs;
SemaphoreHandle_t mtx;
char pending[480];
String dbgBody;                                      // JSON string besar untuk /devices/<role>/dbg (diagnosis)
bool dbgDirty = false;
bool dirty = false;
char devName[32];
char watchRole[24] = "";                             // node perangkat lain yang dibaca ("" = tidak membaca)
String idToken, refreshToken, uid;
uint32_t tokenExpiry = 0;                            // millis() at which to refresh
NetworkClientSecure tls;

bool postJson(const char* url, const String& body, JsonDocument& out) {
  tls.stop();
  HTTPClient http;
  http.setReuse(false);
  http.setTimeout(10000);
  if (!http.begin(tls, url)) return false;
  http.addHeader("Content-Type", url[8] == 's' ? "application/x-www-form-urlencoded" : "application/json");
  int code = http.POST(body);
  bool ok = false;
  if (code == 200) {
    String payload = http.getString();
    DeserializationError err = deserializeJson(out, payload);
    ok = !err;
    if (err) Serial.printf("# cloud: auth JSON %s\n", err.c_str());
  } else {
    Serial.printf("# cloud: auth HTTP %d %s\n", code, code > 0 ? http.getString().substring(0, 120).c_str() : http.errorToString(code).c_str());
  }
  http.end();
  tls.stop();
  return ok;
}

bool signIn() {
  char url[160];
  snprintf(url, sizeof url, "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=%s", API_KEY);
  JsonDocument req, res;
  req["email"] = CLOUD_EMAIL; req["password"] = CLOUD_PASS; req["returnSecureToken"] = true;
  String body; serializeJson(req, body);
  if (!postJson(url, body, res)) return false;
  if (!res["idToken"].is<const char*>() || !res["localId"].is<const char*>()) { Serial.println("# cloud: respons login tak lengkap"); return false; }
  idToken = res["idToken"].as<String>(); refreshToken = res["refreshToken"].as<String>(); uid = res["localId"].as<String>();
  tokenExpiry = millis() + (uint32_t)(atol(res["expiresIn"] | "3600") - 300) * 1000UL;
  return true;
}

bool refresh() {
  char url[120];
  snprintf(url, sizeof url, "https://securetoken.googleapis.com/v1/token?key=%s", API_KEY);
  JsonDocument res;
  if (!postJson(url, "grant_type=refresh_token&refresh_token=" + refreshToken, res)) return false;
  if (!res["id_token"].is<const char*>()) return false;
  idToken = res["id_token"].as<String>(); refreshToken = res["refresh_token"].as<String>();
  tokenExpiry = millis() + (uint32_t)(atol(res["expires_in"] | "3600") - 300) * 1000UL;
  return true;
}

HTTPClient http;                                     // dipakai put() dan getRemote(): satu koneksi TLS tetap hidup

// PUT body at /devices/{uid}/{leaf}.json. Returns the HTTP code.
int put(const char* leaf, const String& body) {
  String url = String(DB_URL) + "/devices/" + CLOUD_ROLE + "/" + leaf + ".json?auth=" + idToken;
  http.setReuse(true);
  http.setTimeout(8000);
  if (!http.begin(tls, url)) return -1;
  http.addHeader("Content-Type", "application/json");
  int code = http.PUT(body);
  if (code != 200) { String r = http.getString(); Serial.printf("# cloud: PUT %s -> %d %s\n", leaf, code, r.substring(0, 100).c_str()); }
  http.end();
  return code;
}

// Ambil /devices/<watchRole>/live dan salin sensornya ke `remote`. Mengembalikan kode HTTP.
int getRemote() {
  String url = String(DB_URL) + "/devices/" + watchRole + "/live.json?auth=" + idToken;
  http.setReuse(true);
  http.setTimeout(8000);
  if (!http.begin(tls, url)) return -1;
  int code = http.GET();
  if (code == 200) {
    JsonDocument d;
    if (!deserializeJson(d, http.getString()) && d.is<JsonObject>()) {
      remote.hasMax = d["mx"] | 0; remote.hasMlx = d["ml"] | 0; remote.finger = d["finger"] | 0;
      remote.hr = d["hr"] | 0.f; remote.spo2 = d["sp"] | 0.f; remote.temp = d["tmp"] | 0.f;
      uint32_t up = d["up"] | 0u;
      if (up != remote.upSeen) { remote.upSeen = up; remote.seenAt = millis() ? millis() : 1; }
    }
  } else {
    Serial.printf("# cloud: GET %s -> %d\n", watchRole, code);
  }
  http.end();
  return code;
}

// Kirim rekaman lari yang masih antre. Slot dihapus hanya setelah RTDB menjawab 200.
void uploadRuns() {
  static uint32_t last = 0;
  if (millis() - last < 5000) return;                 // jangan menghantam server kalau gagal
  last = millis();
  for (int i = 0; i < RUN_SLOTS; i++) {
    char key[8]; snprintf(key, sizeof key, "r%d", i);
    String v;
    if (xSemaphoreTake(mtx, pdMS_TO_TICKS(200))) { prefs.begin("runs", true); v = prefs.getString(key, ""); prefs.end(); xSemaphoreGive(mtx); }
    int bar = v.indexOf('|');
    if (bar <= 0) continue;                           // kosong: "<id>|<json>"
    int code = put((String("runs/") + v.substring(0, bar)).c_str(), v.substring(bar + 1));
    if (code == 200) {
      if (xSemaphoreTake(mtx, pdMS_TO_TICKS(200))) { prefs.begin("runs", false); prefs.remove(key); prefs.end(); xSemaphoreGive(mtx); }
      Serial.printf("# cloud: lari %s tersimpan ke RTDB\n", v.substring(0, bar).c_str());
    } else {
      if (code == 401) idToken = "";
      return;                                         // coba lagi nanti
    }
  }
}

void task(void*) {
  uint32_t lastSend = 0, lastWifi = 0, lastDbg = 0, lastGet = 0;
  bool infoSent = false, ntp = false, wasUp = false;
  for (;;) {
    vTaskDelay(pdMS_TO_TICKS(250));
    uint32_t now = millis();
    bool up = WiFi.status() == WL_CONNECTED;
    status.wifi = up;
    if (!up) {
      if (wasUp) Serial.println("# cloud: WiFi hilang, menyambung ulang");
      wasUp = false; infoSent = false; tls.stop();
      if (now - lastWifi > 15000) { lastWifi = now; WiFi.disconnect(); WiFi.begin(WIFI_SSID, WIFI_PASS); }
      continue;
    }
    if (!wasUp) {
      wasUp = true;
      Serial.printf("# cloud: WiFi ok %s rssi %d\n", WiFi.localIP().toString().c_str(), WiFi.RSSI());
    }
    if (!ntp) {
      configTime(0, 0, "pool.ntp.org", "time.google.com");
      if (time(nullptr) < 1700000000) { vTaskDelay(pdMS_TO_TICKS(1000)); if (time(nullptr) < 1700000000) continue; }
      ntp = true;
      Serial.printf("# cloud: waktu NTP ok (%ld)\n", (long)time(nullptr));
      tls.setCACertBundle(rootca_bundle_start, rootca_bundle_end - rootca_bundle_start);
    }
    if (!idToken.length() || (int32_t)(now - tokenExpiry) >= 0) {
      bool ok = idToken.length() && refreshToken.length() ? refresh() || signIn() : signIn();
      status.authed = ok;
      if (!ok) { idToken = ""; vTaskDelay(pdMS_TO_TICKS(8000)); continue; }
      Serial.printf("# cloud: login ok uid %s\n", uid.c_str());
    }
    if (!infoSent) {
      char s[240];
      snprintf(s, sizeof s, "{\"name\":\"%s\",\"role\":\"%s\",\"ip\":\"%s\",\"mac\":\"%s\",\"boot\":{\".sv\":\"timestamp\"}}",
               devName, CLOUD_ROLE, WiFi.localIP().toString().c_str(), WiFi.macAddress().c_str());
      infoSent = put("info", s) == 200;
    }
    uploadRuns();
    if (dbgDirty && now - lastDbg >= 10000 && xSemaphoreTake(mtx, pdMS_TO_TICKS(50))) {
      String body = dbgBody; dbgDirty = false; xSemaphoreGive(mtx);
      lastDbg = now;
      if (put("dbg", body) == 401) idToken = "";
    }
    if (watchRole[0] && now - lastGet >= SEND_MS) {
      lastGet = now;
      int code = getRemote();
      if (code == 401) idToken = "";
      if (code < 0) tls.stop();
    }
    if (now - lastSend < SEND_MS) continue;
    char body[560];
    bool have = false;
    if (xSemaphoreTake(mtx, pdMS_TO_TICKS(50))) {
      size_t n = strlen(pending);
      if (dirty && n > 2 && pending[n - 1] == '}') {
        snprintf(body, sizeof body, "%.*s,\"ts\":{\".sv\":\"timestamp\"},\"rssi\":%d,\"up\":%lu}", (int)n - 1, pending, WiFi.RSSI(), now / 1000UL);
        dirty = false; have = true;
      }
      xSemaphoreGive(mtx);
    }
    if (!have) continue;
    lastSend = now;
    int code = put("live", body);
    status.lastCode = code; status.lastOk = code == 200;
    if (code == 200) status.sent = status.sent + 1; else status.failed = status.failed + 1;
    if (code == 401) idToken = "";                  // token ditolak: login ulang
    if (code < 0) tls.stop();
    if (code == 200 && status.sent == 1) Serial.println("# cloud: kirim ke RTDB ok");
  }
}

}  // namespace

// Mulai WiFi + task cloud. `name` dicatat di /info.
inline void begin(const char* name) {
  snprintf(devName, sizeof devName, "%s", name);
  mtx = xSemaphoreCreateMutex();
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.setSleep(false);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  xTaskCreatePinnedToCore(task, "cloud", 14336, nullptr, 1, nullptr, 0);
}

// Baca juga sensor perangkat lain (mis. "esp32c3") dari RTDB ke `cloud::remote`. Panggil sebelum/sesudah begin().
inline void watch(const char* role) { snprintf(watchRole, sizeof watchRole, "%s", role); }

// Titipkan telemetri terbaru (objek JSON, diakhiri '}'). Aman dipanggil dari task mana pun.
inline void publish(const char* json) {
  if (!mtx || !xSemaphoreTake(mtx, 0)) return;
  snprintf(pending, sizeof pending, "%s", json);
  dirty = true;
  xSemaphoreGive(mtx);
}

// Titipkan teks diagnosis (hanya angka , ; -) untuk dikirim sebagai /devices/<role>/dbg tiap >= 10 dtk.
inline void publishDbg(const String& text) {
  if (!mtx || !xSemaphoreTake(mtx, 0)) return;
  dbgBody = "\"" + text + "\"";
  dbgDirty = true;
  xSemaphoreGive(mtx);
}

// Antre rekaman satu lari ({...} JSON) untuk dikirim ke /devices/{role}/runs/{id}.
// Disimpan dulu di NVS, jadi aman walau WiFi mati atau jam di-reboot sebelum terkirim.
inline bool saveRun(const char* id, const char* json) {
  if (!mtx || !xSemaphoreTake(mtx, pdMS_TO_TICKS(500))) return false;
  bool ok = false;
  prefs.begin("runs", false);
  int slot = -1;
  for (int i = 0; i < RUN_SLOTS && slot < 0; i++) { char k[8]; snprintf(k, sizeof k, "r%d", i); if (!prefs.isKey(k)) slot = i; }
  if (slot < 0) slot = 0;                             // penuh: timpa yang tertua (slot 0)
  char k[8]; snprintf(k, sizeof k, "r%d", slot);
  String v = String(id) + "|" + json;
  ok = prefs.putString(k, v) == v.length();
  prefs.end();
  xSemaphoreGive(mtx);
  return ok;
}

}  // namespace cloud
