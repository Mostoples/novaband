// ============================================================
// Nova-Band — firmware for the LILYGO T-Display-S3 Touch (ESP32-S3R8)
//
//   display  ST7789 170x320 on the 8-bit i80 bus, esp_lcd + DMA, two frame
//            buffers (draw one while the other is on the wire), ~60 fps
//   assets   Blender renders + fonts in the "assets" flash partition,
//            memory-mapped (tools/fw_assets.py -> build/fw/assets.bin)
//   input    CST816 touch (swipe between pages, tap), BOOT + KEY buttons
//   link     Bluetooth LE: standard Heart Rate (0x180D) + Battery (0x180F)
//            services, so any HR app can read it, plus the Nova-Band service
//            (JSON telemetry, PPG wave, commands) for the web app;
//            the same JSON lines over USB serial for Web Serial.
//
// Build + flash: firmware/flash.ps1 (arduino-cli + esptool). Board options:
//   esp32:esp32:esp32s3:CDCOnBoot=cdc,FlashSize=16M,PSRAM=opi,PartitionScheme=custom
// ============================================================
#include <Arduino.h>
#include <BLE2902.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <Wire.h>
#include <esp_lcd_io_i80.h>
#include <esp_lcd_panel_io.h>
#include <esp_lcd_panel_ops.h>
#include <esp_lcd_panel_st7789.h>
#include <esp_mac.h>
#include <esp_partition.h>
#include <freertos/queue.h>
#include <freertos/semphr.h>

#include "sensors.h"
#include "src/assets.h"
#include "src/gfx.h"
#include "src/model.h"
#include "src/protocol.h"
#include "src/ui.h"

// ---------------------------------------------------------------- pins (T-Display-S3)
static const int PIN_PWR = 15, PIN_BL = 38, PIN_RD = 9, PIN_WR = 8, PIN_DC = 7, PIN_CS = 6, PIN_RST = 5;
static const int PIN_D[8] = {39, 40, 41, 42, 45, 46, 47, 48};
static const int PIN_SDA = 18, PIN_SCL = 17, PIN_TINT = 16, PIN_TRST = 21;
static const int PIN_BTN_PREV = 0, PIN_BTN_NEXT = 14, PIN_BAT = 4;
static const uint32_t PCLK_HZ = 20 * 1000 * 1000;

// Touch panel -> landscape screen, as in LILYGO's own example (swap XY,
// mirror X). The CST816 reports in the panel's native
// portrait frame; flip these if a swipe goes the wrong way (raw values are
// logged on the serial port as "# touch").
#define TOUCH_SWAP 1
#define TOUCH_FLIP_X 1
#define TOUCH_FLIP_Y 0

// ---------------------------------------------------------------- BLE UUIDs
#define NB_SVC   "4e420001-6e6f-7661-6261-6e6453330000"
#define NB_TELEM "4e420002-6e6f-7661-6261-6e6453330000"
#define NB_WAVE  "4e420003-6e6f-7661-6261-6e6453330000"
#define NB_CMD   "4e420004-6e6f-7661-6261-6e6453330000"

// ---------------------------------------------------------------- state
static esp_lcd_panel_handle_t panel;
static esp_lcd_panel_io_handle_t io;
// The frame is drawn as two 85-row bands, one per CPU core, each in its own
// internal-RAM DMA buffer (same memory as one full frame). Core 0 draws the
// top band while core 1 (loop) draws the bottom one; then both go out on the
// i80 bus. A band is reused as soon as its own transfer is done.
static const int BAND = gfx::H / 2;
static uint16_t* band[2] = {nullptr, nullptr};
static SemaphoreHandle_t bandFree[2], goTop, doneTop;
static volatile int dmaNext = 0;                   // which band the next "done" belongs to
static gfx::Canvas canvasTop, canvasBot;
static Assets assets;
static Model model;
static Ui ui;
static char devName[24];
static int brightness = 220;

struct Line { char s[256]; uint8_t src; };      // commands from BLE/USB, handled in loop()
static QueueHandle_t cmdQ;
static BLECharacteristic *chTelem, *chWave, *chHr, *chBat;
static volatile int bleClients = 0;
static uint32_t usbSeenMs = 0;                  // last command over USB
static bool usbStream = false;

static float uptime() { return millis() / 1000.f; }
static void setBrightness(int v) { brightness = constrain(v, 10, 255); }

