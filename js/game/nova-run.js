/* ============================================================
   Nova Run — a three-lane endless runner for the Nova-Band booth.
   Nova (sprites rendered from the Blender mascot, blender/game_sprites.py)
   runs down a cartoon street lined with Nova-Band billboards. Players steer
   with their body through the webcam (js/game/pose.js): shift sideways to
   change lane, jump, crouch, run in place for a score multiplier, raise both
   hands to start. Keyboard / swipe work too. With nobody playing, Nova runs
   on autopilot (attract mode) so the screen keeps drawing people in.
   ============================================================ */
import * as THREE from "three";
import { loadPose, Moves, drawSkeleton } from "./pose.js";

const $ = (id) => document.getElementById(id);
const stage = $("stage");
const rnd = (a, b) => a + Math.random() * (b - a);
const pick = (arr) => arr[(Math.random() * arr.length) | 0];

/* ---------------- renderer / camera ---------------- */
const renderer = new THREE.WebGLRenderer({ canvas: $("world"), antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(60, 9 / 16, 0.1, 400);
const CAM = new THREE.Vector3(0, 3.1, 5.6);
camera.position.copy(CAM);
camera.lookAt(0, 1.0, -10);
function resize() {
  const w = stage.clientWidth, h = stage.clientHeight;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  const sk = $("skel");
  sk.width = sk.clientWidth * devicePixelRatio; sk.height = sk.clientHeight * devicePixelRatio;
}
addEventListener("resize", resize);

function canvasTex(w, h, draw, repeat) {
  const c = document.createElement("canvas");
  c.width = w; c.height = h;
  draw(c.getContext("2d"), w, h);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 4;
  if (repeat) { t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(...repeat); }
  return t;
}

/* ---------------- sky, light, fog ---------------- */
scene.background = canvasTex(16, 512, (g, w, h) => {
  const gr = g.createLinearGradient(0, 0, 0, h);
  gr.addColorStop(0, "#3aa3ff"); gr.addColorStop(0.55, "#8fd3ff"); gr.addColorStop(1, "#dff3ff");
  g.fillStyle = gr; g.fillRect(0, 0, w, h);
});
scene.fog = new THREE.Fog(0xd6efff, 70, 175);
scene.add(new THREE.HemisphereLight(0xffffff, 0x8aa36a, 1.25));
const sun = new THREE.DirectionalLight(0xfff2dd, 1.6);
sun.position.set(-6, 12, 6);
scene.add(sun);

// a few soft clouds far away
const cloudTex = canvasTex(256, 128, (g, w, h) => {
  g.fillStyle = "#fff";
  for (const [x, y, r] of [[70, 80, 40], [120, 60, 52], [175, 78, 38], [100, 90, 34], [150, 92, 34]]) {
    g.beginPath(); g.arc(x, y, r, 0, Math.PI * 2); g.fill();
  }
});
for (let i = 0; i < 7; i++) {
  const m = new THREE.Mesh(new THREE.PlaneGeometry(26, 13), new THREE.MeshBasicMaterial({ map: cloudTex, transparent: true, fog: false, depthWrite: false }));
  m.position.set(rnd(-70, 70), rnd(34, 58), -230);
  scene.add(m);
}

/* ---------------- road, sidewalks ---------------- */
const LANE = 2.2, ROAD = 7.6, LEN = 260, WALK = 3.4, TILE = 8;
const laneX = (l) => l * LANE;
const roadTex = canvasTex(512, 512, (g, w, h) => {
  g.fillStyle = "#454852"; g.fillRect(0, 0, w, h);
  for (let i = 0; i < 2500; i++) { g.fillStyle = `rgba(255,255,255,${Math.random() * 0.05})`; g.fillRect(Math.random() * w, Math.random() * h, 2, 2); }
  g.fillStyle = "#f4f4f4";
  g.fillRect(10, 0, 10, h); g.fillRect(w - 20, 0, 10, h);                    // edge lines
  for (const x of [w / 3, (2 * w) / 3]) g.fillRect(x - 5, 40, 10, h / 2 - 40);  // dashes
}, [1, LEN / TILE]);
const road = new THREE.Mesh(new THREE.PlaneGeometry(ROAD, LEN), new THREE.MeshLambertMaterial({ map: roadTex }));
road.rotation.x = -Math.PI / 2;
road.position.z = -LEN / 2 + 20;
scene.add(road);

const walkTex = canvasTex(256, 256, (g, w, h) => {
  g.fillStyle = "#d9d2c5"; g.fillRect(0, 0, w, h);
  g.strokeStyle = "#bdb4a5"; g.lineWidth = 4;
  for (let y = 0; y <= h; y += 64) { g.beginPath(); g.moveTo(0, y); g.lineTo(w, y); g.stroke(); }
  g.beginPath(); g.moveTo(w / 2, 0); g.lineTo(w / 2, h); g.stroke();
  g.fillStyle = "#9b9488"; g.fillRect(0, 0, 18, h);                       // curb
}, [1, LEN / TILE]);
const walks = [];
for (const s of [-1, 1]) {
  const m = new THREE.Mesh(new THREE.BoxGeometry(WALK, 0.25, LEN), new THREE.MeshLambertMaterial({ map: walkTex }));
  m.position.set(s * (ROAD / 2 + WALK / 2), 0.12, -LEN / 2 + 20);
  if (s < 0) m.scale.x = -1;
  scene.add(m); walks.push(m);
  const grass = new THREE.Mesh(new THREE.PlaneGeometry(80, LEN), new THREE.MeshLambertMaterial({ color: 0x86c26a }));
  grass.rotation.x = -Math.PI / 2;
  grass.position.set(s * (ROAD / 2 + WALK + 40), 0.01, -LEN / 2 + 20);
  scene.add(grass);
}

/* ---------------- scenery: buildings, billboards, trees, lamps ---------------- */
const PAL = [0xe8a87c, 0xf6d186, 0x8fd1c6, 0xf2efe6, 0xd5896f, 0xa8c5e8, 0xf4b6b6, 0xc7b8e0];
const windowTex = canvasTex(128, 256, (g, w, h) => {
  g.fillStyle = "#ffffff"; g.fillRect(0, 0, w, h);
  for (let y = 18; y < h - 20; y += 38) for (let x = 14; x < w - 20; x += 36) {
    g.fillStyle = Math.random() < 0.25 ? "#ffe7a8" : "#5f7d99"; g.fillRect(x, y, 22, 26);
    g.fillStyle = "rgba(255,255,255,.6)"; g.fillRect(x, y, 22, 3);
  }
}, [1, 1]);
windowTex.wrapS = windowTex.wrapT = THREE.RepeatWrapping;

const ADS = [
  ["LARI LEBIH AMAN", "Pantau detak jantung dari lengan atas", "#6d0f22"],
  ["NOVA-BAND", "Upper-arm wearable untuk pelari", "#ff4f63"],
  ["TAHU KAPAN GAS,", "tahu kapan istirahat · Readiness Score", "#1c6e8c"],
  ["PELATIH IKUT MENJAGA", "Shared Safety Net · peringatan dini", "#3a2a6b"],
];
const adTex = ADS.map(([big, small, bg]) => canvasTex(1024, 512, (g, w, h) => {
  g.fillStyle = bg; g.fillRect(0, 0, w, h);
  g.fillStyle = "rgba(255,255,255,.08)";
  for (let i = 0; i < 6; i++) { g.beginPath(); g.arc(w * 0.85, h * 0.5, 60 + i * 55, 0, Math.PI * 2); g.lineWidth = 18; g.strokeStyle = "rgba(255,255,255,.06)"; g.stroke(); }
  g.fillStyle = "#fff"; g.font = "800 92px Poppins, sans-serif"; g.fillText(big, 56, 230);
  g.fillStyle = "#ffe0c8"; g.font = "600 46px Poppins, sans-serif"; g.fillText(small, 60, 310);
  g.fillStyle = "#fff"; g.font = "800 40px Poppins, sans-serif"; g.fillText("Nova", 60, 440);
  g.fillStyle = "#ff8a98"; g.fillText("-", 60 + g.measureText("Nova").width, 440);
  g.fillStyle = "#fff"; g.fillText("Band", 60 + g.measureText("Nova-").width, 440);
  g.fillStyle = "rgba(255,255,255,.75)"; g.font = "500 30px Poppins, sans-serif"; g.fillText("novaband-id.web.app", 290, 440);
}));

const SPAN = 240, SLOT = 12;
const scenery = [];
const boxGeo = new THREE.BoxGeometry(1, 1, 1);
function building(side) {
  const g = new THREE.Group();
  const h = rnd(7, 20), d = SLOT - rnd(0.6, 2.2), w = rnd(7, 11);
  const tex = windowTex.clone(); tex.needsUpdate = true; tex.repeat.set(Math.round(d / 3), Math.round(h / 3.4));
  const mat = new THREE.MeshLambertMaterial({ color: pick(PAL), map: tex });
  const body = new THREE.Mesh(boxGeo, mat);
  body.scale.set(w, h, d); body.position.set(0, h / 2, 0);
  const roof = new THREE.Mesh(boxGeo, new THREE.MeshLambertMaterial({ color: 0x6b5a55 }));
  roof.scale.set(w + 0.4, 0.5, d + 0.4); roof.position.y = h + 0.25;
  g.add(body, roof);
  g.position.x = side * (ROAD / 2 + WALK + w / 2 + 0.2);
  return g;
}
function billboard(side, k) {
  const g = new THREE.Group();
  const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.15, 0.15, 6.4, 8), new THREE.MeshLambertMaterial({ color: 0x5a5f69 }));
  pole.position.y = 3.2;
  const board = new THREE.Mesh(new THREE.BoxGeometry(6.4, 3.2, 0.25), [0, 0, 0, 0, new THREE.MeshBasicMaterial({ map: adTex[k % adTex.length] }), 0]
    .map((m) => m || new THREE.MeshLambertMaterial({ color: 0xe9e9e9 })));
  board.position.y = 6.2;
  g.add(pole, board);
  g.position.x = side * (ROAD / 2 + WALK - 0.4);
  g.rotation.y = side * -0.42;                                             // angled toward the runner
  return g;
}
const trunkMat = new THREE.MeshLambertMaterial({ color: 0x7a5236 });
const leafMats = [0x4f9d48, 0x67b356, 0x3e8a4a].map((c) => new THREE.MeshLambertMaterial({ color: c }));
function tree() {
  const g = new THREE.Group();
  const t = new THREE.Mesh(new THREE.CylinderGeometry(0.16, 0.2, 1.6, 6), trunkMat); t.position.y = 0.8;
  const l = new THREE.Mesh(new THREE.IcosahedronGeometry(1.15, 0), pick(leafMats)); l.position.y = 2.4; l.scale.y = 1.1;
  g.add(t, l);
  return g;
}
function lamp() {
  const g = new THREE.Group();
  const m = new THREE.MeshLambertMaterial({ color: 0x3d4450 });
  const p = new THREE.Mesh(new THREE.CylinderGeometry(0.07, 0.09, 4.2, 6), m); p.position.y = 2.1;
  const arm = new THREE.Mesh(new THREE.BoxGeometry(1.0, 0.08, 0.08), m); arm.position.set(-0.5, 4.15, 0);
  const bulb = new THREE.Mesh(new THREE.BoxGeometry(0.4, 0.14, 0.24), new THREE.MeshBasicMaterial({ color: 0xfff3c4 })); bulb.position.set(-0.95, 4.05, 0);
  g.add(p, arm, bulb);
  return g;
}
let adK = 0;
for (const side of [-1, 1]) {
  for (let i = 0; i < SPAN / SLOT; i++) {
    const z = 15 - i * SLOT;
    const isAd = i % 4 === 2 + (side > 0 ? 1 : 0) % 2;
    const b = building(side); b.position.z = z; scene.add(b);
    scenery.push({ obj: b, kind: "building", side });
    if (isAd) { const a = billboard(side, adK++); a.position.z = z - 2; scene.add(a); scenery.push({ obj: a, kind: "ad" }); }
    const t = i % 2 ? tree() : lamp();
    t.position.set(side * (ROAD / 2 + WALK - 0.7), 0.25, z - SLOT / 2);
    if (side > 0 && t.children.length === 3) t.rotation.y = Math.PI;
    scene.add(t); scenery.push({ obj: t, kind: "prop" });
  }
}

