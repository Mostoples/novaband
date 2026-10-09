/* =========================================================
   Nova-Band — link to the band (T-Display-S3 firmware)

   Two transports, one protocol (firmware/novaband_display/src/protocol.h):
     * Bluetooth LE  — Web Bluetooth (Chrome / Edge on Android, Windows,
                       macOS, ChromeOS; not iOS Safari)
     * USB           — Web Serial (Chrome / Edge on desktop), JSON lines

   window.NovaLink:
     connect("ble" | "usb")  -> Promise
     disconnect()
     send({cmd: ...})        -> Promise
     on(event, fn)           events: status, telemetry, wave, info, message
     state                   { transport, name, fw, connected }
   ========================================================= */
(function () {
  "use strict";

  var SVC = "4e420001-6e6f-7661-6261-6e6453330000";
  var TELEM = "4e420002-6e6f-7661-6261-6e6453330000";
  var WAVE = "4e420003-6e6f-7661-6261-6e6453330000";
  var CMD = "4e420004-6e6f-7661-6261-6e6453330000";
  var ESPRESSIF_VID = 0x303a;

  var handlers = {};
  var state = { transport: null, name: "", fw: "", connected: false };
  var ble = null;          // { device, cmd }
  var serial = null;       // { port, writer, reader, keepAlive }
  var timeSync = null;
  var enc = new TextEncoder(), dec = new TextDecoder();

  function emit(ev, data) { (handlers[ev] || []).forEach(function (fn) { try { fn(data); } catch (e) { console.error(e); } }); }
  function on(ev, fn) { (handlers[ev] = handlers[ev] || []).push(fn); }

  function setStatus(connected, transport) {
    state.connected = connected;
    state.transport = connected ? transport : null;
    if (!connected) { state.name = ""; state.fw = ""; }
    emit("status", state);
  }

  function handleJson(text) {
    var msg;
    try { msg = JSON.parse(text); } catch (e) { return; }
    if (msg.t === "m") emit("telemetry", msg);
    else if (msg.t === "info") { state.name = msg.name; state.fw = msg.fw; emit("info", msg); emit("status", state); }
    else emit("message", msg);
  }

  /* ---------------- Web Bluetooth ---------------- */
  function connectBle() {
    if (!navigator.bluetooth) return Promise.reject(new Error("Web Bluetooth tidak tersedia di browser ini"));
    var device;
    return navigator.bluetooth.requestDevice({
      filters: [{ namePrefix: "NovaBand" }],
      optionalServices: [SVC, "heart_rate", "battery_service"]
    }).then(function (d) {
      device = d;
      device.addEventListener("gattserverdisconnected", function () { ble = null; setStatus(false); });
      return device.gatt.connect();
    }).then(function (server) {
      return server.getPrimaryService(SVC);
    }).then(function (svc) {
      return Promise.all([svc.getCharacteristic(TELEM), svc.getCharacteristic(WAVE), svc.getCharacteristic(CMD)]);
    }).then(function (ch) {
      ch[0].addEventListener("characteristicvaluechanged", function (e) {
        handleJson(dec.decode(e.target.value));
      });
      ch[1].addEventListener("characteristicvaluechanged", function (e) {
        var v = e.target.value, out = [];
        for (var i = 1; i < v.byteLength; i++) out.push(v.getInt8(i) / 90);   // byte 0 = sequence
        emit("wave", out);
      });
      ble = { device: device, cmd: ch[2] };
      state.name = device.name || "NovaBand";
      return ch[0].startNotifications().then(function () { return ch[1].startNotifications(); });
    }).then(function () {
      setStatus(true, "ble");
    });
  }

  /* ---------------- Web Serial ---------------- */
  function connectUsb() {
    if (!navigator.serial) return Promise.reject(new Error("Web Serial tidak tersedia di browser ini (gunakan Chrome/Edge desktop)"));
    var port;
    return navigator.serial.requestPort({ filters: [{ usbVendorId: ESPRESSIF_VID }] }).then(function (p) {
      port = p;
      return port.open({ baudRate: 115200 });
    }).then(function () {
      // keep the ESP32-S3 out of reset / download mode
      return port.setSignals ? port.setSignals({ dataTerminalReady: false, requestToSend: false }).catch(function () {}) : null;
    }).then(function () {
      serial = { port: port, writer: port.writable.getWriter(), reader: null, keepAlive: null };
      serial.keepAlive = setInterval(function () { send({ cmd: "ping" }).catch(function () {}); }, 3000);
      readSerial();
      state.name = "NovaBand (USB)";
      setStatus(true, "usb");
      navigator.serial.addEventListener("disconnect", function (e) { if (serial && e.target === port) closeSerial(); });
    });
  }

  function readSerial() {
    var buf = "";
    var reader = serial.port.readable.getReader();
    serial.reader = reader;
    (function pump() {
      reader.read().then(function (r) {
        if (r.done) return;
        buf += dec.decode(r.value, { stream: true });
        var lines = buf.split(/\r?\n/);
        buf = lines.pop();
        lines.forEach(function (l) { if (l.charAt(0) === "{") handleJson(l); });   // "#" lines are the firmware log
        pump();
      }).catch(function () { closeSerial(); });
    })();
  }

  function closeSerial() {
    if (!serial) return;
    var s = serial;
    serial = null;
    clearInterval(s.keepAlive);
    Promise.resolve()
      .then(function () { return s.reader && s.reader.cancel(); })
      .then(function () { s.writer.releaseLock(); return s.port.close(); })
      .catch(function () {});
    setStatus(false);
  }

  /* ---------------- Cloud (Firebase Realtime Database) ----------------
     The band uploads its telemetry to /devices/<ROLE>/live every 2 s over WiFi; the site only reads it.
     No pairing needed, works from any browser/phone. Commands cannot go back this way (BLE/USB only). */
  var CLOUD_ROLE = "esplilygo", STALE_MS = 9000;
  var cloud = null;        // { offLive, offInfo, lastTs, lastAt, timer }
  var autoCloud = true;    // reconnect to the cloud automatically until the user disconnects on purpose

  function connectCloud() {
    if (!window.NovaCloud || !window.NovaCloud.watch) return Promise.reject(new Error("Firebase belum siap"));
    closeCloud();
    cloud = { lastTs: 0, lastAt: 0, up: false };
    var c = cloud;
    c.offInfo = window.NovaCloud.watch("devices/" + CLOUD_ROLE + "/info", function (v) {
      if (v) { state.name = v.name || "NovaBand"; if (state.connected && state.transport === "cloud") emit("status", state); }
    });
    c.offLive = window.NovaCloud.watch("devices/" + CLOUD_ROLE + "/live", function (v) {
      if (!v || c !== cloud) return;
      var prev = c.lastTs;
      c.lastTs = v.ts;
      /* fresh = the band just uploaded: ts moved on, or (first value) it is recent by the local clock */
      var fresh = prev ? v.ts !== prev : Math.abs(Date.now() - v.ts) < STALE_MS * 2;
      if (fresh) c.lastAt = Date.now();
      if (!c.up) {
        if (!fresh) return;
        c.up = true;
        setStatus(true, "cloud");
      }
      if (!fresh) return;
      if (v.t === "m") emit("telemetry", v);
    });
    c.timer = setInterval(function () {          // no new upload for a while: the band is off or out of WiFi
      if (c.up && Date.now() - c.lastAt > STALE_MS) { c.up = false; setStatus(false); }
    }, 2000);
    return Promise.resolve();
  }

  function closeCloud() {
    if (!cloud) return;
    clearInterval(cloud.timer);
    if (cloud.offLive) cloud.offLive();
    if (cloud.offInfo) cloud.offInfo();
    var was = cloud.up;
    cloud = null;
    if (was && state.transport === "cloud") setStatus(false);
  }

  /* ---------------- common ---------------- */
  function send(obj) {
    if (cloud) return Promise.resolve();      // read-only link
    var text = JSON.stringify(obj);
    if (ble) return ble.cmd.writeValueWithResponse(enc.encode(text));
    if (serial) return serial.writer.write(enc.encode(text + "\n"));
    return Promise.reject(new Error("not connected"));
  }

  function connect(kind) {
    disconnect();
    autoCloud = kind === "cloud";
    if (kind === "cloud") return connectCloud();
    var p = kind === "usb" ? connectUsb() : connectBle();
    return p.then(function () { return hello(); }).then(function () {
      clearInterval(timeSync);                          // keep the band clock on the phone's time
      timeSync = setInterval(function () {
        send({ cmd: "time", t: Math.floor(Date.now() / 1000), tz: -new Date().getTimezoneOffset() }).catch(function () {});
      }, 300000);
    });
  }

  function hello() {
    var prof = (window.NovaProfile && window.NovaProfile()) || {};
    return send({
      cmd: "hello",
      name: prof.name || "Runner",
      age: prof.age || 17,
      hrmax: prof.hrmax || 195,
      rest: prof.rest || 62,
      height: prof.height || 170,
      alert: prof.alert || 185,
      t: Math.floor(Date.now() / 1000),
      tz: -new Date().getTimezoneOffset()
    });
  }

  function disconnect() {
    clearInterval(timeSync);
    closeCloud();
    if (ble) { try { ble.device.gatt.disconnect(); } catch (e) {} ble = null; }
    if (serial) closeSerial();
    if (state.connected) setStatus(false);
  }

  /* Start listening as soon as Firebase is up, unless a direct link (BLE/USB) is already open. */
  document.addEventListener("novaband:cloud-ready", function () {
    if (!state.connected && !ble && !serial && autoCloud && !cloud) connectCloud().catch(function () {});
  });

  window.NovaLink = {
    connect: connect, disconnect: disconnect, send: send, on: on, state: state,
    support: { ble: !!navigator.bluetooth, usb: !!navigator.serial, cloud: true }
  };
})();