// ---------------------------------------------------------------- display
static bool IRAM_ATTR onDone(esp_lcd_panel_io_handle_t, esp_lcd_panel_io_event_data_t*, void*) {
  BaseType_t woken = pdFALSE;
  int b = dmaNext;
  dmaNext = b ^ 1;
  xSemaphoreGiveFromISR(bandFree[b], &woken);
  return woken == pdTRUE;
}

static void displayInit() {
  pinMode(PIN_RD, OUTPUT);
  digitalWrite(PIN_RD, HIGH);
  esp_lcd_i80_bus_handle_t bus = nullptr;
  esp_lcd_i80_bus_config_t bc = {};
  bc.dc_gpio_num = PIN_DC;
  bc.wr_gpio_num = PIN_WR;
  bc.clk_src = LCD_CLK_SRC_DEFAULT;
  for (int i = 0; i < 8; i++) bc.data_gpio_nums[i] = PIN_D[i];
  bc.bus_width = 8;
  bc.max_transfer_bytes = gfx::W * gfx::H * 2;
  bc.dma_burst_size = 64;
  ESP_ERROR_CHECK(esp_lcd_new_i80_bus(&bc, &bus));

  esp_lcd_panel_io_i80_config_t ic = {};
  ic.cs_gpio_num = PIN_CS;
  ic.pclk_hz = PCLK_HZ;
  ic.trans_queue_depth = 4;
  ic.on_color_trans_done = onDone;
  ic.lcd_cmd_bits = 8;
  ic.lcd_param_bits = 8;
  ic.dc_levels.dc_data_level = 1;
  ic.flags.swap_color_bytes = 1;               // RGB565 in memory is little-endian; the ST7789 wants MSB first
  ESP_ERROR_CHECK(esp_lcd_new_panel_io_i80(bus, &ic, &io));

  esp_lcd_panel_dev_config_t pc = {};
  pc.reset_gpio_num = PIN_RST;
  pc.rgb_ele_order = LCD_RGB_ELEMENT_ORDER_RGB;
  pc.bits_per_pixel = 16;
  ESP_ERROR_CHECK(esp_lcd_new_panel_st7789(io, &pc, &panel));
  esp_lcd_panel_reset(panel);
  esp_lcd_panel_init(panel);
  esp_lcd_panel_invert_color(panel, true);
  esp_lcd_panel_swap_xy(panel, true);          // landscape, USB-C on the left
  esp_lcd_panel_mirror(panel, false, true);
  esp_lcd_panel_set_gap(panel, 0, 35);         // 170 visible rows of the 240-row controller
  esp_lcd_panel_disp_on_off(panel, true);

  for (int i = 0; i < 2; i++) {
    band[i] = (uint16_t*)esp_lcd_i80_alloc_draw_buffer(io, gfx::W * BAND * 2, MALLOC_CAP_DMA | MALLOC_CAP_INTERNAL);
    memset(band[i], 0, gfx::W * BAND * 2);
    bandFree[i] = xSemaphoreCreateBinary();
    xSemaphoreGive(bandFree[i]);
  }
  canvasTop.band(band[0], 0, BAND);
  canvasBot.band(band[1], BAND, gfx::H);
}

// core 0: draws the top band whenever the loop says go
static void renderTopTask(void*) {
  for (;;) {
    xSemaphoreTake(goTop, portMAX_DELAY);
    xSemaphoreTake(bandFree[0], portMAX_DELAY);
    ui.render(canvasTop);
    xSemaphoreGive(doneTop);
  }
}

// ---------------------------------------------------------------- assets
static bool assetsInit() {
  const esp_partition_t* p = esp_partition_find_first(ESP_PARTITION_TYPE_DATA, (esp_partition_subtype_t)0x40, "assets");
  if (!p) return false;
  const void* ptr = nullptr;
  esp_partition_mmap_handle_t h;
  if (esp_partition_mmap(p, 0, p->size, ESP_PARTITION_MMAP_DATA, &ptr, &h) != ESP_OK) return false;
  if (!assets.load((const uint8_t*)ptr)) return false;
  // everything after the splash -> PSRAM; the half-res background -> internal RAM
  assets.relocate(A::BG, [](size_t n) { return heap_caps_malloc(n, MALLOC_CAP_SPIRAM); });
  gfx::Image bg = assets.image(A::BG);
  uint16_t* fast = (uint16_t*)heap_caps_malloc(bg.w * bg.h * 2, MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT);
  if (fast) { memcpy(fast, bg.px, bg.w * bg.h * 2); ui.setBackground(fast); }
  return true;
}