/* ---------------- obstacles and bands ---------------- */
const stripeTex = canvasTex(256, 32, (g, w, h) => {
  for (let x = 0; x < w; x += 32) { g.fillStyle = (x / 32) % 2 ? "#ffffff" : "#e8283f"; g.fillRect(x, 0, 32, h); }
});
const bannerTex = canvasTex(512, 160, (g, w, h) => {
  g.fillStyle = "#6d0f22"; g.fillRect(0, 0, w, h);
  g.fillStyle = "#fff"; g.font = "800 64px Poppins, sans-serif"; g.textAlign = "center"; g.fillText("NOVA-BAND", w / 2, 82);
  g.fillStyle = "#ffd2a0"; g.font = "700 34px Poppins, sans-serif"; g.fillText("▼ MERUNDUK! ▼", w / 2, 134);
});
const postMat = new THREE.MeshLambertMaterial({ color: 0xf1f1f1 });
const TRUCK = [0xffc145, 0x4fb3d9, 0xff7a59, 0x8fd16a];
function makeObstacle(type, lane) {
  const g = new THREE.Group();
  if (type === "hurdle") {
    for (const s of [-1, 1]) { const p = new THREE.Mesh(new THREE.BoxGeometry(0.1, 0.75, 0.1), postMat); p.position.set(s * 0.85, 0.37, 0); g.add(p); }
    const bar = new THREE.Mesh(new THREE.BoxGeometry(1.9, 0.26, 0.14), new THREE.MeshLambertMaterial({ map: stripeTex }));
    bar.position.y = 0.62; g.add(bar);
  } else if (type === "bar") {
    for (const s of [-1, 1]) { const p = new THREE.Mesh(new THREE.BoxGeometry(0.12, 2.7, 0.12), postMat); p.position.set(s * 0.98, 1.35, 0); g.add(p); }
    const b = new THREE.Mesh(new THREE.BoxGeometry(2.05, 0.78, 0.12), [0, 0, 0, 0, new THREE.MeshBasicMaterial({ map: bannerTex }), 0]
      .map((m) => m || new THREE.MeshLambertMaterial({ color: 0x6d0f22 })));
    b.position.y = 2.0; g.add(b);
  } else {                                                                 // block: a little delivery van
    const c = pick(TRUCK);
    const body = new THREE.Mesh(new THREE.BoxGeometry(1.9, 1.7, 4.4), new THREE.MeshLambertMaterial({ color: c }));
    body.position.y = 1.15; g.add(body);
    const cab = new THREE.Mesh(new THREE.BoxGeometry(1.86, 0.9, 1.2), new THREE.MeshLambertMaterial({ color: 0x2f3a4a }));
    cab.position.set(0, 1.6, 1.6); g.add(cab);
    for (const [x, z] of [[-0.85, 1.4], [0.85, 1.4], [-0.85, -1.4], [0.85, -1.4]]) {
      const w = new THREE.Mesh(new THREE.CylinderGeometry(0.36, 0.36, 0.3, 12), new THREE.MeshLambertMaterial({ color: 0x222222 }));
      w.rotation.z = Math.PI / 2; w.position.set(x, 0.36, z); g.add(w);
    }
  }
  g.position.x = laneX(lane);
  return { obj: g, type, lane, len: type === "block" ? 4.4 : 0.3, hit: false };
}

