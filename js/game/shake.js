/* ============================================================
   Nova Shake Sprint — a 100 m race on the visitor's own phone.
   The accelerometer turns each arm swing into a beat; the beat RATE (not the
   force) sets Nova's speed, so shaking harder never helps. Swings above ~3 g
   trip a warning and make Nova stumble, which keeps phones in hands.
   No sensor (desktop, denied permission): tap left/right alternately.
   ============================================================ */
const $ = (id) => document.getElementById(id);
const cv = $("track"), ctx = cv.getContext("2d");
const G = 9.81;
const LIMIT = 3.0 * G;          // total acceleration above this = too hard
const BEAT_HI = 5.5, BEAT_LO = 2.0, REFRACT = 140;   // m/s^2 (gravity removed), ms
const RACE = 100;

const sheet = new Image();
sheet.src = "assets/game/nova-side.webp";             // 7 x 2 cells, 12 run frames + jump
const CW = 300, CH = 390;

/* ---------------- state ---------------- */
let state = "start", t0 = 0, now = 0, x = 0, v = 0, ghostX = 0, anim = 0, stumble = 0;
let beats = [], hi = false, lastBeat = 0, spm = 0, spmSum = 0, spmN = 0, swings = 0, tooHard = 0, forceShown = 0;
let sensor = false, lastMotion = 0, tapSide = null;
const BEST = "novashake-best";
let best = +(localStorage.getItem(BEST) || 0);
const ghostTime = () => best || 16;                 // pacer: your best time, else 16 s

/* ---------------- sensor ---------------- */
let lpX = 0, lpY = 0, lpZ = 0;                      // gravity estimate (low-pass)
function onMotion(e) {
  const a = e.accelerationIncludingGravity;
  if (!a || a.x === null) return;
  sensor = true; lastMotion = performance.now();
  const k = 0.1;
  lpX += (a.x - lpX) * k; lpY += (a.y - lpY) * k; lpZ += (a.z - lpZ) * k;
  const lin = e.acceleration && e.acceleration.x !== null ? e.acceleration : { x: a.x - lpX, y: a.y - lpY, z: a.z - lpZ };
  const m = Math.hypot(lin.x, lin.y, lin.z);
  const total = Math.hypot(a.x, a.y, a.z);
  forceShown = Math.max(forceShown * 0.9, total / LIMIT);
  if (state !== "race") return;
  if (total > LIMIT) { warnTooHard(); return; }
  const t = performance.now();
  if (!hi && m > BEAT_HI && t - lastBeat > REFRACT) { hi = true; beat(t); }
  if (hi && m < BEAT_LO) hi = false;
}
function beat(t) { lastBeat = t; beats.push(t); swings++; }
function warnTooHard() {
  if (stumble <= 0) { tooHard++; navigator.vibrate && navigator.vibrate(80); }
  stumble = 0.7; v *= 0.4;
  $("warn").hidden = false;
  clearTimeout(warnTooHard.t);
  warnTooHard.t = setTimeout(() => ($("warn").hidden = true), 900);
}

async function enableSensor() {
  try {
    if (typeof DeviceMotionEvent !== "undefined" && typeof DeviceMotionEvent.requestPermission === "function") {
      const r = await DeviceMotionEvent.requestPermission();        // iOS asks the user here
      if (r !== "granted") return false;
    }
    addEventListener("devicemotion", onMotion);
    return true;
  } catch (e) { return false; }
}

/* ---------------- tap fallback (no accelerometer) ---------------- */
function tap(side) {
  if (state !== "race" || side === tapSide) return;               // must alternate
  tapSide = side; beat(performance.now());
}
$("taps").addEventListener("pointerdown", (e) => { const b = e.target.closest("button"); if (b) tap(b.dataset.side); });
addEventListener("keydown", (e) => { if (e.key === "ArrowLeft" || e.key === "f") tap("L"); if (e.key === "ArrowRight" || e.key === "j") tap("R"); });