// ---------------------------------------------------------------- touch (CST816)
static bool touchRead(int& x, int& y) {
  Wire.beginTransmission(0x15);
  Wire.write(0x02);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom(0x15, 5) != 5) return false;
  uint8_t n = Wire.read(), xh = Wire.read(), xl = Wire.read(), yh = Wire.read(), yl = Wire.read();
  if (!(n & 0x0F)) return false;
  int tx = ((xh & 0x0F) << 8) | xl, ty = ((yh & 0x0F) << 8) | yl;
  static uint32_t lastLog = 0;
  if (millis() - lastLog > 250) { Serial.printf("# touch raw %d,%d\n", tx, ty); lastLog = millis(); }
#if TOUCH_SWAP
  x = ty; y = tx;
#else
  x = tx; y = ty;
#endif
#if TOUCH_FLIP_X
  x = gfx::W - 1 - x;
#endif
#if TOUCH_FLIP_Y
  y = gfx::H - 1 - y;
#endif
  return true;
}

static void touchInit() {
  pinMode(PIN_TRST, OUTPUT);
  digitalWrite(PIN_TRST, LOW);
  delay(10);
  digitalWrite(PIN_TRST, HIGH);
  delay(60);
  pinMode(PIN_TINT, INPUT);
  Wire.begin(PIN_SDA, PIN_SCL, 400000);
}

// ---------------------------------------------------------------- buttons
struct Button {
  int pin; uint32_t downAt = 0; bool down = false, longFired = false;
  // 0 nothing, 1 short press, 2 long press (fires once while held)
  int poll() {
    bool d = digitalRead(pin) == LOW;
    uint32_t now = millis();
    int ev = 0;
    if (d && !down) { down = true; downAt = now; longFired = false; }
    else if (d && down && !longFired && now - downAt > 650) { longFired = true; ev = 2; }
    else if (!d && down) { down = false; if (!longFired && now - downAt > 25) ev = 1; }
    return ev;
  }
};
static Button bPrev{PIN_BTN_PREV}, bNext{PIN_BTN_NEXT};

// ---------------------------------------------------------------- battery
static void batteryRead() {
  static float v = 0;
  float mv = analogReadMilliVolts(PIN_BAT) * 2.f;            // 1:2 divider on the board
  v = v ? v * .9f + mv * .1f : mv;
  model.m.usbPower = v > 4350;
  float pct = (v - 3300) / (4150 - 3300) * 100;
  model.m.battery = model.m.usbPower ? 100 : constrain((int)pct, 0, 100);
}

// ---------------------------------------------------------------- sensors -> model
// Fresh readings replace the simulation; a stale one lets the model take over again.
static void applySensors() {
  using namespace sensors;
  uint32_t ms = millis();
  float up = uptime();
  auto fresh = [&](uint32_t at) { return at && ms - at < VALID_MS; };
  if (fresh(data.hrAt)) model.setRealHr(data.hr, up);
  if (fresh(data.spo2At)) model.setRealSpo2(data.spo2, up);
  if (fresh(data.cadAt)) model.setRealCadence(data.cadence, up);
  model.m.temp = fresh(data.tempAt) ? data.temp : 0;
}

// ---------------------------------------------------------------- BLE
class SrvCb : public BLEServerCallbacks {
  void onConnect(BLEServer*) override { bleClients++; }
  void onDisconnect(BLEServer* s) override {
    if (bleClients > 0) bleClients--;
    s->startAdvertising();                                  // stay discoverable
  }
};
class CmdCb : public BLECharacteristicCallbacks {
  void onWrite(BLECharacteristic* c) override {
    Line l = {};
    String v = c->getValue();
    strncpy(l.s, v.c_str(), sizeof l.s - 1);
    l.src = 0;
    xQueueSend(cmdQ, &l, 0);
  }
};