const bandMat = new THREE.MeshLambertMaterial({ color: 0x9b1b30, emissive: 0x3a0610 });
const screenMat = new THREE.MeshBasicMaterial({ color: 0x5fe3ff });
function makeBand(lane, y) {
  const g = new THREE.Group();
  const ring = new THREE.Mesh(new THREE.TorusGeometry(0.24, 0.075, 10, 24), bandMat);
  const scr = new THREE.Mesh(new THREE.BoxGeometry(0.26, 0.17, 0.07), screenMat); scr.position.z = 0.27;
  const glow = new THREE.Mesh(new THREE.CircleGeometry(0.42, 24), new THREE.MeshBasicMaterial({ color: 0xffe066, transparent: true, opacity: 0.35, depthWrite: false }));
  glow.position.z = -0.05;
  g.add(glow, ring, scr);
  g.position.set(laneX(lane), y, 0);
  return { obj: g, lane, y, taken: false };
}

/* ---------------- Nova ---------------- */
const sheet = new THREE.TextureLoader().load("assets/game/nova-sheet.webp");
sheet.colorSpace = THREE.SRGBColorSpace;
sheet.repeat.set(1 / 7, 1 / 2);
const NW = 2.0, NH = NW * 390 / 300;
const novaMat = new THREE.MeshBasicMaterial({ map: sheet, transparent: true, alphaTest: 0.08 });
const nova = new THREE.Mesh(new THREE.PlaneGeometry(NW, NH), novaMat);
scene.add(nova);
const shadow = new THREE.Mesh(new THREE.CircleGeometry(0.62, 24), new THREE.MeshBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.28, depthWrite: false }));
shadow.rotation.x = -Math.PI / 2; shadow.scale.y = 0.55;
scene.add(shadow);
function frame(i) { sheet.offset.set((i % 7) / 7, 1 - (((i / 7) | 0) + 1) / 2); }

