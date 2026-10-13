/* ============================================================
   Nova-Band — shared site behaviour
   Theme, navigation, scroll reveal, counters, meters, BEP chart,
   showreel, and the Three.js scenes.
   ============================================================ */
(function () {
  "use strict";

  var doc = document;
  var root = doc.documentElement;

  /* ---------- Theme (light is the design; dark is opt-in) ---------- */
  var Theme = {
    KEY: "novaband-theme",
    get: function () { return root.getAttribute("data-theme") || "light"; },
    set: function (mode) {
      root.setAttribute("data-theme", mode);
      try { localStorage.setItem(Theme.KEY, mode); } catch (e) {}
      var meta = doc.querySelector('meta[name="theme-color"]');
      if (meta) meta.setAttribute("content", mode === "dark" ? "#120c0e" : "#ffffff");
      doc.dispatchEvent(new CustomEvent("novaband:theme", { detail: { mode: mode } }));
    },
    toggle: function () { Theme.set(Theme.get() === "dark" ? "light" : "dark"); }
  };
  window.NovaTheme = Theme;
  doc.addEventListener("click", function (e) {
    if (e.target.closest(".theme-toggle")) Theme.toggle();
  });

  /* ---------- Navigation ---------- */
  var nav = doc.querySelector(".nav");
  if (nav) {
    var onScroll = function () { nav.classList.toggle("scrolled", window.scrollY > 12); };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
  }
  var burger = doc.querySelector(".burger");
  var links = doc.querySelector(".nav-links");
  if (burger && links) {
    burger.addEventListener("click", function () {
      var open = links.classList.toggle("open");
      burger.classList.toggle("open", open);
      burger.setAttribute("aria-expanded", open ? "true" : "false");
    });
    links.addEventListener("click", function (e) {
      if (e.target.tagName === "A") { links.classList.remove("open"); burger.classList.remove("open"); }
    });
  }

  /* scroll spy */
  var spyLinks = Array.prototype.slice.call(doc.querySelectorAll('.nav-links a[href^="#"]'));
  if (spyLinks.length && "IntersectionObserver" in window) {
    var byId = {};
    spyLinks.forEach(function (a) {
      var el = doc.querySelector(a.getAttribute("href"));
      if (el) byId[el.id] = a;
    });
    var spy = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting) return;
        spyLinks.forEach(function (a) { a.classList.remove("active"); });
        if (byId[en.target.id]) byId[en.target.id].classList.add("active");
      });
    }, { rootMargin: "-45% 0px -50% 0px" });
    Object.keys(byId).forEach(function (id) { spy.observe(doc.getElementById(id)); });
  }

  /* ---------- Reveal on scroll (staggered per parent) ---------- */
  function onceVisible(nodes, fn, opts) {
    if (!nodes.length) return;
    if (!("IntersectionObserver" in window)) { nodes.forEach(fn); return; }
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting) return;
        fn(en.target);
        io.unobserve(en.target);
      });
    }, opts || { threshold: 0.12, rootMargin: "0px 0px -6% 0px" });
    nodes.forEach(function (n) { io.observe(n); });
  }

  var reveals = Array.prototype.slice.call(doc.querySelectorAll(".reveal"));
  reveals.forEach(function (el) {
    var sibs = Array.prototype.filter.call(el.parentElement.children, function (c) {
      return c.classList.contains("reveal");
    });
    el.style.transitionDelay = Math.min(sibs.indexOf(el), 6) * 70 + "ms";
  });
  onceVisible(reveals, function (el) { el.classList.add("in"); });

  /* ---------- Counters ---------- */
  function fmt(v, el) {
    var dec = (el.dataset.count.split(".")[1] || "").length;
    var s = v.toFixed(dec);
    if (el.dataset.decimal) s = s.replace(".", el.dataset.decimal);
    if (el.dataset.thousands) s = s.replace(/\B(?=(\d{3})+(?!\d))/g, el.dataset.thousands);
    return (el.dataset.prefix || "") + s + (el.dataset.suffix || "");
  }
  onceVisible(Array.prototype.slice.call(doc.querySelectorAll("[data-count]")), function (el) {
    var target = parseFloat(el.dataset.count), start = null, dur = 1400;
    function step(ts) {
      if (start === null) start = ts;
      var p = Math.min((ts - start) / dur, 1);
      el.textContent = fmt(target * (1 - Math.pow(1 - p, 3)), el);
      if (p < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }, { threshold: 0.5 });

  /* ---------- Result meters ---------- */
  onceVisible(Array.prototype.slice.call(doc.querySelectorAll(".meter i[data-w]")), function (el) {
    el.style.width = el.dataset.w + "%";
  }, { threshold: 0.6 });

  /* ---------- BEP projection chart ----------
     Values read off the chart on the ISIF deck (units as on the deck). */
  var bep = doc.getElementById("bep-chart");
  if (bep) {
    var years = [2026, 2027, 2028, 2029, 2030];
    var series = [
      { name: "Fixed cost", color: "#c9a3a3", data: [4, 4, 4, 4, 4], dash: "5 5" },
      { name: "Total cost", color: "#962a2c", data: [4, 6, 8, 10, 12] },
      { name: "Revenue",    color: "#4b070f", data: [4, 7, 9, 13, 17] }
    ];
    var W = 440, H = 250, L = 34, R = 14, T = 12, B = 30, max = 20;
    var px = function (i) { return L + (W - L - R) * i / (years.length - 1); };
    var py = function (v) { return T + (H - T - B) * (1 - v / max); };
    var ns = "http://www.w3.org/2000/svg";
    var el = function (n, a) {
      var e = doc.createElementNS(ns, n);
      for (var k in a) e.setAttribute(k, a[k]);
      return e;
    };
    for (var v = 0; v <= max; v += 5) {
      bep.appendChild(el("line", { x1: L, x2: W - R, y1: py(v), y2: py(v), "class": "grid-l" }));
      var t = el("text", { x: L - 8, y: py(v) + 4, "text-anchor": "end", "class": "axis-t" });
      t.textContent = v;
      bep.appendChild(t);
    }
    years.forEach(function (y, i) {
      var t = el("text", { x: px(i), y: H - 8, "text-anchor": "middle", "class": "axis-t" });
      t.textContent = y;
      bep.appendChild(t);
    });
    /* shade the gap once revenue clears total cost */
    var area = "M" + years.map(function (_, i) { return px(i) + "," + py(series[2].data[i]); }).join(" L") +
      " L" + years.map(function (_, i) { return px(4 - i) + "," + py(series[1].data[4 - i]); }).join(" L") + "Z";
    bep.appendChild(el("path", { d: area, fill: "rgba(123,32,33,.08)" }));
    series.forEach(function (s) {
      var d = s.data.map(function (v, i) { return (i ? "L" : "M") + px(i) + "," + py(v); }).join(" ");
      var p = el("path", { d: d, fill: "none", stroke: s.color, "stroke-width": 2.6,
        "stroke-linecap": "round", "stroke-linejoin": "round" });
      if (s.dash) p.setAttribute("stroke-dasharray", s.dash);
      bep.appendChild(p);
      s.data.forEach(function (v, i) {
        bep.appendChild(el("circle", { cx: px(i), cy: py(v), r: 3.6, fill: "#fff", stroke: s.color, "stroke-width": 2 }));
      });
    });
    /* draw-in animation */
    onceVisible([bep], function () {
      Array.prototype.forEach.call(bep.querySelectorAll("path[stroke]"), function (p) {
        var len = p.getTotalLength();
        p.style.strokeDasharray = p.getAttribute("stroke-dasharray") || len;
        if (!p.getAttribute("stroke-dasharray")) {
          p.style.strokeDashoffset = len;
          p.getBoundingClientRect();
          p.style.transition = "stroke-dashoffset 1.6s cubic-bezier(.22,1,.36,1)";
          p.style.strokeDashoffset = 0;
        }
      });
    }, { threshold: 0.4 });
  }

  /* ---------- Showreel ----------
     preload="none" keeps the ~MB video off the critical path; it starts
     (muted) once the section is on screen, and never for reduce-motion. */
  var still = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  doc.querySelectorAll(".reel").forEach(function (box) {
    var reel = box.querySelector("video");
    var reelBtn = box.querySelector(".reel-toggle");
    if (!reel || !reelBtn) return;
    var userPaused = false;
    var sync = function () {
      reelBtn.textContent = reel.paused ? "Putar" : "Jeda";
      reelBtn.setAttribute("aria-pressed", reel.paused ? "false" : "true");
    };
    reelBtn.addEventListener("click", function () {
      if (reel.paused) { userPaused = false; reel.play().catch(function () {}); }
      else { userPaused = true; reel.pause(); }
    });
    reel.addEventListener("play", sync);
    reel.addEventListener("pause", sync);
    if ("IntersectionObserver" in window && !still) {
      new IntersectionObserver(function (entries) {
        entries.forEach(function (en) {
          if (en.isIntersecting && !userPaused) reel.play().catch(function () {});
          else if (!en.isIntersecting) reel.pause();
        });
      }, { threshold: 0.35 }).observe(reel);
    }
    sync();
  });

  /* ---------- Hero: blurred background film ----------
     Plays muted while the hero is on screen; stays on the poster for
     reduce-motion or data-saver users. */
  var heroFilm = doc.querySelector(".hero-bg-video");
  if (heroFilm) {
    var saveData = navigator.connection && navigator.connection.saveData;
    if (still || saveData) {
      heroFilm.removeAttribute("autoplay");
      heroFilm.pause();
    } else if ("IntersectionObserver" in window) {
      new IntersectionObserver(function (entries) {
        entries.forEach(function (en) {
          if (en.isIntersecting && !doc.hidden) heroFilm.play().catch(function () {});
          else heroFilm.pause();
        });
      }, { threshold: 0.05 }).observe(heroFilm);
    }
  }

  /* ---------- Hero carousel ----------
     Slides are stacked in one grid cell (no height jumps). Auto-advances
     every 7 s; pauses on hover, keyboard focus, hidden tab, or the pause
     button; reduce-motion starts paused. Inactive slides are `inert`. */
  var hc = doc.querySelector(".hc");
  if (hc) (function () {
    var slides = Array.prototype.slice.call(hc.querySelectorAll(".hc-slide"));
    var dotsBox = hc.querySelector(".hc-dots");
    var pauseBtn = hc.querySelector(".hc-pause");
    var DUR = 7000;
    var idx = 0, elapsed = 0, last = 0;
    var userPaused = !!still, hover = false, focus = false;
    var dots = slides.map(function (s, i) {
      var b = doc.createElement("button");
      b.type = "button";
      b.className = "hc-dot";
      b.setAttribute("role", "tab");
      b.setAttribute("aria-label", "Slide " + (i + 1));
      b.innerHTML = "<span></span>";
      b.addEventListener("click", function () { go(i); });
      dotsBox.appendChild(b);
      return b;
    });

    function go(i) {
      idx = (i + slides.length) % slides.length;
      elapsed = 0;
      slides.forEach(function (s, k) {
        var on = k === idx;
        s.classList.toggle("is-active", on);
        s.setAttribute("aria-hidden", on ? "false" : "true");
        if (on) s.removeAttribute("inert"); else s.setAttribute("inert", "");
      });
      dots.forEach(function (d, k) {
        d.setAttribute("aria-selected", k === idx ? "true" : "false");
        d.classList.toggle("is-active", k === idx);
        d.firstChild.style.transform = "scaleX(" + (k < idx ? 1 : 0) + ")";
      });
    }
    function paused() { return userPaused || hover || focus || doc.hidden; }
    function syncPause() {
      hc.classList.toggle("is-paused", userPaused);
      pauseBtn.setAttribute("aria-pressed", userPaused ? "true" : "false");
      pauseBtn.setAttribute("aria-label", userPaused ? "Putar slide otomatis" : "Jeda slide otomatis");
    }
    function tick(t) {
      var dt = last ? t - last : 0;
      last = t;
      if (!paused()) {
        elapsed += dt;
        if (elapsed >= DUR) go(idx + 1);
      }
      dots[idx].firstChild.style.transform = "scaleX(" + Math.min(elapsed / DUR, 1) + ")";
      requestAnimationFrame(tick);
    }

    hc.querySelector(".hc-prev").addEventListener("click", function () { go(idx - 1); });
    hc.querySelector(".hc-next").addEventListener("click", function () { go(idx + 1); });
    pauseBtn.addEventListener("click", function () { userPaused = !userPaused; syncPause(); });
    hc.addEventListener("mouseenter", function () { hover = true; });
    hc.addEventListener("mouseleave", function () { hover = false; });
    hc.addEventListener("focusin", function () { focus = true; });
    hc.addEventListener("focusout", function (e) { if (!hc.contains(e.relatedTarget)) focus = false; });
    hc.addEventListener("keydown", function (e) {
      if (e.key === "ArrowLeft") { go(idx - 1); e.preventDefault(); }
      else if (e.key === "ArrowRight") { go(idx + 1); e.preventDefault(); }
    });
    /* swipe */
    var x0 = null, y0 = 0;
    hc.addEventListener("touchstart", function (e) { x0 = e.touches[0].clientX; y0 = e.touches[0].clientY; }, { passive: true });
    hc.addEventListener("touchend", function (e) {
      if (x0 === null) return;
      var dx = e.changedTouches[0].clientX - x0, dy = e.changedTouches[0].clientY - y0;
      if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy) * 1.4) go(idx + (dx < 0 ? 1 : -1));
      x0 = null;
    }, { passive: true });

    go(0);
    syncPause();
    requestAnimationFrame(tick);
  })();

  /* ---------- Three.js ---------- */
  if (window.NovaThree) {
    var wave = doc.getElementById("wave-canvas");
    if (wave) window.NovaThree.initWave(wave);
    var viewer = doc.getElementById("viewer-canvas");
    if (viewer) {
      /* build the WebGL viewer only when it is about to scroll into view */
      onceVisible([viewer], function () {
        window.NovaThree.initViewer(viewer, doc.getElementById("viewer-fallback"));
      }, { rootMargin: "300px 0px" });
    }
  }

  doc.querySelectorAll("[data-year]").forEach(function (el) { el.textContent = new Date().getFullYear(); });
})();
