/* ============================================================
   Buku tamu — selfie booth.
   Front camera, mirrored preview (feels like a mirror), but the saved photo
   is NOT mirrored. Face filters follow the face (MediaPipe FaceDetector, run
   on the device), Nova the mascot photobombs with a few cheeky moves, and a
   name ribbon with the Nova-Band logo sits under the photo.
   ============================================================ */
export const OUT_W = 720, OUT_H = 960, PH = 800;             // photo area 720x800 + ribbon 160

const MP = "/assets/game/vendor/mediapipe/";
const MP_CDN = "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/";
const FACE_CDN = "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite";

const img = (src) => { const i = new Image(); i.src = src; return i; };
const NOVA = { wink: img("/assets/img/mascot-wink.webp"), run: img("/assets/img/mascot-run.webp"), hero: img("/assets/img/mascot-hero.webp") };

export const FILTERS = [
  { id: "none", label: "Tanpa filter" },
  { id: "headband", label: "Headband" },
  { id: "kacamata", label: "Kacamata" },
  { id: "telinga", label: "Telinga Nova" },
  { id: "juara", label: "Juara 🏅" },
];

async function loadFaceDetector() {
  let vision, wasm, model;
  try { vision = await import(MP + "vision_bundle.mjs"); wasm = location.origin + MP.replace(/\/$/, ""); model = MP + "blaze_face_short_range.tflite"; }
  catch (e) { vision = await import(MP_CDN + "vision_bundle.mjs"); wasm = MP_CDN + "wasm"; model = FACE_CDN; }
  const files = await vision.FilesetResolver.forVisionTasks(wasm);
  const o = (delegate) => ({ baseOptions: { modelAssetPath: model, delegate }, runningMode: "VIDEO", minDetectionConfidence: 0.5 });
  try { return await vision.FaceDetector.createFromOptions(files, o("GPU")); }
  catch (e) { return await vision.FaceDetector.createFromOptions(files, o("CPU")); }
}

export class Booth {
  constructor(video, canvas) {
    this.video = video; this.canvas = canvas; this.ctx = canvas.getContext("2d");
    canvas.width = OUT_W; canvas.height = OUT_H;
    this.filter = "headband"; this.face = null; this.faceT = 0; this.detector = null;
    this.name = ""; this.org = ""; this.count = 0; this.t0 = performance.now(); this.frozenT = null; this.lastVT = -1;
  }

  async start() {
    const st = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user", width: { ideal: 1280 }, height: { ideal: 960 } }, audio: false });
    this.stream = st; this.video.srcObject = st; await this.video.play();
    loadFaceDetector().then((d) => (this.detector = d)).catch((e) => console.warn("[bukutamu] filter wajah tidak tersedia", e));
    const tick = () => { if (!this.stream) return; this.detect(); this.render(this.ctx, true, this.countdown); this.raf = requestAnimationFrame(tick); };
    tick();
  }

  stop() {
    cancelAnimationFrame(this.raf);
    if (this.stream) this.stream.getTracks().forEach((t) => t.stop());
    this.stream = null;
  }

  /* crop of the video that fills the 720x800 photo area */
  crop() {
    const vw = this.video.videoWidth || 640, vh = this.video.videoHeight || 480;
    const s = Math.max(OUT_W / vw, PH / vh);
    return { s, ox: (OUT_W - vw * s) / 2, oy: (PH - vh * s) / 2, vw, vh };
  }

  detect() {
    const v = this.video, now = performance.now();
    if (!this.detector || v.readyState < 2 || v.currentTime === this.lastVT) return;
    this.lastVT = v.currentTime;
    const r = this.detector.detectForVideo(v, now);
    const d = r.detections && r.detections[0];
    if (!d || !d.keypoints || d.keypoints.length < 2) { if (now - this.faceT > 400) this.face = null; return; }
    const { s, ox, oy, vw, vh } = this.crop();
    const P = (k) => ({ x: ox + k.x * vw * s, y: oy + k.y * vh * s });          // unmirrored output coords
    const a = P(d.keypoints[0]), b = P(d.keypoints[1]);
    const [L, R] = a.x < b.x ? [a, b] : [b, a];
    const bb = d.boundingBox;
    const f = { cx: (L.x + R.x) / 2, cy: (L.y + R.y) / 2, w: bb.width * s, ang: Math.atan2(R.y - L.y, R.x - L.x), L, R,
                top: oy + bb.originY * s, bottom: oy + (bb.originY + bb.height) * s };
    if (this.face) {                                                             // smooth the jitter
      const k = 0.45, o = this.face;
      for (const key of ["cx", "cy", "w", "ang", "top", "bottom"]) f[key] = o[key] + (f[key] - o[key]) * k;
    }
    this.face = f; this.faceT = now;
  }