/* ---------------- flow ---------------- */
function show(id) { for (const p of ["start", "result"]) $(p).hidden = p !== id; }
async function start() {
  await enableSensor();
  show(null);
  x = 0; v = 0; ghostX = 0; anim = 0; stumble = 0; beats = []; swings = 0; tooHard = 0; spmSum = 0; spmN = 0; tapSide = null;
  state = "count"; t0 = performance.now();
  setTimeout(() => { if (!sensor || performance.now() - lastMotion > 1500) $("taps").hidden = false; }, 1200);
}
function finish() {
  state = "done";
  const time = (now - t0) / 1000;
  const avg = spmN ? Math.round(spmSum / spmN) : 0;
  const isBest = !best || time < best;
  if (isBest) { best = time; try { localStorage.setItem(BEST, best.toFixed(2)); } catch (e) { /* private mode */ } }
  $("resTitle").textContent = isBest ? "🏆 Rekor baru!" : "Finish!";
  $("resTime").textContent = time.toFixed(2);
  $("resSpm").textContent = avg;
  $("resZone").textContent = zone(avg).name;
  $("resSafe").textContent = swings ? Math.round(100 * swings / (swings + tooHard)) + "%" : "—";
  $("taps").hidden = true;
  navigator.vibrate && navigator.vibrate([60, 60, 120]);
  setTimeout(() => show("result"), 700);
}
$("go").addEventListener("click", start);
$("again").addEventListener("click", start);
$("bestS").textContent = best ? "Rekormu: " + best.toFixed(2) + " s" : "";

function zone(s) {
  if (s >= 180) return { name: "Sprint", cls: "z3" };
  if (s >= 120) return { name: "Tempo", cls: "z2" };
  if (s > 0) return { name: "Easy", cls: "z1" };
  return { name: "—", cls: "" };
}

/* ---------------- drawing ---------------- */
let W = 0, H = 0, dpr = 1;
function resize() {
  dpr = Math.min(devicePixelRatio || 1, 2);
  W = cv.clientWidth; H = cv.clientHeight;
  cv.width = W * dpr; cv.height = H * dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
}
addEventListener("resize", resize);

const crowd = Array.from({ length: 220 }, () => ({ x: Math.random(), y: Math.random(), c: ["#ff4f63", "#ffd166", "#ffffff", "#5fe3ff", "#8f2d3f"][(Math.random() * 5) | 0] }));
function draw(dt) {
  const PX = Math.min(W, H) / 7;                    // pixels per metre
  const camX = x * PX - W * 0.32;
  const ground = H * 0.62;
  // sky
  const g = ctx.createLinearGradient(0, 0, 0, ground);
  g.addColorStop(0, "#2d8fe0"); g.addColorStop(1, "#bfe6ff");
  ctx.fillStyle = g; ctx.fillRect(0, 0, W, ground);
  // stands (slow parallax)
  const standTop = ground - H * 0.24;
  ctx.fillStyle = "#5b2a36"; ctx.fillRect(0, standTop, W, H * 0.2);
  for (const p of crowd) {
    const px = ((p.x * W * 3 - camX * 0.25) % (W * 3) + W * 3) % (W * 3) - W;
    ctx.fillStyle = p.c; ctx.fillRect(px, standTop + 6 + p.y * H * 0.17, 5, 5);
  }
  ctx.fillStyle = "#e8e2d6"; ctx.fillRect(0, standTop + H * 0.2, W, H * 0.04);
  // banner
  const bx = ((W * 0.5 - camX * 0.5) % (W * 1.5) + W * 1.5) % (W * 1.5) - W * 0.4;
  ctx.fillStyle = "#6d0f22"; ctx.fillRect(bx, standTop - H * 0.07, W * 0.7, H * 0.06);
  ctx.fillStyle = "#fff"; ctx.font = `800 ${H * 0.032}px Poppins, sans-serif`; ctx.textBaseline = "middle";
  ctx.fillText("NOVA-BAND · LARI LEBIH AMAN", bx + 12, standTop - H * 0.04);
  // track: two lanes
  ctx.fillStyle = "#c8463e"; ctx.fillRect(0, ground, W, H - ground);
  ctx.fillStyle = "#fff";
  for (const ly of [ground, ground + (H - ground) * 0.42, H - 2]) ctx.fillRect(0, ly, W, 3);
  // distance marks + finish
  for (let m = 0; m <= RACE; m += 10) {
    const sx = m * PX - camX;
    if (sx < -60 || sx > W + 60) continue;
    ctx.fillStyle = "rgba(255,255,255,.85)"; ctx.fillRect(sx, ground, 3, H - ground);
    ctx.font = `700 ${H * 0.022}px Poppins, sans-serif`; ctx.fillText(m + " m", sx + 6, ground + 14);
  }
  const fx = RACE * PX - camX;
  if (fx > -40 && fx < W + 40) {
    const s = 12;
    for (let yy = ground; yy < H; yy += s) for (let k = 0; k < 2; k++) {
      ctx.fillStyle = ((yy - ground) / s + k) % 2 < 1 ? "#111" : "#fff"; ctx.fillRect(fx + k * s, yy, s, s);
    }
  }
  // ghost (best / pacer) in the far lane, Nova in the near lane
  const scale = (H - ground) * 1.05 / CH * 1.6;
  const fr = (n) => (n | 0) % 12;
  if (sheet.complete && sheet.naturalWidth) {
    const gF = fr(anim * 0.9 + 5);
    ctx.globalAlpha = 0.45; ctx.filter = "grayscale(1) brightness(1.3)";
    sprite(gF, ghostX * PX - camX, ground + (H - ground) * 0.36, scale * 0.82);
    ctx.globalAlpha = 1; ctx.filter = "none";
    const f = stumble > 0 ? 12 : fr(anim);
    sprite(f, x * PX - camX, H - 6 + (stumble > 0 ? 6 : 0), scale);
  }
  // speed streaks
  if (v > 5) {
    ctx.strokeStyle = "rgba(255,255,255,.5)"; ctx.lineWidth = 2;
    for (let i = 0; i < 6; i++) {
      const yy = ground + 20 + ((i * 53 + now * 0.3) % (H - ground - 30));
      const xx = W * 0.32 - 80 - ((i * 97) % 120);
      ctx.beginPath(); ctx.moveTo(xx, yy); ctx.lineTo(xx - v * 9, yy); ctx.stroke();
    }
  }
}
function sprite(i, sx, footY, s) {
  const w = CW * s, h = CH * s;
  ctx.drawImage(sheet, (i % 7) * CW, ((i / 7) | 0) * CH, CW, CH, sx - w * 0.5, footY - h * 0.97, w, h);
}