/* ---------------- sound ---------------- */
let actx = null;
function beep(f0, f1, dur, type = "sine", vol = 0.18) {
  try {
    actx = actx || new (window.AudioContext || window.webkitAudioContext)();
    const o = actx.createOscillator(), g = actx.createGain(), t = actx.currentTime;
    o.type = type; o.frequency.setValueAtTime(f0, t); o.frequency.exponentialRampToValueAtTime(f1, t + dur);
    g.gain.setValueAtTime(vol, t); g.gain.exponentialRampToValueAtTime(0.001, t + dur);
    o.connect(g).connect(actx.destination); o.start(t); o.stop(t + dur);
  } catch (e) { /* audio is optional */ }
}
const sfx = {
  band: () => { beep(880, 1320, 0.12, "triangle"); setTimeout(() => beep(1320, 1760, 0.1, "triangle", 0.12), 60); },
  jump: () => beep(300, 700, 0.18, "square", 0.06),
  duck: () => beep(500, 220, 0.16, "square", 0.05),
  lane: () => beep(420, 520, 0.06, "sine", 0.06),
  crash: () => { beep(160, 40, 0.5, "sawtooth", 0.22); beep(90, 30, 0.6, "sine", 0.3); },
  go: () => beep(660, 990, 0.25, "triangle", 0.2),
};