static void bleInit() {
  BLEDevice::init(devName);
  BLEDevice::setMTU(247);
  BLEServer* srv = BLEDevice::createServer();
  srv->setCallbacks(new SrvCb());

  BLEService* hrs = srv->createService(BLEUUID((uint16_t)0x180D));
  chHr = hrs->createCharacteristic(BLEUUID((uint16_t)0x2A37), BLECharacteristic::PROPERTY_NOTIFY);
  chHr->addDescriptor(new BLE2902());
  BLECharacteristic* loc = hrs->createCharacteristic(BLEUUID((uint16_t)0x2A38), BLECharacteristic::PROPERTY_READ);
  uint8_t other = 0;                                        // body sensor location: "other" (upper arm)
  loc->setValue(&other, 1);
  hrs->start();

  BLEService* bas = srv->createService(BLEUUID((uint16_t)0x180F));
  chBat = bas->createCharacteristic(BLEUUID((uint16_t)0x2A19), BLECharacteristic::PROPERTY_READ | BLECharacteristic::PROPERTY_NOTIFY);
  chBat->addDescriptor(new BLE2902());
  bas->start();

  BLEService* nb = srv->createService(NB_SVC);
  chTelem = nb->createCharacteristic(NB_TELEM, BLECharacteristic::PROPERTY_NOTIFY | BLECharacteristic::PROPERTY_READ);
  chTelem->addDescriptor(new BLE2902());
  chWave = nb->createCharacteristic(NB_WAVE, BLECharacteristic::PROPERTY_NOTIFY);
  chWave->addDescriptor(new BLE2902());
  BLECharacteristic* cmd = nb->createCharacteristic(NB_CMD, BLECharacteristic::PROPERTY_WRITE | BLECharacteristic::PROPERTY_WRITE_NR);
  cmd->setCallbacks(new CmdCb());
  nb->start();

  BLEAdvertising* adv = BLEDevice::getAdvertising();
  adv->addServiceUUID(NB_SVC);
  adv->addServiceUUID(BLEUUID((uint16_t)0x180D));
  adv->setScanResponse(true);
  BLEDevice::startAdvertising();
}

static void send(const char* s, uint8_t src) {
  if (src == 1) { Serial.println(s); return; }
  if (bleClients > 0) { chTelem->setValue((uint8_t*)s, strlen(s)); chTelem->notify(); }
}

static void linkTick() {
  static uint32_t lastTelem = 0, lastWave = 0;
  uint32_t now = millis();
  bool usb = usbStream && now - usbSeenMs < 8000;
  ui.setLink(bleClients > 0 ? Link::Ble : usb ? Link::Usb : Link::Advertising,
             bleClients > 0 ? "Web Bluetooth" : usb ? "Web Serial" : "");
  char buf[256];
  if (now - lastTelem >= 1000) {
    lastTelem = now;
    proto::telemetry(model, buf, sizeof buf);
    if (usb) Serial.println(buf);
    if (bleClients > 0) {
      chTelem->setValue((uint8_t*)buf, strlen(buf));
      chTelem->notify();
      uint8_t hr[2] = {0x00, (uint8_t)constrain((int)(model.m.hr + .5f), 0, 255)};   // flags: uint8 HR
      chHr->setValue(hr, 2);
      chHr->notify();
      uint8_t b = (uint8_t)model.m.battery;
      chBat->setValue(&b, 1);
      chBat->notify();
    }
  }
  // PPG wave: the newest 20 samples as int8, every 400 ms, with a sequence byte
  if (bleClients > 0 && now - lastWave >= 400) {
    lastWave = now;
    uint8_t pkt[21];
    static uint8_t seq = 0;
    pkt[0] = seq++;
    for (int i = 0; i < 20; i++) {
      float v = model.ppg[(model.ppgHead + Model::PPG_N - 20 + i) % Model::PPG_N];
      pkt[1 + i] = (uint8_t)(int8_t)constrain((int)(v * 90), -127, 127);
    }
    chWave->setValue(pkt, sizeof pkt);
    chWave->notify();
  }
}

static void serialPoll() {
  static char line[256];
  static int n = 0;
  while (Serial.available()) {
    char ch = (char)Serial.read();
    if (ch == '\n' || ch == '\r') {
      if (n) {
        line[n] = 0;
        Line l = {};
        strncpy(l.s, line, sizeof l.s - 1);
        l.src = 1;
        xQueueSend(cmdQ, &l, 0);
        n = 0;
      }
    } else if (n < (int)sizeof line - 1) line[n++] = ch;
  }
}

static void handleCommands() {
  Line l;
  char reply[256];
  proto::Env env{&model, &ui, devName, setBrightness, uptime};
  while (xQueueReceive(cmdQ, &l, 0) == pdTRUE) {
    if (l.s[0] != '{') continue;
    if (l.src == 1) { usbSeenMs = millis(); usbStream = true; }
    int r = proto::handle(l.s, strlen(l.s), env, reply, sizeof reply);
    if (r > 0) send(reply, l.src);
  }
}


