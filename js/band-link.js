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

  /* ---------------- common ---------------- */
  function send(obj) {
    var text = JSON.stringify(obj);
    if (ble) return ble.cmd.writeValueWithResponse(enc.encode(text));
    if (serial) return serial.writer.write(enc.encode(text + "\n"));
    return Promise.reject(new Error("not connected"));
  }

  function connect(kind) {
    disconnect();
    var p = kind === "usb" ? connectUsb() : connectBle();
    return p.then(function () { return hello(); });
  }

  function hello() {
    var prof = (window.NovaProfile && window.NovaProfile()) || {};
    return send({
      cmd: "hello",
      name: prof.name || "Runner",
      age: prof.age || 17,
      hrmax: prof.hrmax || 195,
      rest: prof.rest || 62,
      alert: prof.alert || 185,
      t: Math.floor(Date.now() / 1000),
      tz: -new Date().getTimezoneOffset()
    });
  }

  function disconnect() {
    if (ble) { try { ble.device.gatt.disconnect(); } catch (e) {} ble = null; }
    if (serial) closeSerial();
    if (state.connected) setStatus(false);
  }

  window.NovaLink = {
    connect: connect, disconnect: disconnect, send: send, on: on, state: state,
    support: { ble: !!navigator.bluetooth, usb: !!navigator.serial }
  };
})();