/* ---------------- game state ---------------- */
const P = { lane: 0, x: 0, y: 0, vy: 0, slide: 0, anim: 0 };
let obstacles = [], bands = [];
let state = "attract", speed = 14, dist = 0, score = 0, collected = 0, nextRow = 30, crashT = 0, overT = 0, mult = 1, spm = 0;
let useCam = false, shake = 0;
const BEST_KEY = "novarun-best";
let best = +(localStorage.getItem(BEST_KEY) || 0);
const PZ = -3.2;                                          // Nova runs a little ahead, above the camera inset
const SPAWN_Z = -135, GRAV = -30, JUMP_V = 11.5;

function resetRun() {
  for (const o of obstacles) scene.remove(o.obj);
  for (const b of bands) scene.remove(b.obj);
  obstacles = []; bands = [];
  Object.assign(P, { lane: 0, x: 0, y: 0, vy: 0, slide: 0 });
  speed = 14; dist = 0; score = 0; collected = 0; nextRow = 30; mult = 1;
  novaMat.color.set(0xffffff);
  // pre-fill the road ahead so the first seconds are not empty
  for (let z = -40; z > SPAWN_Z; z -= 22) spawnRow(z);
  hud();
}

function spawnRow(z) {
  const r = Math.random();
  const lanes = [-1, 0, 1];
  let free = pick(lanes);
  const put = (type, lane) => { const o = makeObstacle(type, lane); o.obj.position.z = z; scene.add(o.obj); obstacles.push(o); };
  if (r < 0.14) lanes.forEach((l) => put("hurdle", l));                    // everyone jumps
  else if (r < 0.26) lanes.forEach((l) => put("bar", l));                  // everyone ducks
  else if (r < 0.6) put(pick(["hurdle", "bar", "block", "block"]), pick(lanes.filter((l) => l !== free)));
  else lanes.filter((l) => l !== free).forEach((l) => put(pick(["hurdle", "bar", "block"]), l));
  // a line of bands in the free lane (over the hurdle if the whole row is hurdles)
  const high = r < 0.14;
  for (let k = 0; k < 5; k++) {
    const b = makeBand(free, high && k === 2 ? 2.0 : 1.0);
    b.obj.position.z = z + 6 - k * 2.6;
    scene.add(b.obj); bands.push(b);
  }
}