  /* draw one frame; mirror=true for the live preview, false for the saved photo */
  render(ctx, mirror, countdown) {
    const { s, ox, oy, vw, vh } = this.crop();
    ctx.save();
    ctx.beginPath(); ctx.rect(0, 0, OUT_W, PH); ctx.clip();
    ctx.fillStyle = "#222"; ctx.fillRect(0, 0, OUT_W, PH);
    if (mirror) { ctx.translate(OUT_W, 0); ctx.scale(-1, 1); }
    if (this.video.readyState >= 2) ctx.drawImage(this.video, ox, oy, vw * s, vh * s);
    if (mirror) ctx.setTransform(1, 0, 0, 1, 0, 0);
    const mx = (x) => (mirror ? OUT_W - x : x);
    if (this.face) this.decorate(ctx, this.face, mx, mirror);
    this.mascot(ctx, mx, this.frozenT ?? performance.now() - this.t0);
    ctx.restore();
    this.ribbon(ctx);
    if (countdown) {
      ctx.fillStyle = "rgba(0,0,0,.25)"; ctx.fillRect(0, 0, OUT_W, PH);
      ctx.fillStyle = "#fff"; ctx.font = "800 260px Poppins, sans-serif"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
      ctx.fillText(countdown, OUT_W / 2, PH / 2);
    }
  }

