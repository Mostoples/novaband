/* ============================================================
   Nova-Band — AI Buddy: chat with Nova (text, quick chips or voice)
   - Brain: on-device intent matcher (assets/buddy/intents.json,
     Indonesian + English) grounded in the live state window.NovaState,
     so answers quote the runner's real heart rate, zone, readiness...
     It can act too: start / pause the session.
   - Voice: English -> Kyutai Pocket TTS on the laptop
     (tools/nova-tts-server.py, http://localhost:8765) when it is running;
     otherwise, and always for Indonesian (Pocket TTS has no Indonesian
     model), the device voice through the Web Speech API.
   - Listening: SpeechRecognition where the browser offers it.
   - While running it speaks by itself: heart-rate alerts and every km.
   Nothing is sent to a cloud LLM; the text never leaves the device
   except to the local Pocket TTS server.
   ============================================================ */
(function () {
  "use strict";
  var doc = document;
  var S = window.NovaState;
  var TTS_URL = "http://localhost:8765";
  var KEY = "novaband-buddy";
  var pref = { lang: "id", voice: true };
  try { Object.assign(pref, JSON.parse(localStorage.getItem(KEY) || "{}")); } catch (e) {}
  var save = function () { try { localStorage.setItem(KEY, JSON.stringify(pref)); } catch (e) {} };

  var T = {
    id: { title: "Nova · AI Buddy", ph: "Tanya Nova…", hello: "Hai, aku Nova! Tanya apa saja soal lari, detak jantung, atau cara pakai band. Aku juga bisa memulai sesi.",
          chips: ["Detak jantungku?", "Siap latihan hari ini?", "Mulai sesi", "Kenapa di lengan atas?", "Cara pakai band", "Tips pendinginan"],
          listen: "Mendengarkan…", engDevice: "Suara: perangkat", engPocket: "Suara: Pocket TTS", noMic: "Mikrofon tidak tersedia di browser ini.",
          km: "Kilometer {n}! Pace {pace} per km, detak jantung {hr}.", alert: "Pelan dulu! Detak jantungmu {hr}, di atas batas {thr}. Atur napas ya.",
          notConnected: "Band belum terhubung, jadi angka ini dari mode simulasi." },
    en: { title: "Nova · AI Buddy", ph: "Ask Nova…", hello: "Hi, I'm Nova! Ask me anything about running, your heart rate or the band. I can start a session too.",
          chips: ["My heart rate?", "Should I train today?", "Start session", "Why the upper arm?", "How to wear it", "Cool-down tips"],
          listen: "Listening…", engDevice: "Voice: device", engPocket: "Voice: Pocket TTS", noMic: "Microphone isn't available in this browser.",
          km: "Kilometre {n}! Pace {pace} per km, heart rate {hr}.", alert: "Easy now! Your heart rate is {hr}, above your {thr} limit. Breathe.",
          notConnected: "The band isn't connected, so these numbers come from the demo." }
  };
  var L = function () { return T[pref.lang]; };

  /* ---------------- live values for the placeholders ---------------- */
  function zoneOf(hr) {
    var p = hr / ((S && S.maxHR) || 195);
    return p < .6 ? 1 : p < .7 ? 2 : p < .8 ? 3 : p < .9 ? 4 : 5;
  }
  var ZN = { id: ["", "pemulihan", "aerobik ringan", "aerobik", "ambang", "maksimal"],
             en: ["", "recovery", "easy aerobic", "aerobic", "threshold", "maximum"] };
  function fmtPace(p) { if (!p || !isFinite(p)) return "-"; var m = Math.floor(p), s = Math.round((p - m) * 60); return m + ":" + String(s).padStart(2, "0"); }
  function fmtTime(t) { t = Math.round(t || 0); return Math.floor(t / 60) + ":" + String(t % 60).padStart(2, "0"); }
  function values() {
    var hr = S ? Math.round(S.hr) : 70, z = zoneOf(hr);
    var steps = Math.round(8500 + (S ? S.dist * 1000 / 1.1 : 0));
    return { hr: hr, zone: z, zoneName: ZN[pref.lang][z], ready: S ? Math.round(S.readiness) : 85,
      pace: S && S.running ? fmtPace(S.pace) : "-", dist: S ? S.dist.toFixed(2).replace(".", pref.lang === "id" ? "," : ".") : "0",
      time: fmtTime(S && S.t), cad: S && S.running ? Math.round(S.cadence) : 0, kcal: S ? Math.round(S.kcal) : 0,
      thr: S ? S.thr.hr : 185, batt: S ? Math.round(S.battery) : 87, steps: steps.toLocaleString(pref.lang === "id" ? "id-ID" : "en-US") };
  }
  function fill(t) { var v = values(); return t.replace(/\{(\w+)\}/g, function (_, k) { return v[k] !== undefined ? v[k] : ""; }); }

  /* ---------------- brain ---------------- */
  var INTENTS = [];
  fetch("assets/buddy/intents.json").then(function (r) { return r.json(); }).then(function (d) { INTENTS = d; });
  var FIRST = ["chest_pain_emergency", "pain_injury"];          // safety intents win any tie
  var norm = function (s) { return " " + s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9 ]/g, " ").replace(/\s+/g, " ") + " "; };
  /* emergency first: chest pain / can't breathe / fainting, in any word order */
  var EMERG = [/(dada\w*|chest).*(nyeri|sakit|sesak|nyesek|berat|pain|hurt|tight)|(nyeri|sakit|sesak|pain|tight).*(dada\w*|chest)/,
               /(sesak napas|sesak nafas|susah napas|susah nafas|sulit napas|sulit bernapas|gak bisa napas|ga bisa napas|tidak bisa bernapas|can ?t breathe|cannot breathe|short of breath|hard to breathe)/,
               /(mau pingsan|hampir pingsan|pingsan|kunang|faint|pass(ing)? out|collapse)/];
  function match(text) {
    var raw = norm(text);
    if (EMERG.some(function (re) { return re.test(raw); })) return byId("chest_pain_emergency");
    var words = raw.trim().split(" ");
    var has = function (w) { return words.some(function (q) { return q === w || (w.length > 3 && q.indexOf(w) === 0); }); };
    var best = null, score = 0;
    INTENTS.forEach(function (it) {
      if (it.intent === "fallback") return;
      var s = 0;
      (it.kw_id || []).concat(it.kw_en || []).forEach(function (k) {
        var ks = norm(k).trim().split(" ").filter(function (w) { return w.length > 1; });
        if (ks.length && ks.every(has)) s += ks.length * 2 + (FIRST.indexOf(it.intent) >= 0 ? 3 : 0);
      });
      if (s > score) { score = s; best = it; }
    });
    return best || byId("fallback");
  }
  function byId(id) { return INTENTS.filter(function (i) { return i.intent === id; })[0]; }
  var pick = function (a) { return a[Math.floor(Math.random() * a.length)]; };
  function reply(text) {
    var it = match(text);
    if (!it) return { text: "…" };
    var lang = pref.lang, pool = it[lang];
    if (it.intent === "should_train" && S && S.readiness < S.thr.ready) pool = it[lang + "_rest"] || pool;
    var out = fill(pick(pool)), act = null;
    if (it.intent === "start_session" && S && !S.running) act = "toggle";
    if (it.intent === "stop_session" && S && S.running) act = "toggle";
    if (/^(hr_now|zone|pace|distance|cadence|calories)$/.test(it.intent) && S && !S.band) out += " " + L().notConnected;
    return { text: out, act: act, urgent: it.intent === "chest_pain_emergency", intent: it.intent };
  }

  /* ---------------- voice out ---------------- */
  var pocket = false, audio = null;
  function checkPocket() {
    if (!window.fetch) return;
    var ctl = window.AbortController ? new AbortController() : null;
    if (ctl) setTimeout(function () { ctl.abort(); }, 1500);
    fetch(TTS_URL + "/health", ctl ? { signal: ctl.signal } : {}).then(function (r) { return r.json(); })
      .then(function (j) { pocket = j && j.engine === "pocket-tts"; badge(); })
      .catch(function () { pocket = false; badge(); });
  }
  function deviceSay(text) {
    if (!("speechSynthesis" in window)) return;
    speechSynthesis.cancel();
    var u = new SpeechSynthesisUtterance(text.replace(/[*_]/g, ""));
    u.lang = pref.lang === "id" ? "id-ID" : "en-US";
    var vs = speechSynthesis.getVoices().filter(function (v) { return v.lang && v.lang.replace("_", "-").indexOf(u.lang.slice(0, 2)) === 0; });
    if (vs.length) u.voice = vs[0];
    u.rate = 1.03; u.pitch = 1.15;
    speechSynthesis.speak(u);
  }
  function say(text) {
    if (!pref.voice) return;
    if (pref.lang === "en" && pocket) {
      if (audio) { audio.pause(); }
      speaking(true);
      fetch(TTS_URL + "/tts", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text: text, lang: "en" }) })
        .then(function (r) { if (!r.ok) throw 0; return r.blob(); })
        .then(function (b) { audio = new Audio(URL.createObjectURL(b)); audio.onended = function () { speaking(false); }; return audio.play(); })
        .catch(function () { pocket = false; badge(); speaking(false); deviceSay(text); });
    } else {
      deviceSay(text);
    }
  }

  /* ---------------- UI ---------------- */
  var css = doc.createElement("link");
  css.rel = "stylesheet"; css.href = "css/nova-buddy.css";
  doc.head.appendChild(css);
  var fab = doc.createElement("button");
  fab.className = "nb-fab"; fab.setAttribute("aria-label", "Chat dengan Nova");
  fab.innerHTML = '<img src="assets/img/mascot-wink.webp" alt=""><span class="nb-dot"></span>';
  var box = doc.createElement("section");
  box.className = "nb-chat"; box.hidden = true; box.setAttribute("aria-label", "Nova AI Buddy");
  box.innerHTML =
    '<header class="nb-head"><img class="nb-av" src="assets/img/mascot-wink.webp" alt="">' +
    '<div><b class="nb-title"></b><span class="nb-eng"></span></div>' +
    '<div class="nb-ctl"><button class="nb-btn" data-a="lang" title="Bahasa / Language"></button>' +
    '<button class="nb-btn" data-a="voice" title="Suara"></button><button class="nb-btn" data-a="close" aria-label="Tutup">✕</button></div></header>' +
    '<div class="nb-log" aria-live="polite"></div><div class="nb-chips"></div>' +
    '<form class="nb-in"><button type="button" class="nb-mic" aria-label="Bicara">🎤</button>' +
    '<input maxlength="160" autocomplete="off"><button class="nb-send" aria-label="Kirim">➤</button></form>';
  doc.body.appendChild(fab);
  doc.body.appendChild(box);
  var log = box.querySelector(".nb-log"), input = box.querySelector("input"), chips = box.querySelector(".nb-chips");

  function speaking(on) { box.classList.toggle("talking", !!on); }
  function badge() {
    box.querySelector(".nb-eng").textContent = (pref.lang === "en" && pocket) ? L().engPocket : L().engDevice;
  }
  function labels() {
    box.querySelector(".nb-title").textContent = L().title;
    box.querySelector('[data-a="lang"]').textContent = pref.lang.toUpperCase();
    box.querySelector('[data-a="voice"]').textContent = pref.voice ? "🔊" : "🔇";
    input.placeholder = L().ph;
    chips.innerHTML = L().chips.map(function (c) { return '<button type="button">' + c + "</button>"; }).join("");
    badge();
  }
  function bubble(text, who, urgent) {
    var d = doc.createElement("div");
    d.className = "nb-msg " + who + (urgent ? " urgent" : "");
    d.textContent = text;
    log.appendChild(d);
    log.scrollTop = log.scrollHeight;
  }
  function ask(text) {
    text = (text || "").trim();
    if (!text) return;
    bubble(text, "me");
    var r = reply(text);
    box.classList.add("thinking");
    setTimeout(function () {
      box.classList.remove("thinking");
      if (r.act === "toggle") { var b = doc.getElementById("btn-session"); if (b) b.click(); }
      bubble(r.text, "nova", r.urgent);
      say(r.text);
    }, 380);
  }
  function open(on) {
    box.hidden = !on;
    fab.classList.toggle("on", on);
    if (on) {
      if (!log.children.length) { bubble(L().hello, "nova"); }
      checkPocket();
      setTimeout(function () { input.focus(); }, 50);
    }
  }
  fab.addEventListener("click", function () { open(box.hidden); });
  box.addEventListener("click", function (e) {
    var a = e.target.closest("[data-a]");
    if (a) {
      if (a.dataset.a === "close") open(false);
      if (a.dataset.a === "voice") { pref.voice = !pref.voice; if (!pref.voice && "speechSynthesis" in window) speechSynthesis.cancel(); }
      if (a.dataset.a === "lang") { pref.lang = pref.lang === "id" ? "en" : "id"; bubble(L().hello, "nova"); }
      save(); labels();
      return;
    }
    var c = e.target.closest(".nb-chips button");
    if (c) ask(c.textContent);
  });
  box.querySelector(".nb-in").addEventListener("submit", function (e) { e.preventDefault(); ask(input.value); input.value = ""; });

  /* ---------------- voice in ---------------- */
  var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  var mic = box.querySelector(".nb-mic");
  if (!SR) mic.title = T.id.noMic;
  mic.addEventListener("click", function () {
    if (!SR) { bubble(L().noMic, "nova"); return; }
    var rec = new SR();
    rec.lang = pref.lang === "id" ? "id-ID" : "en-US";
    rec.interimResults = false;
    box.classList.add("listening");
    input.placeholder = L().listen;
    rec.onresult = function (e) { ask(e.results[0][0].transcript); };
    rec.onend = function () { box.classList.remove("listening"); input.placeholder = L().ph; };
    rec.start();
  });

  /* ---------------- proactive voice while running ---------------- */
  var lastKm = 0, lastAlert = 0;
  setInterval(function () {
    if (!S || !S.running) { if (S && !S.running && S.dist === 0) lastKm = 0; return; }
    var v = values(), now = Date.now();
    if (S.hr >= S.thr.hr && now - lastAlert > 45000) {
      lastAlert = now;
      var a = L().alert.replace("{hr}", v.hr).replace("{thr}", v.thr);
      if (!box.hidden) bubble(a, "nova", true);
      say(a);
    }
    var km = Math.floor(S.dist);
    if (km > lastKm) {
      lastKm = km;
      var k = L().km.replace("{n}", km).replace("{pace}", v.pace).replace("{hr}", v.hr);
      if (!box.hidden) bubble(k, "nova");
      say(k);
    }
  }, 1000);

  labels();
  checkPocket();
  if ("speechSynthesis" in window) speechSynthesis.getVoices();     // warm the voice list
  window.NovaBuddy = { ask: ask, open: open, say: say, match: function (q) { var m = match(q); return m && m.intent; } };
})();
