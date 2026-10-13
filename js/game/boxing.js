/* ============================================================
   Nova Boxing — upper-body sparring over the mirrored webcam.
   Attack: focus mitts appear within arm's reach (placed from the player's own
   shoulder width, so kids, adults, standing or seated all fit); hit them with
   a wrist before the timing ring closes. Gold mitts score double, streaks
   build a combo, the tempo rises over the 45 s round.
   Defend: Nova throws a hook from one side (warned ~1 s ahead); lean the head
   the other way to slip it, or lose the combo.
   ============================================================ */
import { loadPose } from "./pose.js";

const $ = (id) => document.getElementById(id);
const video = $("video"), cv = $("fx"), ctx = cv.getContext("2d");
const ROUND = 45;
const NOSE = 0, SH_L = 11, SH_R = 12, WR_L = 15, WR_R = 16;
const vis = (p) => (p && (p.visibility === undefined || p.visibility > 0.5));

const pad = new Image(); pad.src = "assets/game/band.webp";
let landmarker = null, poseReady = null, lastVT = -1, lm = null;
let state = "start", t0 = 0, score = 0, hits = 0, spawned = 0, combo = 0, bestCombo = 0, nextSpawn = 0, handsSince = 0;
let targets = [], bursts = [], body = null, head = null;
let hook = null, nextHook = 0, dodged = 0, hooks = 0, flash = 0;      // body: smoothed shoulder centre + width, in screen px
const BEST = "novaboxing-best";
let best = +(localStorage.getItem(BEST) || 0);
$("bestP").textContent = best ? "Rekor: " + best + " poin" : "";

/* ---------------- screen mapping (video is object-fit: cover and mirrored) ---------------- */
let W = 0, H = 0, dpr = 1;
function resize() {
  dpr = Math.min(devicePixelRatio || 1, 2);
  W = cv.clientWidth; H = cv.clientHeight;
  cv.width = W * dpr; cv.height = H * dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
}
addEventListener("resize", resize);
function toScreen(p) {
  const vw = video.videoWidth || 640, vh = video.videoHeight || 480;
  const s = Math.max(W / vw, H / vh), ox = (W - vw * s) / 2, oy = (H - vh * s) / 2;
  return { x: W - (ox + p.x * vw * s), y: oy + p.y * vh * s };
}

/* ---------------- camera + pose ---------------- */
const preload = () => (poseReady = poseReady || loadPose());
setTimeout(() => preload().catch(() => {}), 1200);
async function camera() {
  if (landmarker) return true;
  try {
    say("Menyalakan kamera…");
    const st = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user", width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false });
    video.srcObject = st; await video.play();
    say("Memuat pelacak gerakan…");
    landmarker = await preload();
    say("Angkat kedua tangan!");
    return true;
  } catch (e) {
    console.warn("[NovaBoxing] camera unavailable", e);
    say("Kamera tidak tersedia 😢");
    $("hint").textContent = "Game ini butuh kamera.";
    return false;
  }
}
function track(now) {
  if (!landmarker || video.readyState < 2 || video.currentTime === lastVT) return;
  lastVT = video.currentTime;
  const r = landmarker.detectForVideo(video, now);
  lm = r.landmarks && r.landmarks[0];
  if (!lm || !vis(lm[SH_L]) || !vis(lm[SH_R])) { body = null; return; }
  const a = toScreen(lm[SH_L]), b = toScreen(lm[SH_R]);
  const c = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2, w: Math.max(40, Math.hypot(a.x - b.x, a.y - b.y)) };
  if (vis(lm[NOSE])) { const n = toScreen(lm[NOSE]); head = head ? { x: head.x + (n.x - head.x) * 0.5, y: head.y + (n.y - head.y) * 0.5 } : n; }
  body = body ? { x: body.x + (c.x - body.x) * 0.3, y: body.y + (c.y - body.y) * 0.3, w: body.w + (c.w - body.w) * 0.1 } : c;

  // both hands above the nose for half a second: start / restart
  const up = vis(lm[WR_L]) && vis(lm[WR_R]) && lm[WR_L].y < lm[NOSE].y && lm[WR_R].y < lm[NOSE].y;
  if (up && (state === "start" || state === "over")) {
    if (!handsSince) handsSince = now;
    if (now - handsSince > 500) { handsSince = 0; begin(); }
  } else handsSince = 0;
}
function wrists() {
  if (!lm) return [];
  return [WR_L, WR_R].filter((i) => vis(lm[i])).map((i) => toScreen(lm[i]));
}

/* ---------------- sound ---------------- */
let ac = null;
function tone(f, d, type = "triangle", v = 0.2) {
  try {
    ac = ac || new (window.AudioContext || window.webkitAudioContext)();
    const o = ac.createOscillator(), g = ac.createGain(), t = ac.currentTime;
    o.type = type; o.frequency.setValueAtTime(f, t); o.frequency.exponentialRampToValueAtTime(f * 0.5, t + d);
    g.gain.setValueAtTime(v, t); g.gain.exponentialRampToValueAtTime(0.001, t + d);
    o.connect(g).connect(ac.destination); o.start(t); o.stop(t + d);
  } catch (e) { /* optional */ }
}