/* ---------------- loop ---------------- */
let last = performance.now();
function loop(t) {
  const dt = Math.min(0.05, (t - last) / 1000); last = t; now = t;
  while (beats.length && t - beats[0] > 2000) beats.shift();
  spm = beats.length * 30;
  if (state === "count") {
    const c = 3 - Math.floor((t - t0) / 800);
    $("big").textContent = c > 0 ? c : "GO!";
    if (c <= 0) { state = "race"; t0 = t; setTimeout(() => ($("big").textContent = ""), 500); }
  }
  if (state === "race") {
    const target = stumble > 0 ? 0 : Math.min(9.5, spm / 30);   // 180 swings/min -> 6 m/s
    v += (target - v) * Math.min(1, dt * 2.2);
    x += v * dt;
    ghostX = Math.min(RACE, ((t - t0) / 1000) * RACE / ghostTime());
    if (spm > 0) { spmSum += spm; spmN++; }
    if (x >= RACE) { x = RACE; finish(); }
  }
  stumble = Math.max(0, stumble - dt);
  anim += dt * (4 + v * 2.4);
  draw(dt);
  // HUD
  const el = state === "race" ? (t - t0) / 1000 : state === "done" ? (now - t0) / 1000 : 0;
  if (state !== "done") $("time").textContent = el.toFixed(2);
  $("dist").textContent = Math.floor(x);
  $("spm").textContent = spm;
  const z = zone(spm);
  $("zone").textContent = z.name; $("zone").className = "zone " + z.cls;
  $("spmBar").style.width = Math.min(100, spm / 3) + "%";
  const f = Math.min(1.2, forceShown);
  $("forceBar").style.width = Math.min(100, f * 100) + "%";
  $("forceBar").className = f > 1 ? "bad" : f > 0.75 ? "mid" : "";
  $("force").textContent = f > 1 ? "terlalu keras!" : f > 0.75 ? "hampir batas" : "aman";
  $("force").className = f > 1 ? "bad" : f > 0.75 ? "mid" : "safe";
  forceShown *= 0.97;
  requestAnimationFrame(loop);
}
resize();
requestAnimationFrame(loop);
window.NovaShake = { beat: () => beat(performance.now()), state: () => state, motion: onMotion };   // for testing