/* ---------------- input ---------------- */
function act(a) {
  if (state !== "play" && !(state === "attract" && a === "auto")) return;
  if (a === "left" && P.lane > -1) { P.lane--; sfx.lane(); }
  if (a === "right" && P.lane < 1) { P.lane++; sfx.lane(); }
  if (a === "jump" && P.y <= 0.001) { P.vy = JUMP_V; P.slide = 0; sfx.jump(); }
  if (a === "duck") { if (P.slide <= 0) sfx.duck(); P.slide = 0.75; if (P.y > 0) P.vy = -14; }
}
addEventListener("keydown", (e) => {
  const k = e.key;
  if (state !== "play" && (k === " " || k === "Enter")) { e.preventDefault(); return state === "over" ? again() : startKeys(); }
  if (k === "ArrowLeft" || k === "a") act("left");
  if (k === "ArrowRight" || k === "d") act("right");
  if (k === "ArrowUp" || k === "w" || k === " ") { e.preventDefault(); act("jump"); }
  if (k === "ArrowDown" || k === "s") act("duck");
});
let touch0 = null;
stage.addEventListener("touchstart", (e) => { touch0 = e.touches[0]; }, { passive: true });
stage.addEventListener("touchend", (e) => {
  if (!touch0) return;
  const t = e.changedTouches[0], dx = t.clientX - touch0.clientX, dy = t.clientY - touch0.clientY;
  if (Math.max(Math.abs(dx), Math.abs(dy)) > 30) {
    if (Math.abs(dx) > Math.abs(dy)) act(dx < 0 ? "left" : "right"); else act(dy < 0 ? "jump" : "duck");
  }
  touch0 = null;
});

/* ---------------- camera + pose ---------------- */
const video = $("video"), skel = $("skel"), sctx = skel.getContext("2d");
const moves = new Moves();
let landmarker = null, lastVideoT = -1, lastLm = null, poseOut = null, poseLaneShown = 0;

async function startCamera() {
  if (landmarker) return true;
  try {
    $("calibMsg").textContent = "Menyalakan kamera…";
    const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user", width: { ideal: 640 }, height: { ideal: 480 } }, audio: false });
    video.srcObject = stream;
    await video.play();
    $("cam").classList.add("on");
    $("calibMsg").textContent = "Memuat pelacak gerakan…";
    landmarker = await loadPose();
    useCam = true;
    return true;
  } catch (e) {
    console.warn("[NovaRun] camera/pose unavailable", e);
    $("camOff").innerHTML = "Kamera tidak tersedia<br><small>pakai ← → ↑ ↓</small>";
    return false;
  }
}

function trackPose(now) {
  if (!landmarker || video.readyState < 2 || video.currentTime === lastVideoT) return;
  lastVideoT = video.currentTime;
  const res = landmarker.detectForVideo(video, now);
  lastLm = res.landmarks && res.landmarks[0];
  drawSkeleton(sctx, lastLm, skel.width, skel.height);
  poseOut = moves.update(lastLm, now);
  spm = poseOut.spm;

  if (poseOut.hands && (state === "attract" || state === "over")) { state === "over" ? again() : beginCalib(); return; }
  if (state !== "play") return;
  if (poseOut.lane !== P.lane) { P.lane = poseOut.lane; sfx.lane(); cue(poseOut.lane < 0 ? "⬅" : poseOut.lane > 0 ? "➡" : "⬆"); }
  if (poseOut.jump) { act("jump"); cue("LOMPAT!"); }
  if (poseOut.duck) { if (P.slide <= 0) { sfx.duck(); cue("JONGKOK!"); } P.slide = Math.max(P.slide, 0.25); }
}
let cueT = 0;
function cue(s) { $("cue").textContent = s; cueT = 0.6; }