/* ---------------- game ---------------- */
const CHEERS = ["Mantap!", "Kena!", "Cepat!", "Lagi!", "Keren!"];
function say(s) { $("say").textContent = s; }
function show(id) { for (const p of ["start", "result"]) $(p).hidden = p !== id; }
async function begin() {
  if (!(await camera())) return;
  show(null);
  state = "count"; t0 = performance.now();
  score = 0; hits = 0; spawned = 0; combo = 0; bestCombo = 0; targets = []; bursts = []; nextSpawn = 0;
  hook = null; nextHook = 0; dodged = 0; hooks = 0;
}
$("go").addEventListener("click", begin);
$("again").addEventListener("click", begin);

function spawn(now) {
  if (!body) return;
  const el = (now - t0) / 1000;
  const side = Math.random() < 0.5 ? -1 : 1;
  const reach = body.w * (0.75 + Math.random() * 0.7);
  const x = body.x + side * reach;
  const y = body.y + body.w * (-1.15 + Math.random() * 1.45);      // from above the head to chest height
  if (targets.some((t) => Math.hypot(t.x - x, t.y - y) < body.w * 0.6)) return;
  const life = Math.max(1.0, 1.9 - el * 0.02);
  targets.push({ x: Math.max(40, Math.min(W - 40, x)), y: Math.max(90, Math.min(H - 60, y)), r: body.w * 0.32, born: now, life,
                 gold: Math.random() < 0.15 });
  spawned++;
}

function update(now) {
  track(now);
  if (state === "count") {
    const c = 3 - Math.floor((now - t0) / 800);
    $("big").textContent = c > 0 ? c : "GO!";
    if (c <= 0) { state = "play"; t0 = now; say("Pukul!"); setTimeout(() => ($("big").textContent = ""), 500); tone(880, 0.3); }
  }
  if (state === "play") {
    const el = (now - t0) / 1000;
    $("left").textContent = Math.max(0, Math.ceil(ROUND - el));
    const gap = Math.max(380, 1000 - el * 14), maxN = el > 20 ? 3 : 2;
    if (now > nextSpawn && targets.length < maxN) { spawn(now); nextSpawn = now + gap; }
    const ws = wrists();
    for (const t of targets) {
      if (t.done) continue;
      if (ws.some((w) => Math.hypot(w.x - t.x, w.y - t.y) < t.r * 1.15)) {
        t.done = "hit"; hits++; combo++; bestCombo = Math.max(bestCombo, combo);
        const pts = (t.gold ? 20 : 10) * (1 + Math.floor(combo / 5));
        score += pts;
        bursts.push({ x: t.x, y: t.y, born: now, txt: "+" + pts, gold: t.gold });
        tone(t.gold ? 1320 : 990, 0.15);
        if (combo % 5 === 0) say("Combo ×" + (1 + combo / 5) + "!"); else if (Math.random() < 0.3) say(CHEERS[(Math.random() * CHEERS.length) | 0]);
      } else if ((now - t.born) / 1000 > t.life) { t.done = "miss"; combo = 0; tone(180, 0.2, "sine", 0.12); }
    }
    targets = targets.filter((t) => !t.done);
    updateHook(now, el);
    if (el >= ROUND) over();
  }
  $("score").textContent = score;
  const cb = $("combo");
  cb.hidden = combo < 5; cb.textContent = "COMBO ×" + (1 + Math.floor(combo / 5));
}

/* Nova's hook: warn, then check the head slipped to the other side */
const WARN = 1.0;
function updateHook(now, el) {
  if (!nextHook) nextHook = now + 7000;
  if (!hook && now > nextHook && head && body && el < ROUND - 3) {
    hook = { side: Math.random() < 0.5 ? -1 : 1, start: now, x0: head.x };   // side: -1 comes from screen left
    hooks++;
    const el2 = $("dodge"); el2.hidden = false;
    el2.textContent = hook.side < 0 ? "MIRING KE KANAN ➡" : "⬅ MIRING KE KIRI";
    say("Awas pukulan!"); tone(440, 0.25, "square", 0.1);
  }
  if (!hook) return;
  const k = (now - hook.start) / 1000;
  if (k >= WARN) {
    const moved = (head.x - hook.x0) * -hook.side;              // positive = away from the glove
    const ok = moved > body.w * 0.35;
    if (ok) { dodged++; score += 15; combo++; bursts.push({ x: head.x, y: head.y - 60, born: now, txt: "MENGHINDAR +15", gold: true }); say("Gerakan bagus!"); tone(1200, 0.2); }
    else { combo = 0; flash = 1; say("Kena! Miringkan kepala lebih jauh."); tone(120, 0.35, "sawtooth", 0.25); }
    hook = null; $("dodge").hidden = true;
    nextHook = now + 5500 + Math.random() * 4000 - Math.min(2500, el * 50);
  }
}

