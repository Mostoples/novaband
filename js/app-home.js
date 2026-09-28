/* ============================================================
   Nova-Band — Beranda widgets (the home screen from the deck mockup)
   Reads the live simulation state exposed by js/app.js
   (window.NovaState) so the day totals grow while a session runs.
   ============================================================ */
(function () {
  "use strict";

  var doc = document;
  var $ = function (id) { return doc.getElementById(id); };
  var S = window.NovaState || null;

  /* the day before the demo session starts — the numbers in the mockup */
  var DAY = { steps: 8500, kcal: 450, dist: 6.21, actMin: 52 };
  var GOAL = { steps: 10000, kcal: 600, dist: 8, actMin: 60 };
  var STRIDE_M = 1.1;

  function cssVar(n) { return getComputedStyle(doc.documentElement).getPropertyValue(n).trim(); }
  function id(n) { return n.toLocaleString("id-ID"); }

  /* ---------- 24-hour heart-rate curve ----------
     Deterministic shape: low at night, a morning run, an active
     afternoon and an evening walk — sampled every 15 minutes. */
  var HR = (function () {
    var out = [], seed = 7;
    function rnd() { seed = (seed * 16807) % 2147483647; return seed / 2147483647; }
    for (var i = 0; i <= 96; i++) {
      var h = i / 4;
      var v = 58 + 6 * Math.sin((h - 3) / 24 * Math.PI * 2 - Math.PI / 2) + 6;
      if (h > 7 && h < 22) v += 16;                                 // awake
      v += 78 * Math.exp(-Math.pow((h - 6.5) / 0.45, 2));           // morning run
      v += 30 * Math.exp(-Math.pow((h - 12.2) / 0.5, 2));           // lunch errands
      v += 22 * Math.exp(-Math.pow((h - 18.4) / 0.6, 2));           // evening walk
      v += (rnd() - 0.5) * 9;
      out.push(Math.round(v));
    }
    return out;
  })();

  function sizeCanvas(c) {
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    c.width = Math.max(1, Math.round(c.clientWidth * dpr));
    c.height = Math.max(1, Math.round(c.clientHeight * dpr));
    var ctx = c.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    return ctx;
  }

  function drawHR24() {
    var c = $("hr24");
    if (!c || !c.clientWidth) return;
    var ctx = sizeCanvas(c);
    var w = c.clientWidth, h = c.clientHeight;
    var L = 30, R = 8, T = 22, B = 22;
    var red = cssVar("--red") || "#7b2021";
    var line = cssVar("--line") || "#eee";
    var ink3 = cssVar("--ink-3") || "#999";
    var lo = 40, hi = 190;
    var X = function (i) { return L + (w - L - R) * i / (HR.length - 1); };
    var Y = function (v) { return T + (h - T - B) * (1 - (v - lo) / (hi - lo)); };

    ctx.font = "10px Poppins, system-ui, sans-serif";
    ctx.fillStyle = ink3;
    ctx.strokeStyle = line;
    ctx.lineWidth = 1;
    [60, 120, 180].forEach(function (v) {
      ctx.beginPath(); ctx.moveTo(L, Y(v) + .5); ctx.lineTo(w - R, Y(v) + .5); ctx.stroke();
      ctx.textAlign = "right"; ctx.fillText(v, L - 6, Y(v) + 3);
    });
    ctx.textAlign = "center";
    ["00:00", "06:00", "12:00", "18:00", "24:00"].forEach(function (t, k) {
      ctx.fillText(t, X(k * 24), h - 6);
    });

    /* live heart rate replaces the sample for "now" once the band is connected */
    var now = new Date();
    var idxNow = Math.min(96, Math.round((now.getHours() * 60 + now.getMinutes()) / 15));
    var data = HR.slice();
    if (S && S.connected) data[idxNow] = Math.round(S.hr);

    var grad = ctx.createLinearGradient(0, T, 0, h - B);
    grad.addColorStop(0, "rgba(123,32,33,.28)");
    grad.addColorStop(1, "rgba(123,32,33,0)");
    ctx.beginPath();
    ctx.moveTo(X(0), Y(lo));
    for (var i = 0; i <= idxNow; i++) ctx.lineTo(X(i), Y(data[i]));
    ctx.lineTo(X(idxNow), Y(lo));
    ctx.closePath();
    ctx.fillStyle = grad;
    ctx.fill();

    ctx.beginPath();
    for (var j = 0; j <= idxNow; j++) { if (j) ctx.lineTo(X(j), Y(data[j])); else ctx.moveTo(X(j), Y(data[j])); }
    ctx.strokeStyle = red; ctx.lineWidth = 2; ctx.lineJoin = "round"; ctx.stroke();

    /* the rest of the day, still to come */
    ctx.setLineDash([3, 4]);
    ctx.beginPath();
    for (var k = idxNow; k < data.length; k++) { if (k > idxNow) ctx.lineTo(X(k), Y(data[k])); else ctx.moveTo(X(k), Y(data[k])); }
    ctx.strokeStyle = line; ctx.lineWidth = 1.5; ctx.stroke();
    ctx.setLineDash([]);

    /* peak marker, like the "148 BPM" tag on the mockup */
    var peak = 0;
    for (var p = 1; p <= idxNow; p++) if (data[p] > data[peak]) peak = p;
    var px = X(peak), py = Y(data[peak]);
    ctx.beginPath(); ctx.moveTo(px, py); ctx.lineTo(px, h - B); ctx.strokeStyle = red; ctx.globalAlpha = .35; ctx.stroke(); ctx.globalAlpha = 1;
    ctx.beginPath(); ctx.arc(px, py, 4, 0, Math.PI * 2); ctx.fillStyle = "#fff"; ctx.fill();
    ctx.lineWidth = 2; ctx.strokeStyle = red; ctx.stroke();
    var tag = data[peak] + " BPM";
    ctx.font = "600 10.5px Poppins, system-ui, sans-serif";
    var tw = ctx.measureText(tag).width + 14;
    var tx = Math.min(Math.max(px - tw / 2, L), w - R - tw);
    ctx.fillStyle = red;
    ctx.beginPath();
    if (ctx.roundRect) ctx.roundRect(tx, py - 26, tw, 18, 6); else ctx.rect(tx, py - 26, tw, 18);
    ctx.fill();
    ctx.fillStyle = "#fff"; ctx.textAlign = "center"; ctx.fillText(tag, tx + tw / 2, py - 13);

    var sum = 0;
    for (var a = 0; a <= idxNow; a++) sum += data[a];
    var avg = $("hr24-avg");
    if (avg) avg.textContent = "Rata-rata " + Math.round(sum / (idxNow + 1)) + " BPM";
  }

  /* ---------- day totals, activity ring, battery, insight ---------- */
  function update() {
    var dist = DAY.dist + (S ? S.dist : 0);
    var steps = Math.round(DAY.steps + (S ? S.dist * 1000 / STRIDE_M : 0));
    var kcal = Math.round(DAY.kcal + (S ? S.kcal : 0));
    var mins = Math.round(DAY.actMin + (S ? S.t / 60 : 0));

    var set = function (k, v) { var el = $(k); if (el) el.textContent = v; };
    var bar = function (k, v, g) { var el = $(k); if (el) el.style.width = Math.min(100, v / g * 100) + "%"; };
    set("h-steps", id(steps));
    set("h-kcal", id(kcal));
    set("h-dist", dist.toFixed(2).replace(".", ","));
    bar("h-steps-bar", steps, GOAL.steps);
    bar("h-kcal-bar", kcal, GOAL.kcal);
    bar("h-dist-bar", dist, GOAL.dist);

    set("act-min", mins);
    var ring = $("act-ring");
    if (ring) ring.style.strokeDashoffset = 263.9 * (1 - Math.min(mins / GOAL.actMin, 1));

    if (S) {
      var b = Math.round(S.battery);
      set("home-batt", b + "%");
      var bb = $("home-batt-bar"); if (bb) bb.style.setProperty("--lvl", b + "%");

      var tip;
      if (S.running && S.readiness < S.thr.ready) tip = "Readiness turun di bawah ambang. Sudahi sesi berat dan lanjutkan dengan pendinginan.";
      else if (S.running) tip = "Sesi berjalan. Jaga kadensi di atas 172 spm untuk mengurangi beban puncak di lutut.";
      else if (steps >= GOAL.steps) tip = "Target langkah hari ini tercapai. Waktunya pemulihan — tidur cukup malam ini.";
      else tip = "Kamu aktif pagi ini. Pertahankan konsistensimu untuk mencapai target mingguan.";
      set("insight-text", tip);
    }
  }

  /* ---------- shortcuts on the home cards jump to other panels ---------- */
  doc.addEventListener("click", function (e) {
    var t = e.target.closest("[data-goto]");
    if (!t) return;
    e.preventDefault();
    var tab = doc.querySelector('.side-item[data-panel="' + t.dataset.goto + '"]');
    if (tab) { tab.click(); window.scrollTo({ top: 0, behavior: "smooth" }); }
  });
  doc.querySelectorAll('.side-item[data-panel="p-home"]').forEach(function (b) {
    b.addEventListener("click", function () { setTimeout(drawHR24, 30); });
  });

  var sync = $("home-sync");
  if (sync) {
    var d = new Date(Date.now() - 42 * 60000);
    sync.textContent = "Terakhir sinkron: Hari ini, " +
      String(d.getHours()).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0");
  }

  window.addEventListener("resize", drawHR24);
  doc.addEventListener("novaband:theme", drawHR24);
  drawHR24();
  update();
  setInterval(function () { update(); if (S && S.connected) drawHR24(); }, 1000);
})();
