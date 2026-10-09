/* ============================================================
   NovaBand — application dashboard simulation
   A self-contained physiological model so the demo behaves like the
   real device: PPG waveform, HR response with lag + cardiac drift,
   cadence/pace, zone accumulation, soft-tissue load, readiness,
   and the Biological Early Warning engine.
   ============================================================ */
(function () {
  "use strict";

  var doc = document;
  var $ = function (id) { return doc.getElementById(id); };
  var clamp = function (v, a, b) { return Math.max(a, Math.min(b, v)); };
  var rnd = function (a, b) { return a + Math.random() * (b - a); };

  /* ---------------- State ---------------- */
  var S = {
    connected: false,
    band: false,          // true while a real Nova-Band streams telemetry (BLE / USB)
    bandDemo: true,       // the band reports whether its HR is simulated
    spo2: 98,
    running: false,
    t: 0,                 // elapsed seconds
    effort: 55,           // 0-100 user driven intensity
    hr: 68,               // current bpm
    restHR: 62,
    maxHR: 195,
    cadence: 0,
    pace: 0,              // min per km
    dist: 0,              // km
    kcal: 0,
    zoneSec: [0, 0, 0, 0, 0],
    readiness: 85,
    battery: 87,
    phase: 0,             // PPG waveform phase
    thr: { hr: 185, load: 75, ready: 70 },
    /* the six inputs behind the Readiness Score, 0-100 */
    factors: { hrv: 72, rhr: 80, acwr: 65, rec: 88, kin: 91, fat: 58 },
    tissue: {
      achilles:  { label: "Achilles tendon",   v: 41, rate: 0.85 },
      itbs:      { label: "Iliotibial band",   v: 35, rate: 0.72 },
      hamstring: { label: "Hamstring",         v: 28, rate: 0.60 },
      quadriceps:{ label: "Quadriceps",        v: 24, rate: 0.55 },
      calf:      { label: "Gastrocnemius",     v: 31, rate: 0.66 }
    },
    cooldown: {}
  };
  /* read by js/app-home.js for the Beranda widgets; never written to from outside */
  window.NovaState = S;
  /* profile sent to the band on connect (js/band-link.js) */
  window.NovaProfile = function () {
    return { name: "Runner", age: 17, hrmax: S.maxHR, rest: S.restHR, alert: S.thr.hr, height: 170 };
  };

  var ZONES = [
    { name: "Zona 1", cls: "z1", lo: 0.00, hi: 0.60, tag: "Pemulihan" },
    { name: "Zona 2", cls: "z2", lo: 0.60, hi: 0.70, tag: "Aerobik" },
    { name: "Zona 3", cls: "z3", lo: 0.70, hi: 0.80, tag: "Tempo" },
    { name: "Zona 4", cls: "z4", lo: 0.80, hi: 0.90, tag: "Ambang" },
    { name: "Zona 5", cls: "z5", lo: 0.90, hi: 1.20, tag: "Maksimal" }
  ];

  function currentZone() {
    var f = S.hr / S.maxHR;
    for (var i = ZONES.length - 1; i >= 0; i--) if (f >= ZONES[i].lo) return i;
    return 0;
  }

  function cssVar(name) {
    return getComputedStyle(doc.documentElement).getPropertyValue(name).trim();
  }

  /* ---------------- Toasts ---------------- */
  function toast(msg) {
    var box = $("toasts");
    if (!box) return;
    var el = doc.createElement("div");
    el.className = "toast";
    el.textContent = msg;
    box.appendChild(el);
    setTimeout(function () {
      el.style.transition = "opacity .4s, transform .4s";
      el.style.opacity = "0";
      el.style.transform = "translateX(30px)";
      setTimeout(function () { el.remove(); }, 420);
    }, 3200);
  }

  /* ---------------- Alerts ---------------- */
  function alertCard(kind, title, body) {
    var icons = { info: "i", warn: "!", danger: "!", good: "✓" };
    var box = $("alerts");
    if (!box) return;
    var el = doc.createElement("div");
    el.className = "alert " + kind;
    el.innerHTML =
      '<div class="ic">' + icons[kind] + "</div>" +
      "<div><strong></strong><p></p></div>" +
      '<span class="t"></span>';
    el.querySelector("strong").textContent = title;
    el.querySelector("p").textContent = body;
    el.querySelector(".t").textContent = fmtTime(S.t);
    box.prepend(el);
    while (box.children.length > 14) box.lastChild.remove();
  }

  function once(key, seconds, fn) {
    var now = S.t;
    if (S.cooldown[key] !== undefined && now - S.cooldown[key] < seconds) return;
    S.cooldown[key] = now;
    fn();
  }

  /* ---------------- Formatting ---------------- */
  function fmtTime(sec) {
    var m = Math.floor(sec / 60), s = Math.floor(sec % 60);
    return String(m).padStart(2, "0") + ":" + String(s).padStart(2, "0");
  }
  function fmtPace(p) {
    if (!p || !isFinite(p)) return "—";
    var m = Math.floor(p), s = Math.round((p - m) * 60);
    if (s === 60) { m++; s = 0; }
    return m + ":" + String(s).padStart(2, "0");
  }

  /* =========================================================
     PPG waveform canvas
     ========================================================= */
  var ecg = $("ecg");
  var ectx = ecg ? ecg.getContext("2d") : null;
  var wave = [];
  var WAVE_LEN = 620;

  function sizeCanvas(c) {
    if (!c) return;
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    var w = c.clientWidth, h = c.clientHeight;
    c.width = Math.max(1, Math.round(w * dpr));
    c.height = Math.max(1, Math.round(h * dpr));
    var ctx = c.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  /* One cardiac cycle of a PPG pulse: systolic peak + dicrotic notch */
  function ppgSample(p) {
    var systolic = Math.exp(-Math.pow((p - 0.16) / 0.075, 2));
    var dicrotic = 0.38 * Math.exp(-Math.pow((p - 0.40) / 0.10, 2));
    var baseline = 0.05 * Math.sin(p * Math.PI * 2);
    return systolic + dicrotic + baseline;
  }

  function pushWave(dt) {
    if (S.band) return;                        // samples arrive from the band (NovaLink "wave")
    var perSample = 1 / 60;
    var steps = Math.max(1, Math.round(dt / perSample));
    for (var i = 0; i < steps; i++) {
      S.phase += (S.hr / 60) * perSample;
      if (S.phase >= 1) S.phase -= 1;
      var noise = S.running ? rnd(-0.022, 0.022) * (1 + S.effort / 160) : rnd(-0.008, 0.008);
      wave.push(ppgSample(S.phase) + noise);
      if (wave.length > WAVE_LEN) wave.shift();
    }
  }

  function drawWave() {
    if (!ectx || !ecg) return;
    var w = ecg.clientWidth, h = ecg.clientHeight;
    ectx.clearRect(0, 0, w, h);
    if (!w || !h) return;

    var line = cssVar("--line") || "rgba(0,0,0,.1)";
    var brand = cssVar("--brand-500") || "#b31e4b";
    var brand4 = cssVar("--brand-400") || "#d13a67";

    /* grid */
    ectx.strokeStyle = line;
    ectx.lineWidth = 1;
    ectx.beginPath();
    for (var gx = 0; gx <= w; gx += 40) { ectx.moveTo(gx + .5, 0); ectx.lineTo(gx + .5, h); }
    for (var gy = 0; gy <= h; gy += 28) { ectx.moveTo(0, gy + .5); ectx.lineTo(w, gy + .5); }
    ectx.stroke();

    if (wave.length < 2) return;

    var stepX = w / (WAVE_LEN - 1);
    var base = h * 0.86, amp = h * 0.62;
    var startIdx = WAVE_LEN - wave.length;

    /* filled area */
    var grad = ectx.createLinearGradient(0, 0, 0, h);
    grad.addColorStop(0, brand4 + "55");
    grad.addColorStop(1, brand4 + "00");
    ectx.beginPath();
    ectx.moveTo(startIdx * stepX, base);
    for (var i = 0; i < wave.length; i++) {
      ectx.lineTo((startIdx + i) * stepX, base - wave[i] * amp);
    }
    ectx.lineTo((WAVE_LEN - 1) * stepX, base);
    ectx.closePath();
    ectx.fillStyle = grad;
    ectx.fill();

    /* the trace */
    ectx.beginPath();
    for (var j = 0; j < wave.length; j++) {
      var x = (startIdx + j) * stepX, y = base - wave[j] * amp;
      if (j === 0) ectx.moveTo(x, y); else ectx.lineTo(x, y);
    }
    ectx.strokeStyle = brand;
    ectx.lineWidth = 2.2;
    ectx.lineJoin = "round";
    ectx.shadowColor = brand;
    ectx.shadowBlur = 12;
    ectx.stroke();
    ectx.shadowBlur = 0;

    /* leading dot */
    var lx = (WAVE_LEN - 1) * stepX;
    var ly = base - wave[wave.length - 1] * amp;
    ectx.beginPath();
    ectx.arc(lx, ly, 4, 0, Math.PI * 2);
    ectx.fillStyle = brand;
    ectx.fill();
  }

  /* =========================================================
     Weekly training-load chart
     ========================================================= */
  var WEEK = [
    { d: "Sen", v: 42 }, { d: "Sel", v: 68 }, { d: "Rab", v: 30 },
    { d: "Kam", v: 76 }, { d: "Jum", v: 22 }, { d: "Sab", v: 94 }, { d: "Min", v: 55 }
  ];
  function drawWeek() {
    var c = $("weekchart");
    if (!c) return;
    sizeCanvas(c);
    var ctx = c.getContext("2d");
    var w = c.clientWidth, h = c.clientHeight;
    ctx.clearRect(0, 0, w, h);
    var brand = cssVar("--brand-500") || "#b31e4b";
    var brand8 = cssVar("--brand-800") || "#6b1230";
    var text2 = cssVar("--text-2") || "#777";
    var line = cssVar("--line");

    var padB = 26, padT = 10;
    var bw = w / WEEK.length;
    var maxV = 100;

    ctx.strokeStyle = line; ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, h - padB + .5); ctx.lineTo(w, h - padB + .5);
    ctx.stroke();

    WEEK.forEach(function (item, i) {
      var bh = ((h - padB - padT) * item.v) / maxV;
      var x = i * bw + bw * 0.26;
      var bwid = bw * 0.48;
      var y = h - padB - bh;
      var g = ctx.createLinearGradient(0, y, 0, h - padB);
      g.addColorStop(0, brand);
      g.addColorStop(1, brand8);
      ctx.fillStyle = g;
      var r = Math.min(6, bwid / 2);
      ctx.beginPath();
      ctx.moveTo(x, h - padB);
      ctx.lineTo(x, y + r);
      ctx.quadraticCurveTo(x, y, x + r, y);
      ctx.lineTo(x + bwid - r, y);
      ctx.quadraticCurveTo(x + bwid, y, x + bwid, y + r);
      ctx.lineTo(x + bwid, h - padB);
      ctx.closePath();
      ctx.fill();

      ctx.fillStyle = text2;
      ctx.font = '11px "Outfit", sans-serif';
      ctx.textAlign = "center";
      ctx.fillText(item.d, x + bwid / 2, h - 8);
    });
  }

  /* =========================================================
     Community map (generated SVG)
     ========================================================= */
  var MEMBERS = [
    { n: "A. Pratama",   bpm: 152, r: 88, km: 8.4,  st: "ok" },
    { n: "R. Wulandari", bpm: 168, r: 74, km: 12.1, st: "mid" },
    { n: "B. Nugroho",   bpm: 191, r: 52, km: 15.8, st: "bad" },
    { n: "S. Handayani", bpm: 141, r: 91, km: 6.2,  st: "ok" },
    { n: "D. Kurniawan", bpm: 176, r: 68, km: 11.5, st: "mid" },
    { n: "M. Fadhil",    bpm: 149, r: 86, km: 9.0,  st: "ok" },
    { n: "L. Anggraini", bpm: 158, r: 81, km: 10.3, st: "ok" },
    { n: "T. Wijaya",    bpm: 186, r: 58, km: 14.2, st: "bad" }
  ];
  var STCOLOR = { ok: "#22c55e", mid: "#f59e0b", bad: "#ef4444" };

  function buildMap() {
    var svg = $("map-svg");
    if (!svg) return;
    var ns = "http://www.w3.org/2000/svg";
    svg.innerHTML = "";

    var line = cssVar("--line") || "rgba(0,0,0,.1)";
    var brand = cssVar("--brand-500") || "#b31e4b";

    /* grid */
    var g = doc.createElementNS(ns, "g");
    for (var x = 0; x <= 600; x += 40) {
      var v = doc.createElementNS(ns, "line");
      v.setAttribute("x1", x); v.setAttribute("y1", 0);
      v.setAttribute("x2", x); v.setAttribute("y2", 280);
      v.setAttribute("stroke", line); v.setAttribute("stroke-width", "1");
      g.appendChild(v);
    }
    for (var y = 0; y <= 280; y += 40) {
      var hl = doc.createElementNS(ns, "line");
      hl.setAttribute("x1", 0); hl.setAttribute("y1", y);
      hl.setAttribute("x2", 600); hl.setAttribute("y2", y);
      hl.setAttribute("stroke", line); hl.setAttribute("stroke-width", "1");
      g.appendChild(hl);
    }
    svg.appendChild(g);

    /* running routes */
    ["M40,210 C120,120 190,235 265,150 S400,90 470,155 S560,120 580,80",
     "M25,90 C110,55 165,150 250,95 S380,180 470,60"].forEach(function (d, i) {
      var p = doc.createElementNS(ns, "path");
      p.setAttribute("d", d);
      p.setAttribute("fill", "none");
      p.setAttribute("stroke", brand);
      p.setAttribute("stroke-width", i ? "1.6" : "2.2");
      p.setAttribute("stroke-opacity", i ? ".3" : ".45");
      p.setAttribute("stroke-dasharray", "7 6");
      svg.appendChild(p);
    });

    /* coordinator hub */
    var hub = doc.createElementNS(ns, "circle");
    hub.setAttribute("cx", 300); hub.setAttribute("cy", 140);
    hub.setAttribute("r", 9); hub.setAttribute("fill", brand);
    svg.appendChild(hub);
    var halo = doc.createElementNS(ns, "circle");
    halo.setAttribute("cx", 300); halo.setAttribute("cy", 140);
    halo.setAttribute("r", 9); halo.setAttribute("fill", "none");
    halo.setAttribute("stroke", brand); halo.setAttribute("stroke-width", "2");
    halo.innerHTML =
      '<animate attributeName="r" values="9;34" dur="2.6s" repeatCount="indefinite"/>' +
      '<animate attributeName="stroke-opacity" values="0.6;0" dur="2.6s" repeatCount="indefinite"/>';
    svg.appendChild(halo);

    /* runner dots */
    var spots = [[95,195],[160,105],[235,175],[330,95],[395,190],[455,120],[520,200],[555,75]];
    MEMBERS.forEach(function (m, i) {
      var pos = spots[i % spots.length];
      var c = doc.createElementNS(ns, "circle");
      c.setAttribute("class", "runner-dot");
      c.setAttribute("cx", pos[0]); c.setAttribute("cy", pos[1]);
      c.setAttribute("r", 7);
      c.setAttribute("fill", STCOLOR[m.st]);
      c.setAttribute("fill-opacity", ".92");
      var title = doc.createElementNS(ns, "title");
      title.textContent = m.n + " — " + m.bpm + " bpm · readiness " + m.r;
      c.appendChild(title);
      if (m.st === "bad") {
        var ring = doc.createElementNS(ns, "circle");
        ring.setAttribute("cx", pos[0]); ring.setAttribute("cy", pos[1]);
        ring.setAttribute("r", 7); ring.setAttribute("fill", "none");
        ring.setAttribute("stroke", STCOLOR.bad); ring.setAttribute("stroke-width", "2");
        ring.innerHTML =
          '<animate attributeName="r" values="7;20" dur="1.6s" repeatCount="indefinite"/>' +
          '<animate attributeName="stroke-opacity" values="0.9;0" dur="1.6s" repeatCount="indefinite"/>';
        svg.appendChild(ring);
      }
      svg.appendChild(c);
    });
  }

  function buildMembers() {
    var tb = $("member-rows");
    if (!tb) return;
    tb.innerHTML = "";
    MEMBERS.forEach(function (m) {
      var tr = doc.createElement("tr");
      var label = m.st === "ok" ? "Aman" : m.st === "mid" ? "Pantau" : "Peringatan";
      tr.innerHTML =
        "<td>" + m.n + "</td>" +
        '<td class="mono">' + m.bpm + "</td>" +
        '<td class="mono">' + m.r + "</td>" +
        '<td class="mono">' + m.km.toFixed(1) + " km</td>" +
        '<td><span class="pill ' + m.st + '">' + label + "</span></td>";
      tb.appendChild(tr);
    });
  }

  /* =========================================================
     Soft tissue + zones rendering
     ========================================================= */
  function buildTissues() {
    var box = $("tissues");
    if (!box) return;
    box.innerHTML = "";
    Object.keys(S.tissue).forEach(function (k) {
      var t = S.tissue[k];
      var el = doc.createElement("div");
      el.className = "load-item";
      el.innerHTML =
        '<div class="row"><span>' + t.label + '</span><span class="mono" id="tv-' + k + '">0%</span></div>' +
        '<div class="load-track"><div class="load-fill" id="tb-' + k + '" style="width:0%"></div></div>';
      box.appendChild(el);
    });
  }

  function buildZones() {
    var box = $("zones");
    if (!box) return;
    box.innerHTML = "";
    ZONES.forEach(function (z, i) {
      var el = doc.createElement("div");
      el.className = "zone " + z.cls;
      el.innerHTML =
        "<span>" + z.name + '</span><div class="track"><div class="fill" id="zf-' + i + '" style="width:0%"></div></div>' +
        '<span class="mono" id="zt-' + i + '" style="text-align:right">0%</span>';
      box.appendChild(el);
    });
  }

  /* =========================================================
     Readiness radar — six axes, redrawn from S.factors
     ========================================================= */
  var NS = "http://www.w3.org/2000/svg";
  var FACTORS = [
    { key: "hrv",  short: "HRV",       barTxt: "f-hrv",  bar: "fb-hrv" },
    { key: "rhr",  short: "RHR",       barTxt: "f-rhr",  bar: "fb-rhr" },
    { key: "acwr", short: "Beban",     barTxt: "f-acwr", bar: "fb-acwr" },
    { key: "rec",  short: "Pemulihan", barTxt: "f-rec",  bar: "fb-rec" },
    { key: "kin",  short: "Kinematika", barTxt: "f-kin", bar: "fb-kin" },
    { key: "fat",  short: "Kelelahan", barTxt: "f-fat",  bar: "fb-fat" }
  ];
  var RADAR = { cx: 160, cy: 148, r: 108 };

  function svgEl(name, attrs) {
    var el = doc.createElementNS(NS, name);
    Object.keys(attrs || {}).forEach(function (k) { el.setAttribute(k, attrs[k]); });
    return el;
  }

  function radarPoint(i, frac) {
    var a = -Math.PI / 2 + (i / FACTORS.length) * Math.PI * 2;
    return [RADAR.cx + Math.cos(a) * RADAR.r * frac,
            RADAR.cy + Math.sin(a) * RADAR.r * frac];
  }

  function buildRadar() {
    var svg = $("radar");
    if (!svg) return;
    svg.innerHTML = "";

    /* concentric guide rings */
    [1, 0.75, 0.5, 0.25].forEach(function (f) {
      var pts = FACTORS.map(function (_, i) {
        return radarPoint(i, f).map(function (v) { return Math.round(v * 10) / 10; }).join(",");
      }).join(" ");
      svg.appendChild(svgEl("polygon", { points: pts, class: "dg-grid" }));
    });

    /* spokes + labels */
    FACTORS.forEach(function (f, i) {
      var end = radarPoint(i, 1);
      svg.appendChild(svgEl("line", {
        x1: RADAR.cx, y1: RADAR.cy, x2: end[0], y2: end[1], class: "dg-axis"
      }));
      var lab = radarPoint(i, 1.20);
      var t = svgEl("text", {
        x: Math.round(lab[0]), y: Math.round(lab[1]),
        class: "dg-label", "text-anchor": "middle"
      });
      t.textContent = f.short;
      svg.appendChild(t);

      var v = svgEl("text", {
        x: Math.round(lab[0]), y: Math.round(lab[1]) + 13,
        class: "dg-value", "text-anchor": "middle", fill: "var(--brand-500)",
        id: "radar-v-" + f.key
      });
      v.textContent = "0";
      svg.appendChild(v);
    });

    /* the value shape, filled in by updateRadar() */
    svg.appendChild(svgEl("polygon", { points: "", class: "dg-poly", id: "radar-shape" }));
    FACTORS.forEach(function (f) {
      svg.appendChild(svgEl("circle", { r: 3.5, class: "dg-dot", id: "radar-d-" + f.key }));
    });
  }

  function updateRadar() {
    var shape = $("radar-shape");
    if (!shape) return;
    var pts = FACTORS.map(function (f, i) {
      var val = clamp(S.factors[f.key], 0, 100);
      var p = radarPoint(i, val / 100);
      var d = $("radar-d-" + f.key);
      if (d) { d.setAttribute("cx", p[0].toFixed(1)); d.setAttribute("cy", p[1].toFixed(1)); }
      var t = $("radar-v-" + f.key);
      if (t) t.textContent = Math.round(val);
      return p[0].toFixed(1) + "," + p[1].toFixed(1);
    });
    shape.setAttribute("points", pts.join(" "));
  }

  /* =========================================================
     Soft-tissue map — a schematic leg with load hotspots
     ========================================================= */
  var LEG_OUTLINE =
    "M50,24 C34,80 36,140 46,196 C36,244 42,292 50,330 L44,358 " +
    "C42,368 48,376 60,376 L116,376 C126,376 130,368 124,360 L110,334 " +
    "C96,320 84,300 82,280 C90,234 94,204 90,188 C98,136 104,80 110,26 Z";

  var HOTSPOTS = [
    /* ly: where the label sits — kept >= 34px apart so labels never stack */
    { key: "quadriceps", x: 86,  y: 104, ly: 70,  label: "Quadriceps" },
    { key: "hamstring",  x: 46,  y: 118, ly: 112, label: "Hamstring" },
    { key: "itbs",       x: 97,  y: 150, ly: 154, label: "Iliotibial band" },
    { key: "calf",       x: 54,  y: 248, ly: 248, label: "Gastrocnemius" },
    { key: "achilles",   x: 56,  y: 328, ly: 328, label: "Achilles tendon" }
  ];

  function buildLegMap() {
    var svg = $("legmap");
    if (!svg) return;
    svg.innerHTML = "";

    svg.appendChild(svgEl("path", { d: LEG_OUTLINE, class: "dg-limb" }));
    /* knee line, so the anatomy reads at a glance */
    svg.appendChild(svgEl("path", {
      d: "M44,192 C64,186 76,184 92,186",
      class: "dg-axis", fill: "none", "stroke-dasharray": "3 4"
    }));

    HOTSPOTS.forEach(function (h) {
      svg.appendChild(svgEl("line", {
        x1: h.x, y1: h.y, x2: 176, y2: h.ly,
        stroke: "var(--line)", "stroke-width": 1, "stroke-dasharray": "3 4"
      }));
      /* the halo grows and changes colour with the load */
      svg.appendChild(svgEl("circle", {
        cx: h.x, cy: h.y, r: 6, id: "hs-halo-" + h.key, opacity: ".28"
      }));
      svg.appendChild(svgEl("circle", {
        cx: h.x, cy: h.y, r: 4, id: "hs-dot-" + h.key
      }));

      var lab = svgEl("text", { x: 184, y: h.ly - 2, class: "dg-label" });
      lab.textContent = h.label;
      svg.appendChild(lab);

      var val = svgEl("text", {
        x: 184, y: h.ly + 12, class: "dg-value", id: "hs-val-" + h.key
      });
      val.textContent = "0%";
      svg.appendChild(val);
    });

    var cap = svgEl("text", { x: 0, y: 406, class: "dg-label" });
    cap.textContent = "Ukuran titik mengikuti akumulasi beban pada sesi berjalan.";
    svg.appendChild(cap);
  }

  function loadColor(v) {
    if (v >= S.thr.load) return "#ef4444";
    if (v >= S.thr.load - 15) return "#f59e0b";
    return "var(--brand-500)";
  }

  function updateLegMap() {
    HOTSPOTS.forEach(function (h) {
      var t = S.tissue[h.key];
      if (!t) return;
      var color = loadColor(t.v);
      var halo = $("hs-halo-" + h.key), dot = $("hs-dot-" + h.key), val = $("hs-val-" + h.key);
      if (halo) {
        halo.setAttribute("r", (6 + (t.v / 100) * 16).toFixed(1));
        halo.setAttribute("fill", color);
      }
      if (dot) dot.setAttribute("fill", color);
      if (val) { val.textContent = Math.round(t.v) + "%"; val.setAttribute("fill", color); }
    });
  }

  /* =========================================================
     Rendering the whole UI from state
     ========================================================= */
  function render() {
    /* live metrics */
    var zi = currentZone();
    setText("m-bpm", S.connected && S.hrOk !== false ? Math.round(S.hr) + " " : "— ", "bpm");
    setText("m-cad", S.running ? Math.round(S.cadence) + " " : "— ", "spm");
    setText("m-pace", S.running ? fmtPace(S.pace) + " " : "— ", "/km");
    var mt = $("m-time"); if (mt) mt.textContent = fmtTime(S.t);

    var mz = $("m-zone");
    if (mz) mz.textContent = S.connected ? ZONES[zi].name + " · " + ZONES[zi].tag : "Zona —";
    var cn = $("m-cad-note");
    if (cn) cn.textContent = S.running
      ? (S.cadence >= 172 ? "optimal" : "tingkatkan kadensi")
      : "menunggu data";
    var md = $("m-dist"); if (md) md.textContent = S.dist.toFixed(2).replace(".", ",") + " km";
    var mk = $("m-kcal"); if (mk) mk.textContent = Math.round(S.kcal) + " kkal";

    /* zones */
    var total = S.zoneSec.reduce(function (a, b) { return a + b; }, 0) || 1;
    for (var i = 0; i < 5; i++) {
      var pct = (S.zoneSec[i] / total) * 100;
      var f = $("zf-" + i), tx = $("zt-" + i);
      if (f) f.style.width = pct.toFixed(1) + "%";
      if (tx) tx.textContent = Math.round(pct) + "%";
    }

    /* tissue load */
    Object.keys(S.tissue).forEach(function (k) {
      var t = S.tissue[k];
      var v = $("tv-" + k), b = $("tb-" + k);
      if (v) v.textContent = Math.round(t.v) + "%";
      if (b) {
        b.style.width = clamp(t.v, 0, 100) + "%";
        b.className = "load-fill" + (t.v >= S.thr.load ? " danger" : t.v >= S.thr.load - 15 ? " warn" : "");
      }
    });

    /* readiness factors: bars and radar read the same numbers */
    FACTORS.forEach(function (f) {
      var v = clamp(S.factors[f.key], 0, 100);
      var txt = $(f.barTxt), bar = $(f.bar);
      if (txt) txt.textContent = Math.round(v);
      if (bar) {
        bar.style.width = v + "%";
        bar.className = "load-fill" + (v < 50 ? " danger" : v < 70 ? " warn" : "");
      }
    });
    updateRadar();
    updateLegMap();

    var dgBpm = $("dg-bpm");
    if (dgBpm) dgBpm.textContent = S.connected && S.hrOk !== false ? Math.round(S.hr) + " bpm" : "— bpm";

    /* readiness ring */
    var ring = $("ring-prog");
    if (ring) {
      var c = 2 * Math.PI * 50;
      ring.style.strokeDashoffset = c * (1 - clamp(S.readiness, 0, 100) / 100);
    }
    var rv = $("ready-val"); if (rv) rv.textContent = Math.round(S.readiness);
    var rl = $("ready-lbl"), rd = $("ready-desc");
    if (rl && rd) {
      if (S.readiness >= 80) { rl.textContent = "Siap latihan"; rd.textContent = "Tubuh dalam kondisi baik. Sesi tempo hingga 45 menit masih aman."; }
      else if (S.readiness >= S.thr.ready) { rl.textContent = "Cukup siap"; rd.textContent = "Pertahankan intensitas sedang. Hindari lari interval hari ini."; }
      else if (S.readiness >= 45) { rl.textContent = "Perlu pemulihan"; rd.textContent = "Turunkan volume. Prioritaskan easy run dan tidur cukup."; }
      else { rl.textContent = "Risiko tinggi"; rd.textContent = "Hentikan sesi berat. Beban jaringan lunak mendekati ambang cedera."; }
    }

    /* signal quality drifts a little with intensity */
    if (S.connected) {
      var skin = clamp(99 - S.effort * 0.05 - (S.running ? rnd(0, 1.6) : 0), 88, 99);
      var art  = clamp(98 - S.effort * 0.06 - (S.running ? rnd(0, 1.4) : 0), 86, 99);
      var conf = clamp((skin + art) / 2 + rnd(-0.6, 0.6), 85, 99);
      setBar("q-skin", "qb-skin", skin);
      setBar("q-art", "qb-art", art);
      setBar("q-conf", "qb-conf", conf);
      var sg = $("txt-signal");
      if (sg) sg.textContent = conf >= 95 ? "Sangat baik" : conf >= 90 ? "Baik" : "Sedang";
    }

    var tb = $("txt-batt"), db = $("d-batt");
    if (tb) tb.textContent = Math.round(S.battery) + "%";
    if (db) db.textContent = Math.round(S.battery) + "%";
  }

  function setText(id, main, unit) {
    var el = $(id);
    if (!el) return;
    el.innerHTML = main + (unit ? "<small>" + unit + "</small>" : "");
  }
  function setBar(txtId, barId, val) {
    var t = $(txtId), b = $(barId);
    if (t) t.textContent = Math.round(val) + "%";
    if (b) b.style.width = val + "%";
  }

  /* =========================================================
     Physiological model tick
     ========================================================= */
  function physics(dt) {
    if (S.band) return bandPhysics(dt);
    var targetHR;
    if (S.running) {
      /* cardiac drift: HR creeps up as the session goes long */
      var drift = Math.min(S.t / 60 * 0.35, 9);
      targetHR = S.restHR + (S.effort / 100) * (S.maxHR - S.restHR - 8) + drift;
    } else {
      targetHR = S.restHR + (S.connected ? rnd(0, 3) : 0);
    }
    /* first-order lag — the heart does not jump instantly */
    S.hr += (targetHR - S.hr) * clamp(dt * 0.55, 0, 1);
    S.hr += rnd(-0.5, 0.5);
    S.hr = clamp(S.hr, 45, 205);

    if (!S.running) return;

    S.t += dt;
    S.cadence = 148 + S.effort * 0.42 + Math.sin(S.t * 0.4) * 1.6;
    S.pace = clamp(9.2 - S.effort * 0.05, 3.4, 11);
    var kmPerSec = 1 / (S.pace * 60);
    S.dist += kmPerSec * dt;
    S.kcal += (0.9 + S.effort / 55) * dt;

    S.zoneSec[currentZone()] += dt;

    /* soft tissue accumulation scales with impact and intensity */
    var impact = 0.6 + Math.pow(S.effort / 100, 1.6) * 1.8;
    Object.keys(S.tissue).forEach(function (k) {
      var t = S.tissue[k];
      t.v = clamp(t.v + t.rate * impact * dt * 0.6, 0, 100);
    });

    /* readiness erodes with accumulated strain */
    var strain = (S.effort / 100) * 0.06 + (S.hr / S.maxHR > 0.9 ? 0.05 : 0);
    S.readiness = clamp(S.readiness - strain * dt, 5, 100);

    /* the underlying factors drift with the session, each at its own pace */
    var e = S.effort / 100;
    S.factors.fat = clamp(S.factors.fat - e * 0.09 * dt, 5, 100);
    S.factors.hrv = clamp(S.factors.hrv - e * 0.05 * dt, 5, 100);
    S.factors.acwr = clamp(S.factors.acwr - e * 0.07 * dt, 5, 100);
    S.factors.kin = clamp(S.factors.kin - Math.pow(e, 2) * 0.06 * dt, 5, 100);

    S.battery = clamp(S.battery - dt * 0.004, 0, 100);

    evaluateWarnings();
  }

  /* With a band connected the vitals come from its telemetry; the app keeps
     the models the band does not run (zones, soft tissue, readiness factors),
     driven by the measured heart rate instead of the effort slider. */
  function bandPhysics(dt) {
    if (S.hrOk === false) return;                  // no finger: nothing to base zones or warnings on
    S.effort = clamp((S.hr - S.restHR) / (S.maxHR - S.restHR) * 110, 0, 100);
    if (!S.running) return;
    S.zoneSec[currentZone()] += dt;
    var impact = 0.6 + Math.pow(S.effort / 100, 1.6) * 1.8;
    Object.keys(S.tissue).forEach(function (k) {
      var t = S.tissue[k];
      t.v = clamp(t.v + t.rate * impact * dt * 0.6, 0, 100);
    });
    var strain = (S.effort / 100) * 0.06 + (S.hr / S.maxHR > 0.9 ? 0.05 : 0);
    S.readiness = clamp(S.readiness - strain * dt, 5, 100);
    var e = S.effort / 100;
    S.factors.fat = clamp(S.factors.fat - e * 0.09 * dt, 5, 100);
    S.factors.hrv = clamp(S.factors.hrv - e * 0.05 * dt, 5, 100);
    S.factors.acwr = clamp(S.factors.acwr - e * 0.07 * dt, 5, 100);
    S.factors.kin = clamp(S.factors.kin - Math.pow(e, 2) * 0.06 * dt, 5, 100);
    evaluateWarnings();
  }

  /* =========================================================
     Biological Early Warning engine
     ========================================================= */
  function evaluateWarnings() {
    if (S.hr >= S.thr.hr) {
      once("hr", 45, function () {
        alertCard("danger", "Detak jantung melewati ambang",
          "HR " + Math.round(S.hr) + " bpm melebihi batas " + S.thr.hr +
          " bpm. Turunkan intensitas dan lanjutkan dengan easy pace.");
        toast("⚠ Detak jantung melewati ambang aman");
      });
    }

    Object.keys(S.tissue).forEach(function (k) {
      var t = S.tissue[k];
      if (t.v >= S.thr.load) {
        once("tis-" + k, 70, function () {
          alertCard("warn", "Beban " + t.label + " tinggi",
            "Akumulasi mencapai " + Math.round(t.v) + "%. Risiko mikro-trauma kronis " +
            "meningkat bila sesi diteruskan tanpa pemulihan.");
        });
      }
    });

    if (S.readiness < S.thr.ready) {
      once("ready", 90, function () {
        alertCard("warn", "Readiness di bawah ambang",
          "Skor kesiapan " + Math.round(S.readiness) + " di bawah " + S.thr.ready +
          ". Pertimbangkan menyudahi sesi berat hari ini.");
      });
    }

    if (currentZone() === 4) {
      once("z5", 60, function () {
        alertCard("info", "Zona 5 terdeteksi",
          "Anda berada di zona maksimal. Batasi durasi agar tidak memicu kelelahan ekstrem.");
      });
    }

    if (S.cadence >= 174 && S.t > 30) {
      once("cad", 240, function () {
        alertCard("good", "Kadensi efisien",
          "Kadensi " + Math.round(S.cadence) + " spm menurunkan beban puncak pada lutut dan ITB.");
      });
    }
  }

  /* =========================================================
     Loop
     ========================================================= */
  var last = performance.now();
  var acc = 0;
  function loop(now) {
    requestAnimationFrame(loop);
    var dt = Math.min((now - last) / 1000, 0.1);
    last = now;

    physics(dt);
    pushWave(dt);
    drawWave();

    acc += dt;
    if (acc > 0.25) { acc = 0; render(); }
  }

  /* =========================================================
     Wiring
     ========================================================= */
  function setConnected(on) {
    S.connected = on;
    var dot = $("dot-status"), txt = $("txt-status"), lbl = $("connect-label");
    if (dot) dot.classList.toggle("on", on);
    if (txt) txt.textContent = on ? "Terhubung" : "Terputus";
    if (lbl) lbl.textContent = on ? "Putuskan" : "Hubungkan";
    if (on) {
      alertCard("good", "NovaBand terhubung", "Bluetooth aktif. Streaming PPG dan IMU 6-axis dimulai.");
      toast("NovaBand terhubung via Bluetooth");
    } else {
      toast("Perangkat diputus");
    }
  }

  function setRunning(on) {
    if (S.band) window.NovaLink.send({ cmd: "run", a: on ? "start" : "pause" });
    if (on && !S.connected) { setConnected(true); }
    S.running = on;
    var lbl = $("session-label");
    if (lbl) lbl.textContent = on ? "Jeda Sesi" : (S.t > 0 ? "Lanjutkan" : "Mulai Sesi");
    var note = $("ecg-note");
    if (note) note.textContent = on ? "Merekam · Edge FFT aktif" : "Siaga · Edge FFT aktif";
    if (on) {
      alertCard("info", "Sesi dimulai", "Pemantauan real-time berjalan. Readiness awal " + Math.round(S.readiness) + ".");
      toast("Sesi latihan dimulai");
    }
  }

  function resetSession() {
    if (S.band) window.NovaLink.send({ cmd: "run", a: "stop" });
    S.running = false;
    S.t = 0; S.dist = 0; S.kcal = 0; S.zoneSec = [0, 0, 0, 0, 0];
    S.readiness = 85; S.cooldown = {};
    S.factors = { hrv: 72, rhr: 80, acwr: 65, rec: 88, kin: 91, fat: 58 };
    S.tissue.achilles.v = 41; S.tissue.itbs.v = 35; S.tissue.hamstring.v = 28;
    S.tissue.quadriceps.v = 24; S.tissue.calf.v = 31;
    var lbl = $("session-label"); if (lbl) lbl.textContent = "Mulai Sesi";
    var box = $("alerts"); if (box) box.innerHTML = "";
    render();
    toast("Sesi direset");
  }

  var btnConnect = $("btn-connect");
  if (btnConnect) btnConnect.addEventListener("click", function () {
    if (S.band) { window.NovaLink.disconnect(); return; }
    if (S.connected) { setConnected(false); return; }
    openConnect();
  });

  /* ---------------- link to the real band ---------------- */
  var dlg = $("connect-dlg");
  function openConnect() {
    if (!dlg) { setConnected(true); return; }
    var L = window.NovaLink;
    var nb = $("cx-ble"), nu = $("cx-usb");
    if (nb) nb.disabled = !(L && L.support.ble);
    if (nu) nu.disabled = !(L && L.support.usb);
    var note = $("cx-note");
    if (note) note.textContent = (L && (L.support.ble || L.support.usb)) ? "" :
      "Browser ini belum mendukung Web Bluetooth / Web Serial (mis. Safari iOS). Gunakan Chrome atau Edge, atau coba mode simulasi.";
    if (dlg.showModal) dlg.showModal(); else dlg.setAttribute("open", "");
  }
  function closeConnect() { if (dlg) { if (dlg.close) dlg.close(); else dlg.removeAttribute("open"); } }
  function linkTo(kind) {
    closeConnect();
    toast(kind === "usb" ? "Pilih port USB NovaBand…" : "Pilih NovaBand di daftar Bluetooth…");
    window.NovaLink.connect(kind).catch(function (e) {
      if (e && e.name === "NotFoundError") return;          // user closed the picker
      toast("Gagal terhubung: " + (e && e.message ? e.message : e));
    });
  }
  [["cx-ble", "ble"], ["cx-usb", "usb"]].forEach(function (b) {
    var el = $(b[0]);
    if (el) el.addEventListener("click", function () { linkTo(b[1]); });
  });
  var cxSim = $("cx-sim");
  if (cxSim) cxSim.addEventListener("click", function () { closeConnect(); setConnected(true); });
  var cxClose = $("cx-close");
  if (cxClose) cxClose.addEventListener("click", closeConnect);

  if (window.NovaLink) {
    var L = window.NovaLink;
    L.on("status", function (st) {
      var was = S.band;
      S.band = st.connected;
      S.connected = st.connected;
      var dot = $("dot-status"), txt = $("txt-status"), lbl = $("connect-label");
      if (dot) dot.classList.toggle("on", st.connected);
      if (txt) txt.textContent = st.connected ? (st.transport === "usb" ? "Band · USB" : "Band · Bluetooth") : "Terputus";
      if (lbl) lbl.textContent = st.connected ? "Putuskan" : "Hubungkan";
      var dn = $("band-name"), dt = $("band-transport"), df = $("band-fw");
      if (dn) dn.textContent = st.connected ? (st.name || "NovaBand") : "—";
      if (dt) dt.textContent = st.connected ? (st.transport === "usb" ? "USB · Web Serial" : "Bluetooth LE · Web Bluetooth") : "Belum terhubung";
      if (df) df.textContent = st.fw || "—";
      doc.body.classList.toggle("band-live", st.connected);
      if (st.connected && !was) {
        wave.length = 0;
        alertCard("good", "NovaBand terhubung", "Data langsung dari band via " + (st.transport === "usb" ? "USB." : "Bluetooth LE."));
        toast("NovaBand terhubung");
      } else if (!st.connected && was) {
        S.running = false;
        var sl = $("session-label"); if (sl) sl.textContent = S.t > 0 ? "Lanjutkan" : "Mulai Sesi";
        toast("NovaBand terputus");
      }
      render();
    });
    L.on("telemetry", function (m) {
      S.hrOk = m.hok !== 0;                            // false = no finger on the PPG sensor
      if (S.hrOk) S.hr = m.hr;
      if (m.sok !== 0) S.spo2 = m.sp;
      S.cadence = m.cad;
      S.temp = m.tok ? m.tmp : 0;
      S.spo2Ok = m.sok !== 0;
      S.pace = m.pace > 0 ? m.pace / 60 : 0;           // band: s/km, app: min/km
      S.dist = m.dist; S.kcal = m.kcal; S.battery = m.bat; S.bandDemo = !!m.demo;
      if (m.run) S.t = m.sec;
      S.steps = m.stp || 0;
      var se = $("m-steps"); if (se) se.textContent = S.steps.toLocaleString("id-ID") + " langkah";
      recordTick(m);
      var run = !!m.run && !m.pz;
      if (run !== S.running) {                         // started / paused on the band itself
        S.running = run;
        var lbl = $("session-label");
        if (lbl) lbl.textContent = run ? "Jeda Sesi" : (S.t > 0 ? "Lanjutkan" : "Mulai Sesi");
      }
      var bd = $("band-data");
      if (bd) bd.textContent = m.demo ? "Simulasi di band (belum ada sensor PPG)" : "Sensor asli · MAX30102 · MLX90614 · MPU6050";
      var bt = $("band-temp"); if (bt) bt.textContent = S.temp > 0 ? S.temp.toFixed(1).replace(".", ",") + " °C" : "—";
      var bs = $("band-spo2"); if (bs) bs.textContent = S.spo2Ok && m.sp > 0 ? Math.round(m.sp) + " %" : "—";
      var bh = $("band-hr"); if (bh) bh.textContent = S.hrOk ? Math.round(m.hr) + " bpm" : "Letakkan jari di sensor";
    });
    L.on("wave", function (samples) {
      samples.forEach(function (v) { wave.push(v); if (wave.length > WAVE_LEN) wave.shift(); });
    });
  }


  /* ---------------- activity recorder (Strava-style log of a band run) ---------------- */
  var ACT_KEY = "nova.activities", rec = null;
  function loadActs() { try { return JSON.parse(localStorage.getItem(ACT_KEY)) || []; } catch (e) { return []; } }
  function recordTick(m) {
    if (m.run && !rec) rec = { start: Date.now(), s: [], lastSec: -1 };
    if (rec && m.run && !m.pz && m.sec !== rec.lastSec) {      // one sample per second of running time
      rec.lastSec = m.sec;
      rec.s.push([m.sec, m.hok === 0 ? 0 : m.hr, +m.dist.toFixed(3), m.stp || 0, m.cad || 0, m.kcal || 0]);
    }
    if (rec && !m.run) { saveActivity(); rec = null; }
  }
  function saveActivity() {
    var s = rec.s; if (s.length < 10) return;
    var last = s[s.length - 1], hrs = s.map(function (x) { return x[1]; }).filter(Boolean);
    var splits = [], kmMark = 0, tMark = 0;
    s.forEach(function (x) { if (x[2] >= kmMark + 1) { splits.push(Math.round(x[0] - tMark)); tMark = x[0]; kmMark += 1; } });
    var acts = loadActs();
    acts.unshift({ at: rec.start, sec: last[0], dist: last[2], steps: last[3], kcal: Math.round(last[5]),
      hrAvg: hrs.length ? Math.round(hrs.reduce(function (a, b) { return a + b; }, 0) / hrs.length) : 0,
      hrMax: hrs.length ? Math.max.apply(null, hrs) : 0, splits: splits,
      hr: s.filter(function (x, i) { return i % Math.max(1, Math.floor(s.length / 60)) === 0; }).map(function (x) { return x[1]; }),
      series: s.filter(function (x, i) { return i % Math.max(1, Math.ceil(s.length / 300)) === 0; }),   // [sec, hr, km, steps, cad, kcal]
      cloud: false });
    putActs(acts.slice(0, 30));
    renderActs(); toast("Aktivitas tersimpan"); syncActs();
  }
  function putActs(a) { try { localStorage.setItem(ACT_KEY, JSON.stringify(a)); } catch (e) {} }
  /* Push every session that is not in Firebase yet; failures (offline, rules) are retried later. */
  var syncing = false;
  function syncActs() {
    if (syncing || !window.NovaCloud) return;
    var todo = loadActs().filter(function (a) { return !a.cloud; });
    if (!todo.length) return;
    syncing = true;
    var chain = Promise.resolve();
    todo.forEach(function (a) {
      chain = chain.then(function () {
        var d = {}; Object.keys(a).forEach(function (k) { if (k !== "cloud") d[k] = a[k]; });
        d.savedAt = Date.now(); d.source = "novaband";
        return window.NovaCloud.saveSession(a.at, d).then(function () {
          var all = loadActs(); all.forEach(function (x) { if (x.at === a.at) x.cloud = true; });
          putActs(all); renderActs();
        });
      });
    });
    chain.then(function () { toast("Sesi tersimpan ke Firebase"); })
      .catch(function (e) { console.warn("[NovaBand] sync gagal:", e && e.message); })
      .then(function () { syncing = false; });
  }
  doc.addEventListener("novaband:cloud-ready", syncActs);
  window.addEventListener("online", syncActs);
  setInterval(syncActs, 60000);
  function renderActs() {
    var box = $("act-list"); if (!box) return;
    var acts = loadActs();
    if (!acts.length) { box.innerHTML = '<p class="tile-note">Belum ada lari tersimpan. Mulai lari dengan NovaBand, lalu stop untuk menyimpan.</p>'; return; }
    box.innerHTML = acts.map(function (a) {
      var pace = a.dist > 0.05 ? a.sec / a.dist / 60 : 0, d = new Date(a.at);
      var mx = Math.max.apply(null, a.hr.concat([1])), mn = Math.min.apply(null, a.hr.filter(Boolean).concat([mx]));
      var pts = a.hr.map(function (v, i) { return (i * 200 / Math.max(1, a.hr.length - 1)).toFixed(1) + "," + (38 - (v - mn) / Math.max(1, mx - mn) * 34).toFixed(1); }).join(" ");
      return '<div class="tile" style="margin-bottom:10px"><div class="tile-head"><div class="tile-title">' +
        d.toLocaleDateString("id-ID", { weekday: "long", day: "numeric", month: "short" }) + " · " +
        d.toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" }) + '</div><div class="tile-note">' + fmtTime(a.sec) + '</div></div>' +
        '<div class="row" style="gap:18px;flex-wrap:wrap"><b class="mono">' + a.dist.toFixed(2).replace(".", ",") + ' km</b><span>' +
        (pace ? fmtPace(pace) + " /km" : "—") + '</span><span>' + a.steps.toLocaleString("id-ID") + ' langkah</span><span>' + a.kcal + ' kkal</span><span>HR ' +
        a.hrAvg + '/' + a.hrMax + '</span><span class="tile-note">' + (a.cloud ? '☁ tersinkron' : 'belum tersinkron') + '</span></div><svg viewBox="0 0 200 42" width="100%" height="42" preserveAspectRatio="none" aria-label="Grafik detak jantung"><polyline fill="none" stroke="currentColor" stroke-width="1.5" points="' + pts + '"/></svg>' +
        (a.splits.length ? '<div class="tile-note">Split: ' + a.splits.map(function (x, i) { return (i + 1) + "km " + fmtTime(x); }).join(" · ") + '</div>' : "") + '</div>';
    }).join("");
  }
  renderActs(); syncActs();

  /* band controls in the Perangkat panel */
  var bmSend = $("band-msg-send"), bmText = $("band-msg");
  if (bmSend && bmText) bmSend.addEventListener("click", function () {
    var t = bmText.value.trim();
    if (!t || !S.band) { toast(S.band ? "Tulis pesan dulu" : "Hubungkan NovaBand dulu"); return; }
    window.NovaLink.send({ cmd: "msg", text: t.slice(0, 40), level: "info" }).then(function () { toast("Pesan terkirim ke layar band"); bmText.value = ""; });
  });
  var bBright = $("band-bright");
  if (bBright) bBright.addEventListener("change", function () {
    if (S.band) window.NovaLink.send({ cmd: "bright", v: parseInt(bBright.value, 10) });
  });
  doc.querySelectorAll("[data-band-page]").forEach(function (b) {
    b.addEventListener("click", function () {
      if (S.band) window.NovaLink.send({ cmd: "page", i: parseInt(b.dataset.bandPage, 10) });
      else toast("Hubungkan NovaBand dulu");
    });
  });

  var btnSession = $("btn-session");
  if (btnSession) btnSession.addEventListener("click", function () { setRunning(!S.running); });

  var btnReset = $("btn-reset");
  if (btnReset) btnReset.addEventListener("click", resetSession);

  var btnClear = $("btn-clear-alerts");
  if (btnClear) btnClear.addEventListener("click", function () {
    var box = $("alerts"); if (box) box.innerHTML = "";
    S.cooldown = {};
  });

  var effort = $("effort");
  if (effort) {
    effort.addEventListener("input", function () {
      S.effort = parseInt(effort.value, 10);
      var v = $("eff-val"); if (v) v.textContent = S.effort;
    });
  }
  doc.querySelectorAll("[data-preset]").forEach(function (b) {
    b.addEventListener("click", function () {
      S.effort = parseInt(b.dataset.preset, 10);
      if (effort) effort.value = S.effort;
      var v = $("eff-val"); if (v) v.textContent = S.effort;
      toast("Intensitas diatur ke " + b.textContent.trim());
    });
  });

  /* threshold sliders */
  [["thr-hr", "thr-hr-val", "hr", " bpm"],
   ["thr-load", "thr-load-val", "load", "%"],
   ["thr-ready", "thr-ready-val", "ready", ""]].forEach(function (cfg) {
    var input = $(cfg[0]), out = $(cfg[1]);
    if (!input) return;
    input.addEventListener("input", function () {
      var val = parseInt(input.value, 10);
      S.thr[cfg[2]] = val;
      if (out) out.textContent = val + cfg[3];
      if (cfg[2] === "hr" && S.band) window.NovaLink.send({ cmd: "alert", hr: val });
      render();
    });
  });

  var btnCalib = $("btn-calib");
  if (btnCalib) btnCalib.addEventListener("click", function () {
    toast("Kalibrasi sensor selesai · offset diperbarui");
    alertCard("good", "Kalibrasi selesai", "Baseline PPG dan IMU disetel ulang untuk posisi lengan atas saat ini.");
  });
  var btnSync = $("btn-sync");
  if (btnSync) btnSync.addEventListener("click", function () {
    toast("Data sesi disinkronkan ke dashboard komunitas");
    alertCard("info", "Sinkronisasi cloud", "Riwayat sesi dikirim ke Community Based Analysis Health Management.");
  });

  /* panel switching */
  doc.querySelectorAll(".side-item").forEach(function (btn) {
    btn.addEventListener("click", function () {
      doc.querySelectorAll(".side-item").forEach(function (b) { b.classList.remove("active"); });
      doc.querySelectorAll(".panel").forEach(function (p) { p.classList.remove("active"); });
      btn.classList.add("active");
      var panel = $(btn.dataset.panel);
      if (panel) panel.classList.add("active");
      if (btn.dataset.panel === "p-ready") drawWeek();
      if (btn.dataset.panel === "p-comm") buildMap();
      sizeCanvas(ecg);
    });
  });

  /* advice cards */
  (function advice() {
    var box = $("advice");
    if (!box) return;
    [["good", "Easy run 40 menit", "Zona 2 dominan, jaga HR di bawah 140 bpm untuk membangun basis aerobik."],
     ["info", "Mobility 15 menit", "Fokus pada hip flexor dan calf untuk menurunkan tegangan iliotibial band."],
     ["warn", "Tunda sesi interval", "Rasio beban akut:kronis masih tinggi — jadwalkan ulang 48 jam ke depan."]]
      .forEach(function (a) {
        var el = doc.createElement("div");
        el.className = "alert " + a[0];
        el.innerHTML = '<div class="ic">' + (a[0] === "good" ? "✓" : a[0] === "warn" ? "!" : "i") + "</div>" +
          "<div><strong></strong><p></p></div>";
        el.querySelector("strong").textContent = a[1];
        el.querySelector("p").textContent = a[2];
        box.appendChild(el);
      });
  })();

  /* app.html#device (the QR code on the band's screen) opens Perangkat */
  if (location.hash === "#device") {
    var devBtn = doc.querySelector('.side-item[data-panel="p-device"]');
    if (devBtn) setTimeout(function () { devBtn.click(); }, 0);
    // scanning the band's QR = "connect me": open the picker right away (the browser still needs one tap on Bluetooth)
    setTimeout(function () { if (!S.band && !S.connected) openConnect(); }, 400);
  }

  /* date */
  var td = $("today-date");
  if (td) {
    td.textContent = new Date().toLocaleDateString("id-ID", {
      weekday: "long", day: "numeric", month: "long", year: "numeric"
    });
  }

  /* theme + resize redraws */
  doc.addEventListener("novaband:theme", function () {
    drawWeek(); buildMap(); drawWave();
    buildRadar(); buildLegMap(); updateRadar(); updateLegMap();
  });
  window.addEventListener("resize", function () {
    sizeCanvas(ecg); drawWeek();
  });

  /* boot */
  buildZones();
  buildTissues();
  buildRadar();
  buildLegMap();
  buildMembers();
  buildMap();
  sizeCanvas(ecg);
  drawWeek();
  render();

  var appBg = $("app-bg");
  if (appBg && window.NovaThree) window.NovaThree.initAppBg(appBg);

  requestAnimationFrame(loop);
})();
