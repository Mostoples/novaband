/* ============================================================
   Nova-Band — immersive layer for the app
   - starfield with three depth layers (parallax on pointer/scroll)
   - glass tiles tilt toward the pointer (sets --rx --ry --mx --my)
   - Nova the mascot reacts to the live state in window.NovaState:
     waves hello, runs with you, warns on a heart-rate alert,
     cheers when a session ends, gives a thumbs-up when you are ready.
   Clips: assets/mascot/nova-<clip>.webp (animated, transparent),
   rendered by blender/mascot_anim.py.
   ============================================================ */
(function () {
  "use strict";

  var doc = document;
  var S = window.NovaState || null;
  var still = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var finePointer = window.matchMedia && window.matchMedia("(hover: hover) and (pointer: fine)").matches;

  /* ---------- starfield ---------- */
  var cv = doc.getElementById("fx-stars");
  var px = 0, py = 0, tx = 0, ty = 0;
  if (cv && !still) {
    var ctx = cv.getContext("2d");
    var stars = [];
    var size = function () {
      var dpr = Math.min(window.devicePixelRatio || 1, 2);
      cv.width = innerWidth * dpr; cv.height = innerHeight * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      stars = [];
      var n = Math.round(Math.min(160, innerWidth * innerHeight / 9000));
      for (var i = 0; i < n; i++) {
        stars.push({ x: Math.random() * innerWidth, y: Math.random() * innerHeight, z: [0.25, 0.55, 1][i % 3],
                     r: Math.random() * 1.2 + 0.3, tw: Math.random() * 6.28 });
      }
    };
    size();
    addEventListener("resize", size);
    addEventListener("pointermove", function (e) { tx = e.clientX / innerWidth - 0.5; ty = e.clientY / innerHeight - 0.5; }, { passive: true });
    var t0 = performance.now();
    var frame = function (now) {
      if (!doc.hidden) {
        var t = (now - t0) / 1000;
        px += (tx - px) * 0.05; py += (ty - py) * 0.05;
        var sy = scrollY;
        var dark = doc.documentElement.getAttribute("data-theme") !== "light";
        ctx.clearRect(0, 0, innerWidth, innerHeight);
        for (var i = 0; i < stars.length; i++) {
          var s = stars[i];
          var x = (s.x - px * 40 * s.z + innerWidth) % innerWidth;
          var y = ((s.y - py * 30 * s.z - sy * 0.15 * s.z) % innerHeight + innerHeight) % innerHeight;
          var a = (0.35 + 0.65 * s.z) * (0.6 + 0.4 * Math.sin(t * 1.6 + s.tw));
          ctx.fillStyle = dark ? "rgba(255," + (190 + 50 * s.z | 0) + ",200," + a.toFixed(3) + ")"
                               : "rgba(150,40,60," + (a * 0.45).toFixed(3) + ")";
          ctx.beginPath(); ctx.arc(x, y, s.r * (0.6 + s.z), 0, 6.283); ctx.fill();
        }
      }
      requestAnimationFrame(frame);
    };
    requestAnimationFrame(frame);
  }

  /* ---------- HUD corners + sheen ---------- */
  doc.querySelectorAll(".app-shell .tile").forEach(function (el) {
    var h = doc.createElement("span");
    h.className = "hud"; h.setAttribute("aria-hidden", "true");
    h.innerHTML = "<i></i><i></i><i></i><i></i>";
    el.appendChild(h);
  });
  doc.querySelectorAll(".dev-card, .rail .tile:first-child, .nova-hero").forEach(function (el) {
    var s = doc.createElement("span");
    s.className = "sheen"; s.setAttribute("aria-hidden", "true");
    el.appendChild(s);
  });

  /* ---------- 3D tilt toward the pointer ---------- */
  if (finePointer && !still) {
    var MAX = 7;
    doc.addEventListener("pointermove", function (e) {
      var el = e.target.closest && e.target.closest(".tile, .metric, .nova-hero");
      if (!el || el.closest(".side")) return;
      var r = el.getBoundingClientRect();
      var u = (e.clientX - r.left) / r.width, v = (e.clientY - r.top) / r.height;
      var k = el.classList.contains("nova-hero") ? 0.5 : 1;
      el.style.setProperty("--ry", ((u - 0.5) * 2 * MAX * k).toFixed(2) + "deg");
      el.style.setProperty("--rx", (-(v - 0.5) * 2 * MAX * k).toFixed(2) + "deg");
      el.style.setProperty("--mx", (u * 100).toFixed(1) + "%");
      el.style.setProperty("--my", (v * 100).toFixed(1) + "%");
      el.classList.add("is-tilting");
    }, { passive: true });
    doc.addEventListener("pointerout", function (e) {
      var el = e.target.closest && e.target.closest(".tile, .metric, .nova-hero");
      if (!el || (e.relatedTarget && el.contains(e.relatedTarget))) return;
      el.style.setProperty("--rx", "0deg"); el.style.setProperty("--ry", "0deg");
      el.classList.remove("is-tilting");
    });
  }

  /* ---------- Nova ---------- */
  /* Transparent VP9 WebM (~120 KB a clip) where alpha video works; Safari
     cannot draw VP9 alpha, so it keeps the <img> with an animated WebP. */
  var ua = navigator.userAgent;
  var isSafari = /safari/i.test(ua) && !/chrome|chromium|crios|edg|android|firefox|fxios/i.test(ua);
  var probe = doc.createElement("video");
  var useVideo = !isSafari && !!probe.canPlayType && probe.canPlayType('video/webm; codecs="vp9"') !== "";
  var src = function (c) { return "assets/mascot/nova-" + c + (useVideo ? ".webm" : ".webp"); };

  if (useVideo) {
    doc.querySelectorAll("img.nova-sprite").forEach(function (img) {
      var v = doc.createElement("video");
      v.className = img.className;
      v.dataset.nova = img.dataset.nova;
      v.muted = true; v.loop = true; v.playsInline = true; v.autoplay = !still;
      v.setAttribute("muted", ""); v.setAttribute("playsinline", ""); v.setAttribute("aria-hidden", "true");
      v.preload = "auto";
      img.replaceWith(v);
    });
  }

  function show(el, clip) {
    if (!el || el.dataset.clip === clip) return;
    var first = !el.dataset.clip;
    el.dataset.clip = clip;
    if (first) { el.src = src(clip); return; }
    el.style.opacity = "0";
    setTimeout(function () {
      el.src = src(clip);
      if (el.play && !still) el.play().catch(function () {});
      el.style.opacity = "1";
    }, 180);
  }

  var born = Date.now();
  var alertUntil = 0, cheerUntil = 0, wasRunning = false;
  var alerts = doc.getElementById("alerts");
  if (alerts && "MutationObserver" in window) {
    new MutationObserver(function (list) {
      list.forEach(function (m) {
        m.addedNodes.forEach(function (n) {
          if (n.classList && n.classList.contains("danger")) alertUntil = Date.now() + 8000;
        });
      });
    }).observe(alerts, { childList: true });
  }

  function zone(hr) {
    var p = hr / ((S && S.maxHR) || 195);
    return p < 0.6 ? 1 : p < 0.7 ? 2 : p < 0.8 ? 3 : p < 0.9 ? 4 : 5;
  }
  function mmss(sec) { sec = Math.round(sec); return Math.floor(sec / 60) + ":" + String(sec % 60).padStart(2, "0"); }

  function mood() {
    var now = Date.now();
    var running = S ? S.running : false;
    if (wasRunning && !running && S && S.t > 5) cheerUntil = now + 6000;
    wasRunning = running;
    if (now < alertUntil) return "alert";
    if (now < cheerUntil) return "cheer";
    if (running) return "run";
    if (now - born < 4200) return "wave";
    return "idle";
  }

  function line(m) {
    var hr = S ? Math.round(S.hr) : 68;
    var ready = S ? Math.round(S.readiness) : 85;
    switch (m) {
      case "alert": return "Pelan dulu! Detak jantungmu <b>" + hr + " bpm</b>, melewati ambang <b>" + (S ? S.thr.hr : 185) + " bpm</b>. Turunkan intensitas dan atur napas.";
      case "cheer": return "Sesi selesai! <b>" + (S ? S.dist.toFixed(2).replace(".", ",") : "0") + " km</b> dalam " + (S ? mmss(S.t) : "0:00") + ". Kerja bagus, sekarang pendinginan ya.";
      case "run": return "Ayo terus! <b>" + hr + " bpm</b> · Zona " + zone(hr) + ". Jaga kadensi di atas 170 spm.";
      case "wave": return "Hai, aku <b>Nova</b>! " + (S && S.connected ? "Band kamu sudah tersambung." : "Tekan <b>Hubungkan</b> untuk menyambungkan band.") + " Readiness hari ini <b>" + ready + "</b>.";
      default: return (ready >= (S ? S.thr.ready : 70)
        ? "Readiness <b>" + ready + "</b>, tubuhmu siap. Sesi tempo 45 menit masih aman."
        : "Readiness <b>" + ready + "</b>. Hari ini pemulihan dulu ya, lari santai saja.");
    }
  }

  var say = doc.getElementById("nova-say");
  var coach = doc.getElementById("nova-coach");
  var lastMood = "", typing = null;
  function type(el, html) {
    if (!el) return;
    if (still) { el.innerHTML = html; return; }
    clearInterval(typing);
    var plain = html.replace(/<[^>]+>/g, "");
    var i = 0;
    typing = setInterval(function () {
      i += 2;
      if (i >= plain.length) { clearInterval(typing); typing = null; el.innerHTML = html; return; }
      el.innerHTML = plain.slice(0, i) + '<span class="caret"></span>';
    }, 22);
  }

  function tick() {
    var m = mood();
    var heroImgs = doc.querySelectorAll('[data-nova="hero"]');
    heroImgs.forEach(function (img) { show(img, m); });
    show(doc.querySelector('[data-nova="coach"]'), m === "wave" || m === "cheer" ? (m === "cheer" ? "cheer" : "idle") : m);
    var ready = S ? S.readiness >= S.thr.ready : true;
    show(doc.querySelector('[data-nova="ready"]'), ready ? "thumbs" : "alert");
    show(doc.querySelector('[data-nova="insight"]'), "talk");
    show(doc.querySelector('[data-nova="device"]'), "flex");
    show(doc.querySelector('[data-nova="dialog"]'), "wave");

    var text = line(m);
    if (m !== lastMood) { type(say, text); lastMood = m; }
    else if (!typing && say && (m === "run" || m === "alert")) say.innerHTML = text;
    if (coach && (S && (S.running || m === "alert" || m === "cheer"))) coach.innerHTML = text;
    doc.body.classList.toggle("nova-alert", m === "alert");
  }
  tick();
  setInterval(tick, 1000);
})();
