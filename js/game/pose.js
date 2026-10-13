/* ============================================================
   Nova Run: body tracking with MediaPipe Pose Landmarker, all on device.
   - loadPose(): local copy in assets/game/vendor/mediapipe (works offline at a
     booth, fetched by tools/fetch-game-vendor.py), CDN as fallback; GPU first.
   - Moves: turns landmarks into game input. Every threshold is relative to the
     player's torso length, so it works near or far from the camera, for kids
     and adults alike.
   ============================================================ */
const VER = "0.10.14";
const LOCAL = new URL("../../assets/game/vendor/mediapipe/", import.meta.url).href;
const CDN = "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@" + VER + "/";
const MODEL_CDN = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task";

export async function loadPose() {
  let vision, wasm, model;
  try {
    vision = await import(LOCAL + "vision_bundle.mjs");
    wasm = LOCAL.replace(/\/$/, "");
    model = LOCAL + "pose_landmarker_lite.task";
  } catch (e) {
    vision = await import(CDN + "vision_bundle.mjs");
    wasm = CDN + "wasm";
    model = MODEL_CDN;
  }
  const files = await vision.FilesetResolver.forVisionTasks(wasm);
  const opts = (delegate) => ({
    baseOptions: { modelAssetPath: model, delegate },
    runningMode: "VIDEO", numPoses: 1,
    minPoseDetectionConfidence: 0.5, minPosePresenceConfidence: 0.5, minTrackingConfidence: 0.5,
  });
  try { return await vision.PoseLandmarker.createFromOptions(files, opts("GPU")); }
  catch (e) { return await vision.PoseLandmarker.createFromOptions(files, opts("CPU")); }
}

const NOSE = 0, SH_L = 11, SH_R = 12, WR_L = 15, WR_R = 16, HIP_L = 23, HIP_R = 24, AN_L = 27, AN_R = 28;
const vis = (p) => (p.visibility === undefined ? 1 : p.visibility);

export class Moves {
  constructor() { this.reset(); }

  reset() {
    this.base = null;              // calibrated standing pose
    this.s = null;                 // smoothed signals
    this.lane = 0;
    this.jumpArmed = true;
    this.duck = false;
    this.handsSince = 0;
    this.handsFired = false;
    this.steps = [];
    this.stepSign = 0;
    this.present = false;
    this.stableSince = 0;
  }

  /* landmarks (normalised, image space) -> signals in mirror space */
  read(lm) {
    const ok = [SH_L, SH_R, HIP_L, HIP_R].every((i) => vis(lm[i]) > 0.5);
    if (!ok) return null;
    const x = 1 - (lm[SH_L].x + lm[SH_R].x) / 2;
    const sy = (lm[SH_L].y + lm[SH_R].y) / 2;
    const hy = (lm[HIP_L].y + lm[HIP_R].y) / 2;
    const legs = vis(lm[AN_L]) > 0.5 && vis(lm[AN_R]) > 0.5;
    const alt = legs ? lm[AN_L].y - lm[AN_R].y : lm[WR_L].y - lm[WR_R].y;   // running in place: legs, else arm pump
    const hands = lm[WR_L].y < lm[NOSE].y && lm[WR_R].y < lm[NOSE].y && vis(lm[WR_L]) > 0.4 && vis(lm[WR_R]) > 0.4;
    return { x, sy, hy, alt, hands };
  }

  calibrate() {
    if (!this.s) return false;
    const tl = Math.max(0.08, this.s.hy - this.s.sy);
    this.base = { x: this.s.x, sy: this.s.sy, hy: this.s.hy, tl };
    this.lane = 0; this.duck = false; this.jumpArmed = true;
    return true;
  }