function over() {
  state = "over"; targets = []; hook = null; $("dodge").hidden = true;
  const isBest = score > best;
  if (isBest) { best = score; try { localStorage.setItem(BEST, String(best)); } catch (e) { /* private */ } }
  $("resTitle").textContent = isBest ? "🏆 Rekor baru!" : "Ronde selesai!";
  $("resScore").textContent = score;
  $("resHits").textContent = hits;
  $("resAcc").textContent = spawned ? Math.round(100 * hits / spawned) + "%" : "0%";
  $("resDodge").textContent = dodged + "/" + hooks;
  say(isBest ? "Rekor baru! 🔥" : "Capek? Itu tandanya jantungmu bekerja!");
  show("result");
}

/* ---------------- drawing ---------------- */
function draw(now) {
  ctx.clearRect(0, 0, W, H);
  // wrists: glowing gloves
  for (const w of wrists()) {
    const r = body ? body.w * 0.16 : 22;
    const g = ctx.createRadialGradient(w.x, w.y, 2, w.x, w.y, r * 1.8);
    g.addColorStop(0, "rgba(255,255,255,.95)"); g.addColorStop(0.4, "rgba(255,79,99,.85)"); g.addColorStop(1, "rgba(255,79,99,0)");
    ctx.fillStyle = g; ctx.beginPath(); ctx.arc(w.x, w.y, r * 1.8, 0, Math.PI * 2); ctx.fill();
  }
  for (const t of targets) {
    const k = Math.min(1, (now - t.born) / 1000 / t.life);
    const pop = Math.min(1, (now - t.born) / 150);
    ctx.save(); ctx.translate(t.x, t.y); ctx.scale(pop, pop);
    ctx.fillStyle = t.gold ? "rgba(255,200,60,.92)" : "rgba(255,255,255,.92)";
    ctx.beginPath(); ctx.arc(0, 0, t.r, 0, Math.PI * 2); ctx.fill();
    ctx.lineWidth = Math.max(6, t.r * 0.2); ctx.strokeStyle = t.gold ? "#c98a00" : "#d61f3a";
    ctx.stroke();
    if (pad.complete) ctx.drawImage(pad, -t.r * 0.62, -t.r * 0.62, t.r * 1.24, t.r * 1.24);
    // timing ring
    ctx.lineWidth = Math.max(3, t.r * 0.09); ctx.strokeStyle = k > 0.7 ? "#ff3b3b" : "#2fd18b";
    ctx.beginPath(); ctx.arc(0, 0, t.r * 1.22, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * (1 - k)); ctx.stroke();
    ctx.restore();
  }
  // incoming hook: a glove sliding in from the side toward the head
  if (hook && head && body) {
    const k = Math.min(1, (now - hook.start) / 1000 / WARN);
    const from = hook.side < 0 ? -body.w : W + body.w;
    const gx = from + (hook.x0 - from) * k * k, gy = head.y;
    const r = body.w * 0.42;
    ctx.fillStyle = "rgba(255,59,59," + (0.15 + 0.25 * k) + ")";
    ctx.fillRect(hook.side < 0 ? 0 : W - W * 0.18, 0, W * 0.18, H);
    ctx.fillStyle = "#d61f3a"; ctx.beginPath(); ctx.ellipse(gx, gy, r * 1.15, r, 0, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = "#fff"; ctx.fillRect(gx - hook.side * r * 1.1 - r * 0.25, gy - r * 0.6, r * 0.5, r * 1.2);
    ctx.fillStyle = "rgba(255,255,255,.35)"; ctx.beginPath(); ctx.ellipse(gx + hook.side * r * 0.3, gy - r * 0.35, r * 0.35, r * 0.2, 0, 0, Math.PI * 2); ctx.fill();
  }
  if (flash > 0) { ctx.fillStyle = "rgba(255,40,60," + flash * 0.45 + ")"; ctx.fillRect(0, 0, W, H); flash = Math.max(0, flash - 0.04); }
  bursts = bursts.filter((b) => now - b.born < 600);
  for (const b of bursts) {
    const k = (now - b.born) / 600;
    ctx.globalAlpha = 1 - k;
    ctx.strokeStyle = b.gold ? "#ffc83c" : "#ffffff"; ctx.lineWidth = 6;
    ctx.beginPath(); ctx.arc(b.x, b.y, 30 + k * 90, 0, Math.PI * 2); ctx.stroke();
    ctx.fillStyle = "#fff"; ctx.font = "800 34px Poppins, sans-serif"; ctx.textAlign = "center";
    ctx.fillText(b.txt, b.x, b.y - 30 - k * 50);
    ctx.globalAlpha = 1;
  }
  if ((state === "start" || state === "over") && body) {          // show that the player is seen
    ctx.strokeStyle = "rgba(95,227,255,.8)"; ctx.lineWidth = 4; ctx.setLineDash([10, 8]);
    ctx.beginPath(); ctx.arc(body.x, body.y - body.w * 0.6, body.w * 0.55, 0, Math.PI * 2); ctx.stroke(); ctx.setLineDash([]);
  }
}

function loop() {
  const now = performance.now();
  update(now); draw(now);
  requestAnimationFrame(loop);
}
resize();
loop();
window.NovaBoxing = { state: () => state, score: () => score };   // for testing