// ---------------------------------------------------------------- setup / loop
void setup() {
  pinMode(PIN_PWR, OUTPUT);
  digitalWrite(PIN_PWR, HIGH);                  // peripheral power (LCD, touch) on battery
  Serial.begin(115200);
  pinMode(PIN_BTN_PREV, INPUT_PULLUP);
  pinMode(PIN_BTN_NEXT, INPUT_PULLUP);
  ledcAttach(PIN_BL, 20000, 8);
  ledcWrite(PIN_BL, 0);

  uint8_t mac[6];
  esp_read_mac(mac, ESP_MAC_BT);
  snprintf(devName, sizeof devName, "NovaBand-%02X%02X", mac[4], mac[5]);

  displayInit();
  if (!assetsInit()) {
    // no asset image flashed: a plain wine screen + instructions on the serial port
    for (int i = 0; i < gfx::W * BAND; i++) band[0][i] = gfx::hex(0x7B2021);
    xSemaphoreTake(bandFree[0], portMAX_DELAY);
    esp_lcd_panel_draw_bitmap(panel, 0, 0, gfx::W, BAND, band[0]);
    xSemaphoreTake(bandFree[1], portMAX_DELAY);
    esp_lcd_panel_draw_bitmap(panel, 0, BAND, gfx::W, gfx::H, band[0]);
    ledcWrite(PIN_BL, 200);
    while (true) {
      Serial.println("# assets partition missing or stale: flash build/fw/assets.bin at 0x310000");
      delay(2000);
    }
  }
  touchInit();
  sensors::begin();
  cmdQ = xQueueCreate(8, sizeof(Line));
  ui.begin(&assets, &model);
  ui.setDeviceName(devName);
  bleInit();
  goTop = xSemaphoreCreateBinary();
  doneTop = xSemaphoreCreateBinary();
  xTaskCreatePinnedToCore(renderTopTask, "render0", 6144, nullptr, 3, nullptr, 0);
  Serial.printf("# %s ready, banded dual-core render, heap %u, psram %u\n", devName,
                (unsigned)ESP.getFreeHeap(), (unsigned)ESP.getFreePsram());
}

void loop() {
  static uint32_t last = micros(), statT = millis();
  static int frames = 0;
  static float renderMs = 0;
  static int bl = 0;
  uint32_t nowUs = micros();
  float dt = (nowUs - last) / 1e6f;
  last = nowUs;
  if (dt > .1f) dt = .1f;

  // input
  int tx, ty;
  bool td = touchRead(tx, ty);
  static int lx = 0, ly = 0;
  if (td) { lx = tx; ly = ty; }
  ui.touch(td, lx, ly);
  int e = bNext.poll();
  if (e) ui.buttonNext(e == 2);
  e = bPrev.poll();
  if (e) ui.buttonPrev(e == 2);

  serialPoll();
  handleCommands();
  static uint32_t batT = 0;
  if (millis() - batT > 500) { batT = millis(); batteryRead(); }

  applySensors();
  model.update(dt, uptime());
  ui.update(dt);
  linkTick();

  // backlight eases in with the splash, then follows the brightness setting
  int target = brightness;
  bl += (target - bl) / 6 + (target > bl ? 1 : target < bl ? -1 : 0);
  ledcWrite(PIN_BL, constrain(bl, 0, 255));

  uint32_t r0 = micros();
  xSemaphoreGive(goTop);                        // core 0 starts on the top band
  xSemaphoreTake(bandFree[1], portMAX_DELAY);   // bottom band off the bus?
  ui.render(canvasBot);                         // core 1 draws the bottom band
  xSemaphoreTake(doneTop, portMAX_DELAY);
  renderMs += (micros() - r0) / 1000.f;
  esp_lcd_panel_draw_bitmap(panel, 0, 0, gfx::W, BAND, band[0]);
  esp_lcd_panel_draw_bitmap(panel, 0, BAND, gfx::W, gfx::H, band[1]);

  frames++;
  if (millis() - statT >= 5000) {
    Serial.printf("# fps %.1f  render %.1f ms  heap %u  ble %d  page %d\n", frames * 1000.f / (millis() - statT),
                  renderMs / frames, (unsigned)ESP.getFreeHeap(), bleClients, ui.page());
    statT = millis(); frames = 0; renderMs = 0;
  }
  // cap at ~60 fps
  uint32_t spent = micros() - nowUs;
  if (spent < 15000) delay((16000 - spent) / 1000);       // yields to the BLE / USB tasks
}