/* ---------------- flow ---------------- */
const panels = ["attract", "calib", "over"];
function show(id) { panels.forEach((p) => ($(p).hidden = p !== id)); }

async function beginCalib() {
  show("calib");
  state = "calib";
  $("count").textContent = "";
  if (!(await startCamera())) return startKeys();
  moves.reset();
  calibSince = 0;
}
let calibSince = 0;
function calibTick(now) {
  if (!poseOut || !poseOut.present) { $("calibMsg").innerHTML = "Mundur sampai <b>kepala sampai pinggul</b> terlihat di kamera."; calibSince = 0; $("count").textContent = ""; return; }
  $("calibMsg").innerHTML = "Bagus! Berdiri tegak di <b>tengah</b>…";
  if (!calibSince) calibSince = now;
  const left = 3 - Math.floor((now - calibSince) / 1000);
  $("count").textContent = left > 0 ? left : "GO!";
  if (left <= 0 && moves.calibrate()) go();
}
function startKeys() { useCam = useCam && !!landmarker; show(null); state = "count"; countT = 2.1; resetRun(); }
let countT = 0;
function go() { show(null); resetRun(); state = "play"; sfx.go(); cue("LARI!"); }
function again() {
  resetRun();
  if (useCam) { state = "calib"; show("calib"); calibSince = 0; moves.reset(); }
  else { state = "count"; countT = 2.1; show(null); }
}
function gameOver() {
  state = "over"; overT = 0;
  const s = Math.floor(score);
  if (s > best) { best = s; try { localStorage.setItem(BEST_KEY, String(best)); } catch (e) { /* private mode */ } }
  $("finalScore").textContent = s;
  $("finalBands").textContent = collected + " Nova-Band terkumpul";
  $("bestO").textContent = s >= best && s > 0 ? "🏆 Rekor baru hari ini!" : "Rekor: " + best + " m";
  show("over");
}
$("btnCam").addEventListener("click", beginCalib);
$("btnKeys").addEventListener("click", startKeys);
$("btnAgain").addEventListener("click", again);

function hud() {
  $("score").textContent = Math.floor(score);
  $("bands").textContent = collected;
  const m = $("mult");
  m.hidden = !(state === "play" && useCam && mult > 1);
  if (!m.hidden) m.innerHTML = "×" + mult + "<small>" + spm + " langkah/menit</small>";
  $("bestA").textContent = best ? "Rekor: " + best + " m" : "";
}

/* ---------------- autopilot (attract mode) ---------------- */
function autopilot() {
  const ahead = (lane, z0, z1) => obstacles.filter((o) => o.lane === lane && o.obj.position.z > z0 && o.obj.position.z < z1);
  const blocked = (lane) => ahead(lane, PZ - 16, PZ + 3).some((o) => o.type === "block");
  if (blocked(P.lane)) {
    const opts = [P.lane - 1, P.lane + 1].filter((l) => l >= -1 && l <= 1 && !blocked(l));
    if (opts.length) act(opts[0] < P.lane ? "left" : "right");
  } else if (Math.random() < 0.01) {
    const l = pick([-1, 0, 1]);
    if (!blocked(l) && Math.abs(l - P.lane) === 1) act(l < P.lane ? "left" : "right");
  }
  for (const o of ahead(P.lane, PZ - 4.2, PZ - 1.6)) {
    if (o.type === "hurdle") act("jump");
    if (o.type === "bar") act("duck");
  }
}