  decorate(ctx, f, mx, mirror) {
    const id = this.filter;
    if (id === "none") return;
    const ang = mirror ? -f.ang : f.ang;
    const W = f.w;
    const at = (x, y, fn) => { ctx.save(); ctx.translate(mx(x), y); ctx.rotate(ang); fn(); ctx.restore(); };
    // unit vector "up" the face (perpendicular to the eye line), in unmirrored coords
    const ux = Math.sin(f.ang), uy = -Math.cos(f.ang);
    if (id === "headband" || id === "juara") {
      at(f.cx + ux * W * 0.42, f.cy + uy * W * 0.42, () => {
        const bw = W * 1.22, bh = W * 0.24;
        const g = ctx.createLinearGradient(0, -bh / 2, 0, bh / 2);
        g.addColorStop(0, "#ff5a6e"); g.addColorStop(1, "#b0122e");
        ctx.fillStyle = g; rr(ctx, -bw / 2, -bh / 2, bw, bh, bh * 0.35); ctx.fill();
        ctx.fillStyle = "#fff"; ctx.fillRect(-bw / 2, -bh / 2 + bh * 0.1, bw, bh * 0.07); ctx.fillRect(-bw / 2, bh / 2 - bh * 0.17, bw, bh * 0.07);
        ctx.font = `800 ${bh * 0.5}px Poppins, sans-serif`; ctx.textAlign = "center"; ctx.textBaseline = "middle";
        ctx.fillText("NOVA-BAND", 0, bh * 0.03);
      });
    }
    if (id === "kacamata") {
      at(f.cx, f.cy, () => {
        const d = Math.hypot(f.R.x - f.L.x, f.R.y - f.L.y), lw = d * 0.92, lh = d * 0.56;
        for (const sx of [-1, 1]) {
          const g = ctx.createLinearGradient(0, -lh / 2, 0, lh / 2);
          g.addColorStop(0, "#1b1e2e"); g.addColorStop(1, "#4a1830");
          ctx.fillStyle = g; rr(ctx, sx * d / 2 - lw / 2, -lh / 2, lw, lh, lh * 0.45); ctx.fill();
          ctx.lineWidth = d * 0.07; ctx.strokeStyle = "#ff4f63"; ctx.stroke();
          ctx.strokeStyle = "rgba(255,255,255,.55)"; ctx.lineWidth = d * 0.05;
          ctx.beginPath(); ctx.moveTo(sx * d / 2 - lw * 0.3, -lh * 0.18); ctx.lineTo(sx * d / 2 - lw * 0.05, -lh * 0.32); ctx.stroke();
        }
        ctx.strokeStyle = "#ff4f63"; ctx.lineWidth = d * 0.08;
        ctx.beginPath(); ctx.moveTo(-d * 0.05, -lh * 0.15); ctx.lineTo(d * 0.05, -lh * 0.15); ctx.stroke();
      });
    }
    if (id === "telinga") {
      for (const side of [-1, 1]) {
        const x = f.cx + side * W * 0.38 * Math.cos(f.ang) + ux * W * 0.78, y = f.cy + side * W * 0.38 * Math.sin(f.ang) + uy * W * 0.78;
        at(x, y, () => {
          ctx.rotate(side * (mirror ? -0.25 : 0.25));
          const e = W * 0.3;
          ctx.fillStyle = "#9b2335"; ctx.beginPath(); ctx.moveTo(-e * 0.6, e * 0.4); ctx.quadraticCurveTo(-e * 0.3, -e * 0.9, 0, -e); ctx.quadraticCurveTo(e * 0.3, -e * 0.9, e * 0.6, e * 0.4); ctx.fill();
          ctx.fillStyle = "#f6d7c2"; ctx.beginPath(); ctx.moveTo(-e * 0.35, e * 0.3); ctx.quadraticCurveTo(0, -e * 0.7, e * 0.35, e * 0.3); ctx.fill();
          ctx.fillStyle = "#3a0b14";
          for (const [sx, sy] of [[-0.45, 0.05], [0.42, -0.1], [0.1, -0.75]]) { ctx.beginPath(); ctx.arc(sx * e, sy * e, e * 0.09, 0, 7); ctx.fill(); }
        });
      }
    }
    if (id === "juara") {
      const x = f.cx - ux * W * 1.05, y = f.cy - uy * W * 1.05;
      at(x, y, () => {
        const r = W * 0.2;
        ctx.fillStyle = "#c8102e"; ctx.beginPath(); ctx.moveTo(-r * 1.1, -r * 2.4); ctx.lineTo(-r * 0.25, -r * 0.6); ctx.lineTo(r * 0.25, -r * 0.6); ctx.lineTo(r * 1.1, -r * 2.4); ctx.fill();
        const g = ctx.createRadialGradient(-r * 0.3, -r * 0.3, r * 0.1, 0, 0, r);
        g.addColorStop(0, "#fff3b0"); g.addColorStop(0.5, "#ffc93c"); g.addColorStop(1, "#c98a00");
        ctx.fillStyle = g; ctx.beginPath(); ctx.arc(0, 0, r, 0, 7); ctx.fill();
        ctx.fillStyle = "#8a5a00"; ctx.font = `800 ${r}px Poppins, sans-serif`; ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.fillText("1", 0, r * 0.05);
      });
    }
  }

  /* Nova photobombs: peek in, hop, then pose beside the face; loops every 9 s */
  mascot(ctx, mx, t) {
    const T = (t / 1000) % 9;
    const f = this.face;
    let im, x, y, h, rot = 0;
    if (T < 3) {                                       // peeks in from the right edge, wiggling
      im = NOVA.wink; h = 300;
      const k = Math.min(1, T / 0.6) * (T > 2.5 ? Math.max(0, (3 - T) / 0.5) : 1);
      x = OUT_W - 40 - k * 150; y = PH - 40; rot = -0.25 + 0.08 * Math.sin(T * 9);
    } else if (T < 6) {                                // hops along the bottom
      im = NOVA.run; h = 230;
      const u = (T - 3) / 3;
      x = 80 + u * (OUT_W - 160); y = PH - 10 - Math.abs(Math.sin(u * Math.PI * 4)) * 90; rot = 0.1 * Math.sin(u * 25);
    } else {                                           // poses beside your head (side away from the face)
      im = NOVA.hero; h = 360;
      const side = f && f.cx > OUT_W / 2 ? -1 : 1;
      const fx = f ? f.cx : OUT_W / 2;
      x = Math.max(110, Math.min(OUT_W - 110, fx + side * (f ? f.w * 1.15 : 220)));
      y = PH + 10 - 8 * Math.abs(Math.sin(T * 6)); rot = 0.06 * Math.sin(T * 4);
    }
    if (!im.complete || !im.naturalWidth) return;
    const w = h * im.naturalWidth / im.naturalHeight;
    ctx.save(); ctx.translate(mx(x), y); ctx.rotate(rot);
    ctx.shadowColor = "rgba(0,0,0,.35)"; ctx.shadowBlur = 18;
    ctx.drawImage(im, -w / 2, -h, w, h);
    ctx.restore();
  }