  /* -> { present, stable, lane, jump, duck, hands, spm } */
  update(lm, now) {
    const r = lm ? this.read(lm) : null;
    const out = { present: !!r, stable: false, lane: this.lane, jump: false, duck: this.duck, hands: false, spm: this.spm(now) };
    this.present = !!r;
    if (!r) { this.stableSince = 0; this.handsSince = 0; return out; }

    const a = 0.55;
    if (!this.s) this.s = { ...r };
    else for (const k of ["x", "sy", "hy"]) this.s[k] += (r[k] - this.s[k]) * a;
    const s = this.s;

    // stillness, for calibration
    const moving = this.prev ? Math.abs(s.x - this.prev.x) + Math.abs(s.hy - this.prev.hy) > 0.01 : true;
    this.prev = { x: s.x, hy: s.hy };
    if (moving) this.stableSince = now; else if (!this.stableSince) this.stableSince = now;
    out.stable = now - this.stableSince > 900;

    // both hands above the head, held for half a second
    if (r.hands) {
      if (!this.handsSince) this.handsSince = now;
      if (now - this.handsSince > 500 && !this.handsFired) { out.hands = true; this.handsFired = true; }
    } else { this.handsSince = 0; this.handsFired = false; }

    if (!this.base) return out;
    const b = this.base;

    // lanes: sideways shift of the shoulders, with hysteresis
    const off = (s.x - b.x) / b.tl;
    if (off < -0.55) this.lane = -1;
    else if (off > 0.55) this.lane = 1;
    else if (Math.abs(off) < 0.32) this.lane = 0;
    out.lane = this.lane;

    // jump: hips rise; duck: shoulders drop
    const rise = (b.hy - s.hy) / b.tl;
    const drop = (s.sy - b.sy) / b.tl;
    if (rise > 0.22 && this.jumpArmed) { out.jump = true; this.jumpArmed = false; }
    if (rise < 0.08) this.jumpArmed = true;
    if (drop > 0.32) this.duck = true; else if (drop < 0.16) this.duck = false;
    out.duck = this.duck;

    // slow drift correction while standing normally (people creep forward/back)
    if (!this.duck && Math.abs(rise) < 0.08 && Math.abs(drop) < 0.08) {
      b.sy += (s.sy - b.sy) * 0.01; b.hy += (s.hy - b.hy) * 0.01;
      b.tl += (Math.max(0.08, s.hy - s.sy) - b.tl) * 0.01;
    }

    // cadence: sign changes of the left/right alternation
    const d = r.alt / b.tl;
    const sign = d > 0.07 ? 1 : d < -0.07 ? -1 : 0;
    if (sign && sign !== this.stepSign) { if (this.stepSign) this.steps.push(now); this.stepSign = sign; }
    out.spm = this.spm(now);
    return out;
  }

  spm(now) {
    while (this.steps.length && now - this.steps[0] > 3000) this.steps.shift();
    return this.steps.length * 20;
  }
}

const BONES = [[11, 12], [11, 13], [13, 15], [12, 14], [14, 16], [11, 23], [12, 24], [23, 24], [23, 25], [25, 27], [24, 26], [26, 28]];

export function drawSkeleton(ctx, lm, w, h) {
  ctx.clearRect(0, 0, w, h);
  if (!lm) return;
  ctx.lineWidth = Math.max(2, w / 90);
  ctx.strokeStyle = "rgba(95, 227, 255, .9)";
  ctx.fillStyle = "#ff4f63";
  ctx.beginPath();
  for (const [a, b] of BONES) {
    if (vis(lm[a]) < 0.4 || vis(lm[b]) < 0.4) continue;
    ctx.moveTo(lm[a].x * w, lm[a].y * h);
    ctx.lineTo(lm[b].x * w, lm[b].y * h);
  }
  ctx.stroke();
  for (const i of [0, 11, 12, 15, 16, 23, 24, 27, 28]) {
    if (vis(lm[i]) < 0.4) continue;
    ctx.beginPath();
    ctx.arc(lm[i].x * w, lm[i].y * h, ctx.lineWidth * 1.4, 0, Math.PI * 2);
    ctx.fill();
  }
}