/* ---------------- main loop ---------------- */
const clock = new THREE.Clock();
function update(dt, now) {
  trackPose(now);
  const running = state === "play" || state === "attract" || state === "count";
  if (state === "calib") calibTick(now);
  if (state === "count") { countT -= dt; cue(countT > 1.4 ? "3" : countT > 0.7 ? "2" : countT > 0 ? "1" : ""); if (countT <= 0) { state = "play"; sfx.go(); cue("LARI!"); } }
  if (state === "attract") autopilot();
  if (state === "over") { overT += dt; if (overT > 25) { show("attract"); state = "attract"; resetRun(); } }

  const sp = running ? (state === "count" ? 0 : speed) : state === "over" && crashT > 0 ? 0 : 0;
  if (state === "play") {
    speed = Math.min(32, speed + dt * 0.28);
    mult = useCam ? (spm >= 140 ? 3 : spm >= 90 ? 2 : 1) : 1;
    score += sp * dt * mult;
  }
  dist += sp * dt;

  // scroll the ground and scenery
  roadTex.offset.y += (sp * dt) / TILE;
  walkTex.offset.y += (sp * dt) / TILE;
  for (const s of scenery) {
    s.obj.position.z += sp * dt;
    if (s.obj.position.z > 18) s.obj.position.z -= SPAN;
  }

  // spawn rows by distance
  if (running && state !== "count") {
    nextRow -= sp * dt;
    if (nextRow <= 0) { spawnRow(SPAWN_Z); nextRow = rnd(17, 26) + speed * 0.25; }
  }

  // player physics
  P.x += (laneX(P.lane) - P.x) * Math.min(1, dt * 14);
  if (P.y > 0 || P.vy > 0) { P.vy += GRAV * dt; P.y = Math.max(0, P.y + P.vy * dt); if (P.y === 0) P.vy = 0; }
  P.slide = Math.max(0, P.slide - dt);
  P.anim += dt * (8 + sp * 0.55);
  frame(P.y > 0.05 ? 12 : P.slide > 0 ? 13 : (P.anim | 0) % 12);
  nova.position.set(P.x, NH * 0.5 - 0.42 + P.y, PZ);
  shadow.position.set(P.x, 0.03, PZ + 0.05);
  shadow.scale.setScalar(Math.max(0.45, 1 - P.y * 0.25)); shadow.scale.y *= 0.55;

  // obstacles: move, collide, recycle
  for (const o of obstacles) {
    o.obj.position.z += sp * dt;
    const dz = Math.abs(o.obj.position.z - PZ);
    if (!o.hit && (state === "play" || state === "attract") && dz < o.len / 2 + 0.35 && Math.abs(P.x - laneX(o.lane)) < 1.05) {
      const clear = o.type === "hurdle" ? P.y > 0.72 : o.type === "bar" ? P.slide > 0 : false;
      if (!clear) {
        o.hit = true;
        if (state === "play") { sfx.crash(); shake = 0.45; novaMat.color.set(0xff8f8f); state = "crash"; crashT = 0.9; }
      }
    }
  }
  obstacles = obstacles.filter((o) => { if (o.obj.position.z > 14) { scene.remove(o.obj); return false; } return true; });

  for (const b of bands) {
    b.obj.position.z += sp * dt;
    b.obj.rotation.y += dt * 3;
    if (!b.taken && Math.abs(b.obj.position.z - PZ) < 0.7 && Math.abs(P.x - laneX(b.lane)) < 0.9 && Math.abs(P.y + 1 - b.y) < 1.1) {
      b.taken = true; scene.remove(b.obj);
      if (state === "play") { collected++; score += 10 * mult; sfx.band(); const bb = document.querySelector(".bubble"); bb.classList.remove("pop"); void bb.offsetWidth; bb.classList.add("pop"); }
    }
  }
  bands = bands.filter((b) => { if (b.taken || b.obj.position.z > 14) { scene.remove(b.obj); return false; } return true; });

  if (state === "crash") { crashT -= dt; if (crashT <= 0) gameOver(); }

  // camera: follow the lane a little, shake on a crash
  shake = Math.max(0, shake - dt);
  camera.position.set(CAM.x + P.x * 0.35 + (Math.random() - 0.5) * shake, CAM.y + (Math.random() - 0.5) * shake, CAM.z);
  camera.lookAt(P.x * 0.3, 1.0, -10);

  cueT -= dt;
  if (cueT <= 0) $("cue").textContent = "";
  hud();
}

function loop() {
  const dt = Math.min(0.05, clock.getDelta());
  update(dt, performance.now());
  renderer.render(scene, camera);
  requestAnimationFrame(loop);
}

resize();
resetRun();
show("attract");
loop();
window.NovaRun = { state: () => state, act, P };      // for testing