  ribbon(ctx) {
    const y = PH, h = OUT_H - PH;
    const g = ctx.createLinearGradient(0, y, OUT_W, y + h);
    g.addColorStop(0, "#6d0f22"); g.addColorStop(1, "#2a0a12");
    ctx.fillStyle = g; ctx.fillRect(0, y, OUT_W, h);
    ctx.fillStyle = "#ff4f63"; ctx.fillRect(0, y, OUT_W, 6);
    ctx.textBaseline = "alphabetic"; ctx.textAlign = "left";
    // logo first: the name gets whatever width is left of it
    ctx.textAlign = "right"; ctx.font = "800 32px Poppins, sans-serif";
    const lx = OUT_W - 28, ly = y + 70;
    const logoW = ctx.measureText("Nova-Band").width;
    const maxName = OUT_W - 28 - logoW - 32 - 28;
    ctx.textAlign = "left";
    const name = this.name || "Nama kamu";
    let fs = 50;
    ctx.font = `800 ${fs}px Poppins, sans-serif`;
    while (ctx.measureText(name).width > maxName && fs > 24) { fs -= 2; ctx.font = `800 ${fs}px Poppins, sans-serif`; }
    ctx.fillStyle = "#fff"; fitText(ctx, name, 32, y + 76, maxName);
    ctx.font = "500 26px Poppins, sans-serif"; ctx.fillStyle = "#f3e3d3";
    fitText(ctx, this.org || "Pengunjung pameran", 32, y + 120, maxName);
    ctx.textAlign = "right"; ctx.font = "800 32px Poppins, sans-serif";
    const wBand = ctx.measureText("Band").width, wDash = ctx.measureText("-").width;
    ctx.fillStyle = "#fff"; ctx.fillText("Band", lx, ly);
    ctx.fillStyle = "#ff4f63"; ctx.fillText("-", lx - wBand, ly);
    ctx.fillStyle = "#fff"; ctx.fillText("Nova", lx - wBand - wDash, ly);
    ctx.font = "500 20px Poppins, sans-serif"; ctx.fillStyle = "#d7c8cd";
    ctx.fillText(new Date().toLocaleDateString("id-ID", { day: "numeric", month: "short", year: "numeric" }), lx, y + 112);
  }

  /* 3-2-1, freeze Nova's pose, render the unmirrored photo */
  async shoot(onTick) {
    for (const n of ["3", "2", "1"]) { onTick && onTick(n); await sleep(800); }
    onTick && onTick("");
    this.frozenT = performance.now() - this.t0;
    const c = document.createElement("canvas"); c.width = OUT_W; c.height = OUT_H;
    this.render(c.getContext("2d"), false);
    this.frozenT = null;
    let q = 0.82, url = c.toDataURL("image/jpeg", q);
    while (url.length > 400000 && q > 0.4) { q -= 0.1; url = c.toDataURL("image/jpeg", q); }
    return url;
  }
}

/* draw text, cutting it with an ellipsis if it is still too wide */
function fitText(ctx, t, x, y, max) {
  let s = t;
  while (s.length > 1 && ctx.measureText(s).width > max) s = s.slice(0, -1);
  ctx.fillText(s === t ? t : s.slice(0, -1) + "…", x, y);
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
function rr(ctx, x, y, w, h, r) {
  ctx.beginPath(); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath();
}
