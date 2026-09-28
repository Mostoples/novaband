/* ============================================================
   Nova-Band — ISIF 2026 deck, neumorphic, built with pptxgenjs
   node deck/build-deck.js  ->  ppt/NovaBand_Deck_Neumorph.pptx
   (then: python deck/animate-deck.py adds Morph + entrance builds)

   Structure follows AQUENT_Deck_Neumorph: chapter pill, two-tone title,
   subtitle, brand top-right, page counter, raised neumorphic cards,
   animated 3D icons in raised buttons, a full-colour closing slide.

   Neumorphism in PowerPoint: one shape can only cast one outer shadow,
   so every raised surface is TWO identical shapes — the lower one casts
   the dark shadow down-right, the upper one the white highlight up-left.
   Cards are the SAME colour as the slide, which is also the colour the
   animated GIFs are matted on, so the GIFs sit on them with no edge.
   ============================================================ */
"use strict";
const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");

const ROOT = path.resolve(__dirname, "..");
const A = (...p) => path.join(__dirname, "assets", ...p);
const OUT = path.join(ROOT, "ppt", "NovaBand_Deck_Neumorph.pptx");

// ---------------------------------------------------------------- palette
const BG = "EEE8E9";     // neumorphic surface == GIF matte colour
const INK = "1C1215";
const INK2 = "5D5256";
const INK3 = "948A8D";
const RED = "7B2021";
const DEEP = "4B070F";
const MID = "962A2C";
const ROSE = "C9A3A3";
const CREAM = "F3E3D3";
const TRACK = "DCD2D3";
const DARK_SH = "B09A9D";
const FONT = "Segoe UI";
const FONT_B = "Segoe UI Black";
const TOTAL = 32;

const W = 13.333, H = 7.5, MX = 0.6;

// ---------------------------------------------------------------- image sizes
function imgSize(file) {
  const b = fs.readFileSync(file);
  if (b.slice(1, 4).toString() === "PNG") return [b.readUInt32BE(16), b.readUInt32BE(20)];
  if (b.slice(0, 3).toString() === "GIF") return [b.readUInt16LE(6), b.readUInt16LE(8)];
  let i = 2;                                   // JPEG: walk to the SOF marker
  while (i < b.length) {
    const m = b[i + 1], len = b.readUInt16BE(i + 2);
    if (m >= 0xc0 && m <= 0xc3) return [b.readUInt16BE(i + 7), b.readUInt16BE(i + 5)];
    i += 2 + len;
  }
  throw new Error("unknown image " + file);
}

// ---------------------------------------------------------------- deck
const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";
pres.author = "Team Nova-Band · SMA Negeri 1 Surakarta";
pres.company = "Nova-Band";
pres.title = "Nova-Band — AIoT Upper-Arm Wearable (ISIF 2026)";
const S = pres.shapes;

let uid = 0;
// slides number themselves in order, so slides can be inserted freely
let SLIDE_NO = 0;
function newSlide() { SLIDE_NO++; return pres.addSlide(); }
const nm = (order) => `anim_${String(order).padStart(2, "0")}_${++uid}`;

// ---------------------------------------------------------------- primitives
function raised(slide, x, y, w, h, o = {}) {
  const r = o.r ?? 0.28, bg = o.bg ?? BG, dark = o.dark ?? DARK_SH, light = o.light ?? "FFFFFF";
  const shape = o.shape ?? S.ROUNDED_RECTANGLE;
  const d = o.depth ?? 1;
  const base = { x, y, w, h, fill: { color: bg }, line: { type: "none" } };
  if (shape === S.ROUNDED_RECTANGLE) base.rectRadius = r;
  slide.addShape(shape, { ...base, objectName: o.order != null ? nm(o.order) : o.name ? o.name + "_a" : undefined,
    shadow: { type: "outer", color: dark, opacity: o.darkOp ?? 0.55, blur: 14 * d, offset: 6 * d, angle: 45 } });
  slide.addShape(shape, { ...base, objectName: o.order != null ? nm(o.order) : o.name ? o.name + "_b" : undefined,
    shadow: { type: "outer", color: light, opacity: o.lightOp ?? 0.95, blur: 14 * d, offset: 6 * d, angle: 225 } });
}

function inset(slide, x, y, w, h, o = {}) {
  const r = o.r ?? 0.18;
  const base = { x, y, w, h, fill: { color: o.bg ?? "E8E1E2" }, line: { type: "none" },
    objectName: o.order != null ? nm(o.order) : undefined,
    shadow: { type: "inner", color: o.dark ?? "A8898D", opacity: 0.55, blur: 7, offset: 3, angle: 45 } };
  if ((o.shape ?? S.ROUNDED_RECTANGLE) === S.ROUNDED_RECTANGLE) base.rectRadius = r;
  slide.addShape(o.shape ?? S.ROUNDED_RECTANGLE, base);
}

function text(slide, t, o) {
  const opt = {
    x: o.x, y: o.y, w: o.w, h: o.h, fontFace: o.font ?? FONT, fontSize: o.size ?? 12,
    color: o.color ?? INK, bold: !!o.bold, italic: !!o.italic, align: o.align ?? "left",
    valign: o.valign ?? "top", margin: 0, isTextBox: true, lineSpacingMultiple: o.lsm ?? 1.08,
  };
  if (o.charSpacing) opt.charSpacing = o.charSpacing;
  if (o.order != null) opt.objectName = nm(o.order);
  else if (o.name) opt.objectName = o.name;
  if (o.paraSpaceAfter) opt.paraSpaceAfter = o.paraSpaceAfter;
  slide.addText(t, opt);
}

function img(slide, file, x, y, w, h, o = {}) {
  // contain the image inside the box, centred
  const [iw, ih] = imgSize(file);
  const k = Math.min(w / iw, h / ih);
  const dw = iw * k, dh = ih * k;
  const opt = { path: file, x: x + (w - dw) / 2, y: y + (h - dh) / 2, w: dw, h: dh, altText: o.alt ?? altFor(file) };
  if (o.align === "bottom") opt.y = y + h - dh;
  if (o.align === "top") opt.y = y;
  if (o.transparency) opt.transparency = o.transparency;
  if (o.order != null) opt.objectName = nm(o.order);
  else if (o.name) opt.objectName = o.name;
  slide.addImage(opt);
  return opt;
}
// Alt text for screen readers; without it pptxgenjs writes the local file path.
const ALT = {
  "product-side": "Nova-Band upper-arm band, side view", "product-front": "Nova-Band module with PPG LEDs, front view",
  "app-phone": "Nova-Band app on a smartphone", team: "The six members of Team Nova-Band", testing: "Team members during testing",
  "logo-reka": "REKA Mersif logo", "crest-sman1": "SMA Negeri 1 Surakarta crest", "logo-uns": "Universitas Sebelas Maret logo",
  "logo-mersif-enuma": "Mersif Academy and Enuma Technology logos", "device-on-arm": "3D render of Nova-Band worn on an upper arm",
  "device-exploded": "Exploded 3D view of the Nova-Band module layers", "device-spin": "Animated 3D Nova-Band turning, LEDs pulsing",
  "p-home": "Nova-Band app home screen", "p-live": "Nova-Band app live session screen", "p-ready": "Nova-Band app readiness screen",
  "p-comm": "Nova-Band community dashboard screen", "corner-wave": "Decorative animated dotted wave",
  "corner-rings": "Decorative animated rings", "corner-rings-wine": "Decorative animated rings",
  "orn-pills": "Decorative floating capsules",
  "case-sketch": "LibreCAD drawing of the prototype case: top, front, end and section views with dimensions",
  "ui-live": "Band screen: live heart rate, 3D heart and PPG wave", "ui-run": "Band screen: run time, pace, distance and energy",
  "ui-ready": "Band screen: readiness ring with HRV, sleep and load", "ui-link": "Band screen: pairing page with QR code to the web app",
  "ui-boot": "Band screen: splash with the Nova-Band wordmark", "app-phone": "Nova-Band web app on a phone",
  "gym-orbit": "Rendered gym: a runner on a treadmill wearing the Nova-Band pod on the upper arm",
  "gym-arm": "Rendered close-up of the pod on the runner's upper arm", "gym-bench": "Rendered pod and phone on a gym bench",
  "gym-arm-43": "Rendered close-up of the pod on the runner's upper arm",
  "pod-hero": "3D render of the Nova-Band prototype pod", "gym-wide": "Rendered gym interior with a runner on a treadmill", "orn-ring": "Decorative spinning ring", "ill-anxiety": "Illustration: worried-well anxiety", "ill-harm": "Illustration: physical harm",
  "ill-overtraining": "Illustration: overtraining risk", "ill-data": "Illustration: data inaccuracy",
};
function altFor(file) {
  const base = path.basename(file).replace(/\.(gif|png|jpg)$/, "").replace(/-wine$/, "");
  if (base in ALT) return ALT[base];
  return "Animated 3D icon: " + base.replace(/-/g, " ");
}
const gif = (n) => A("anim", n + ".gif");
const proto = (n) => A("proto", n);
const has = (f) => fs.existsSync(f);
const png = (n) => A("static", n + ".png");
const photo = (n) => {
  const p = A("img", n + ".png");
  return fs.existsSync(p) ? p : A("img", n + ".jpg");
};

function iconBtn(slide, name, cx, cy, d, order, o = {}) {
  raised(slide, cx - d / 2, cy - d / 2, d, d, { shape: S.OVAL, order, depth: o.depth ?? 0.8, bg: o.bg, dark: o.dark, light: o.light });
  img(slide, o.static ? png(name) : gif(name), cx - d * 0.35, cy - d * 0.35, d * 0.70, d * 0.70, { order });
}

function badge(slide, n, cx, cy, d, order, o = {}) {
  slide.addText(String(n), {
    shape: S.OVAL, x: cx - d / 2, y: cy - d / 2, w: d, h: d, fill: { color: o.fill ?? RED },
    color: o.color ?? "FFFFFF", fontFace: FONT, bold: true, fontSize: o.size ?? 11, align: "center",
    valign: "middle", margin: 0, isTextBox: true, objectName: nm(order),
    shadow: { type: "outer", color: DEEP, opacity: 0.3, blur: 6, offset: 2, angle: 90 },
  });
}

function pill(slide, label, x, y, o = {}) {
  const size = o.size ?? 9;
  const w = o.w ?? (0.36 + label.length * size * 0.0118);
  const h = o.h ?? 0.34;
  const nameBase = o.name;
  raised(slide, x, y, w, h, { r: h / 2, depth: 0.55, name: nameBase, order: o.order });
  slide.addText(label, {
    x, y, w, h, fontFace: FONT, fontSize: size, bold: true, color: o.color ?? RED, charSpacing: o.spacing ?? 2,
    align: "center", valign: "middle", margin: 0, isTextBox: true,
    objectName: o.order != null ? nm(o.order) : nameBase ? nameBase + "_t" : undefined,
  });
  return w;
}

function brand(slide, dark = false) {
  slide.addText("N", {
    shape: S.ROUNDED_RECTANGLE, rectRadius: 0.1, x: 10.72, y: 0.42, w: 0.42, h: 0.42,
    fill: { color: dark ? "FFFFFF" : RED }, color: dark ? RED : "FFFFFF", fontFace: FONT_B, fontSize: 15,
    align: "center", valign: "middle", margin: 0, isTextBox: true, objectName: "!!brandMark",
    shadow: { type: "outer", color: dark ? "33050A" : DEEP, opacity: 0.35, blur: 8, offset: 3, angle: 90 },
  });
  slide.addText([
    { text: "Nova", options: { color: dark ? "FFFFFF" : INK } },
    { text: "-", options: { color: dark ? CREAM : RED } },
    { text: "Band", options: { color: dark ? "FFFFFF" : INK } },
  ], { x: 11.22, y: 0.42, w: 1.55, h: 0.42, fontFace: FONT, bold: true, fontSize: 17, valign: "middle",
    margin: 0, isTextBox: true, objectName: "!!brandTxt" });
}

function page(slide, n, dark = false) {
  n = SLIDE_NO;
  text(slide, `${String(n).padStart(2, "0")} / ${TOTAL}`, {
    x: 11.73, y: 7.0, w: 1.0, h: 0.28, size: 9.5, color: dark ? "E9C9C9" : INK3, align: "right", name: "!!page",
  });
}

function corner(slide) {
  // the live dotted wave, bleeding off the bottom-left corner behind the content
  img(slide, gif("corner-wave"), -1.05, 5.72, 3.9, 2.4, { transparency: 30, name: "!!corner" });
}

function header(slide, chapter, t1, t2, sub, n, o = {}) {
  slide.background = { color: BG };
  if (!o.noCorner) corner(slide);
  pill(slide, chapter, MX, 0.42, { name: "!!pill" });
  text(slide, [
    { text: t1, options: { color: INK } },
    { text: t2, options: { color: RED } },
  ], { x: MX, y: 0.86, w: 9.8, h: 0.72, size: 33, bold: true, name: "!!title", valign: "middle" });
  if (sub) text(slide, sub, { x: MX, y: 1.6, w: 10, h: 0.36, size: 13.5, color: INK2, name: "!!sub" });
  brand(slide);
  page(slide, n);
}

function notes(slide, t) { slide.addNotes(t); }

// ============================================================ 01 COVER
{
  const s = newSlide();
  s.background = { color: BG };
  img(s, gif("corner-rings"), 10.55, -1.45, 3.5, 3.5, { name: "!!corner" });
  text(s, "ISIF 2026  ·  SMA NEGERI 1 SURAKARTA", { x: 0.7, y: 0.55, w: 6, h: 0.3, size: 10, bold: true, color: RED, charSpacing: 2, order: 1 });
  pill(s, "AIoT UPPER-ARM WEARABLE", 0.7, 1.0, { order: 2 });
  text(s, [
    { text: "Nova", options: { color: INK } }, { text: "-", options: { color: RED } }, { text: "Band", options: { color: INK } },
  ], { x: 0.62, y: 1.42, w: 6.8, h: 1.25, size: 68, font: FONT_B, order: 3, valign: "middle", name: "!!title" });
  text(s, "An AIoT-driven upper-arm wearable for real-time physiological monitoring and running performance",
    { x: 0.7, y: 2.72, w: 6.2, h: 0.95, size: 17, bold: true, order: 4, lsm: 1.12 });
  text(s, "TEAM NOVA-BAND", { x: 0.7, y: 3.86, w: 4, h: 0.26, size: 9.5, bold: true, color: RED, charSpacing: 2, order: 5 });
  text(s, "Maheswara Nala Wisadewa  ·  Almira Edgina Nareswari Haryadi  ·  Azra Daniswara Tyandaru  ·  Dela Astiara  ·  Rizkyta Aufa Mutiagassania  ·  Satriya Javas Wibisono",
    { x: 0.7, y: 4.14, w: 6.2, h: 0.7, size: 11, color: INK2, order: 5, lsm: 1.2 });
  let x = 0.7;
  for (const t of ["PPG + IMU", "EDGE FFT · ESP32", "EARLY WARNING"]) x += pill(s, t, x, 5.0, { order: 6, size: 8.5 }) + 0.18;
  raised(s, 0.6, 5.62, 6.4, 1.33, { order: 7 });
  text(s, "IN COLLABORATION WITH", { x: 0.88, y: 5.78, w: 4, h: 0.24, size: 8.5, bold: true, color: INK3, charSpacing: 2, order: 7 });
  const logos = [["logo-reka", 1.05], ["crest-sman1", 0.55], ["logo-uns", 1.0], ["logo-mersif-enuma-light", 2.3]];
  let lx = 0.88;
  for (const [n, w] of logos) { const o = img(s, photo(n), lx, 6.12, w, 0.62, { order: 7 }); lx = o.x + o.w + 0.34; }
  raised(s, 7.45, 1.35, 4.95, 4.95, { shape: S.OVAL, order: 2, depth: 1.5 });
  // GIFs only ever sit on flat surface: the circle's interior, well inside its rim
  img(s, gif("device-spin"), 8.25, 2.25, 3.35, 3.15, { order: 3 });
  img(s, gif("orn-pills"), 12.05, 5.8, 1.1, 1.1, { order: 4 });
  pill(s, "UPPER-ARM FIT  ·  PPG + IMU  ·  AIoT", 8.28, 6.47, { order: 5, size: 8.5, color: INK2 });
  notes(s, "Nova-Band: an AIoT-driven upper-arm wearable for real-time physiological monitoring and running performance. Team Nova-Band, SMA Negeri 1 Surakarta, ISIF 2026.");
}

// ============================================================ 02 AGENDA
{
  const s = newSlide();
  header(s, "AGENDA", "What we will ", "cover", "Five chapters, from the running-injury problem to evidence and market.", 2);
  raised(s, 1.05, 2.45, 4.1, 4.1, { shape: S.OVAL, order: 1, depth: 1.3 });
  img(s, png("device-on-arm"), 1.25, 3.2, 3.7, 2.6, { order: 1 });
  img(s, gif("orn-ring"), 4.85, 1.98, 0.95, 0.95, { order: 2 });
  const rows = [
    ["warning", "The running problem", "Sedentary lifestyles, overtraining and unreliable wrist data."],
    ["ai-network", "The Nova-Band system", "Upper-arm fit, PPG + IMU, edge FFT and an AI early warning."],
    ["chip", "Product & hardware", "Module anatomy, 3D digital twin and specifications."],
    ["smartphone", "Software & AI", "The runner app, Readiness Score and the community dashboard."],
    ["bar-chart", "Evidence & market", "MAPE and SUS results, market size and projection."],
  ];
  rows.forEach(([ic, t, d], i) => {
    const y = 2.2 + i * 0.96, x = 5.9, o = 2 + i;
    raised(s, x, y, 6.83, 0.84, { r: 0.42, order: o, depth: 0.8 });
    iconBtn(s, ic, x + 0.5, y + 0.42, 0.66, o);
    text(s, String(i + 1).padStart(2, "0"), { x: x + 0.98, y: y + 0.13, w: 0.7, h: 0.58, size: 21, font: FONT_B, color: RED, valign: "middle", order: o });
    text(s, t, { x: x + 1.72, y: y + 0.1, w: 4.9, h: 0.34, size: 14.5, bold: true, order: o });
    text(s, d, { x: x + 1.72, y: y + 0.45, w: 4.95, h: 0.3, size: 10.5, color: INK2, order: o });
  });
  notes(s, "Five chapters: the problem, the Nova-Band system, product and hardware, software and AI, and evidence with market.");
}

// ============================================================ 03 BACKGROUND
{
  const s = newSlide();
  header(s, "01 · THE RUNNING PROBLEM", "Back", "ground", "Physical inactivity is a public-health problem — and running is where many people start.", 3);
  const cards = [
    ["user", "37.4%", "of Indonesians aged ≥10 are not active enough", "Below the recommended level of physical activity.  SKI 2023"],
    ["heart", "3 Million+", "deaths a year linked to physical inactivity", "One of the leading global risk factors for premature death.  WHO 2020"],
    ["footsteps", "1–42%", "MAPE of consumer wearables in step counting", "Accuracy varies widely between devices.  Al-Maroof et al. 2024"],
    ["flame", "15–44%", "MAPE in energy / calorie estimation", "Even wider error on calories burned.  Al-Maroof et al. 2024"],
  ];
  cards.forEach(([ic, n, l, d], i) => {
    const x = i % 2 ? 6.78 : MX, y = i < 2 ? 2.22 : 4.64, o = 1 + i;
    raised(s, x, y, 5.95, 2.2, { order: o });
    iconBtn(s, ic, x + 0.95, y + 1.1, 1.18, o);
    text(s, n, { x: x + 1.82, y: y + 0.22, w: 3.95, h: 0.68, size: 31, font: FONT_B, color: RED, valign: "middle", order: o });
    text(s, l, { x: x + 1.82, y: y + 0.92, w: 3.95, h: 0.56, size: 12.5, bold: true, order: o, valign: "top" });
    text(s, d, { x: x + 1.82, y: y + 1.55, w: 3.95, h: 0.5, size: 10, color: INK2, order: o });
  });
  notes(s, "37.4% of Indonesians aged 10+ do not meet physical-activity recommendations (SKI 2023). Consumer wearables show MAPE of 1–42% for steps and 15–44% for calories.");
}

// ============================================================ 04 MEET THE PROBLEM
{
  const s = newSlide();
  header(s, "01 · THE RUNNING PROBLEM", "Meet the ", "problem", "Four ways today's running culture — and wrist wearables — fail runners.", 4);
  const items = [
    ["ill-anxiety", "Worried-well anxiety", "Excessive anxiety about digital metrics on the watch screen."],
    ["ill-harm", "Physical harm", "Runners ignore pain and extreme fatigue to hit on-screen targets."],
    ["ill-overtraining", "Overtraining risk", "Pushing beyond physical limits, driven by FoMO and lifestyle pressure."],
    ["ill-data", "Data inaccuracy", "Wrist sensors lose accuracy exactly when running gets intense."],
  ];
  items.forEach(([f, t, d], i) => {
    const x = MX + i * 3.08, y = 2.22, o = 1 + i;
    raised(s, x, y, 2.88, 4.63, { order: o });
    inset(s, x + 0.2, y + 0.2, 2.48, 2.6, { order: o, bg: "EAE3E4" });
    img(s, photo(f), x + 0.35, y + 0.32, 2.18, 2.36, { order: o });
    badge(s, String(i + 1).padStart(2, "0"), x + 0.42, y + 0.42, 0.42, o, { size: 9 });
    text(s, t, { x: x + 0.25, y: y + 3.02, w: 2.4, h: 0.42, size: 15, bold: true, order: o });
    text(s, d, { x: x + 0.25, y: y + 3.48, w: 2.4, h: 0.95, size: 10.8, color: INK2, order: o });
  });
  notes(s, "Worried-well anxiety, physical harm, overtraining risk and data inaccuracy.");
}

// ============================================================ 05 RUNNER INJURIES
{
  const s = newSlide();
  header(s, "01 · THE RUNNING PROBLEM", "Trends in ", "runner injuries", "The injury pattern has shifted toward heavier soft-tissue and tendon damage.", 5);
  raised(s, MX, 2.22, 5.6, 4.63, { order: 1 });
  iconBtn(s, "spring-tendon", MX + 0.95, 3.07, 1.3, 1);
  text(s, "Running is booming — so is overtraining", { x: MX + 1.85, y: 2.55, w: 3.5, h: 1.0, size: 16, bold: true, order: 1, valign: "middle" });
  text(s, "Among urban runners, lifestyle pressure, commodification and Fear of Missing Out push people past their physical limits. Injuries used to be dominated by kneecap pain; they now shift to heavier soft tissue and tendons.",
    { x: MX + 0.35, y: 3.95, w: 4.9, h: 1.55, size: 11.5, color: INK2, order: 2, lsm: 1.18 });
  inset(s, MX + 0.35, 5.72, 4.9, 0.82, { order: 3 });
  text(s, [{ text: "Two main predictors  ", options: { bold: true, color: RED } }, { text: "excess mileage  ·  previous injury history", options: { color: INK } }],
    { x: MX + 0.6, y: 5.72, w: 4.5, h: 0.82, size: 11.5, valign: "middle", order: 3 });
  const rows = [
    ["Achilles tendinopathy", "Tendon overload behind the ankle"],
    ["Calf strain", "Gastrocnemius injury under repeated push-off"],
    ["Hamstring & quadriceps strain", "Thigh muscles overstretched without adequate warm-up"],
    ["Iliotibial Band Syndrome (ITBS)", "Outer-knee pain linked to high training load"],
    ["Knee meniscus tear", "Cartilage damage from accumulated impact"],
  ];
  rows.forEach(([t, d], i) => {
    const y = 2.22 + i * 0.965, x = 6.5, o = 2 + i;
    raised(s, x, y, 6.23, 0.8, { r: 0.4, order: o, depth: 0.75 });
    badge(s, i + 1, x + 0.42, y + 0.4, 0.44, o, { size: 11 });
    text(s, t, { x: x + 0.85, y: y + 0.1, w: 5.2, h: 0.32, size: 13.5, bold: true, order: o });
    text(s, d, { x: x + 0.85, y: y + 0.43, w: 5.2, h: 0.28, size: 10.5, color: INK2, order: o });
  });
  notes(s, "Overtraining shifts injuries to soft tissue and tendons: Achilles tendinopathy, calf strain, hamstring/quadriceps, ITBS and meniscus tears. Excess mileage and previous injury are the two main predictors.");
}

// ============================================================ 06 RESEARCH QUESTIONS
{
  const s = newSlide();
  header(s, "01 · THE RUNNING PROBLEM", "Research ", "questions", "Two problems formulated, two objectives set.", 6);
  const col = (x, label, icon, items, o0) => {
    text(s, label, { x, y: 2.18, w: 4, h: 0.28, size: 9.5, bold: true, color: RED, charSpacing: 2, order: o0 });
    items.forEach((t, i) => {
      const y = 2.55 + i * 2.2, o = o0 + i;
      raised(s, x, y, 5.95, 2.0, { order: o });
      badge(s, i + 1, x + 0.55, y + 0.55, 0.52, o, { size: 13 });
      text(s, t, { x: x + 1.05, y: y + 0.3, w: 3.55, h: 1.45, size: 12.5, order: o, lsm: 1.18, valign: "middle" });
      iconBtn(s, icon, x + 5.05, y + 1.0, 1.12, o);
    });
  };
  col(MX, "PROBLEM FORMULATION", "magnifier", [
    "How do motion artifacts from arm swing affect the accuracy of heart-rate and motion data in wrist-worn wearables used by runners?",
    "How can Nova-Band be designed and tested to extract an accurate Readiness Score that helps prevent soft-tissue injury and cardiovascular collapse?",
  ], 1);
  col(6.78, "RESEARCH OBJECTIVES", "target-tiers", [
    "Design Nova-Band as an upper-arm wearable that mechanically stabilises the sensors to minimise motion artifacts and produce accurate PPG and IMU data.",
    "Evaluate its effectiveness through MAPE accuracy testing and SUS usability testing in extracting a reliable Readiness Score.",
  ], 3);
  notes(s, "Problem formulation and research objectives, from the ISIF material.");
}

// ============================================================ 07 STATE OF THE ART
{
  const s = newSlide();
  header(s, "01 · THE RUNNING PROBLEM", "State of the ", "art", "What the literature shows — and the gap Nova-Band closes.", 7);
  const refs = [
    ["Siradj", "2016", "Wearables help runners track physical activity practically and independently for self-motivation.",
      "Consumer accuracy is low: MAPE 1–42% for steps, 15–44% for calories."],
    ["Al-Maroof et al.", "2024", "Smartwatches enable continuous tracking of physiological metrics and self-monitoring interventions.",
      "Reliability and validity vary across devices, especially at high intensity."],
    ["Moghaddam et al.", "2025", "Placement studies show wrist-worn devices are practical for everyday heart-rate monitoring.",
      "Wrist PPG is highly vulnerable to motion artifacts during intense running."],
    ["McGrath & Doyle et al.", "2023", "IMU sensors with machine learning estimate ground reaction force and running kinematics precisely.",
      "Largely lab-grade — not yet integrated for real-time daily use by runners."],
  ];
  refs.forEach(([a, yr, f, g], i) => {
    const x = MX + i * 3.08, y = 2.22, o = 1 + i;
    raised(s, x, y, 2.88, 3.55, { order: o });
    s.addText([{ text: a, options: { bold: true, breakLine: true } }, { text: yr, options: { fontSize: 9.5, color: "F3D6D6" } }], {
      shape: S.ROUNDED_RECTANGLE, rectRadius: 0.26, x: x + 0.2, y: y + 0.2, w: 2.48, h: 0.62, fill: { color: RED },
      color: "FFFFFF", fontFace: FONT, fontSize: 12, align: "center", valign: "middle", margin: 0, isTextBox: true,
      objectName: nm(o), shadow: { type: "outer", color: DEEP, opacity: 0.3, blur: 8, offset: 3, angle: 90 },
    });
    text(s, f, { x: x + 0.25, y: y + 0.98, w: 2.38, h: 1.18, size: 10.5, color: INK2, order: o, lsm: 1.12 });
    text(s, "↓", { x: x + 1.19, y: y + 2.1, w: 0.5, h: 0.3, size: 14, bold: true, color: RED, align: "center", order: o });
    inset(s, x + 0.2, y + 2.42, 2.48, 0.95, { order: o });
    text(s, [{ text: "Gap  ", options: { bold: true, color: RED } }, { text: g, options: { color: INK } }],
      { x: x + 0.33, y: y + 2.47, w: 2.22, h: 0.85, size: 9.8, order: o, valign: "middle", lsm: 1.08 });
  });
  raised(s, MX, 5.97, 12.13, 0.9, { order: 5 });
  img(s, gif("shield"), MX + 0.2, 6.02, 0.8, 0.8, { order: 5 });
  text(s, "Nova-Band's answer", { x: MX + 1.1, y: 6.1, w: 2.2, h: 0.64, size: 13, bold: true, color: RED, valign: "middle", order: 5 });
  const ans = ["Upper-arm placement reduces motion artifacts", "PPG, IMU and ESP32 integrated: cardio + biomechanics",
    "IoT dashboard alerts organisers early to prevent overtraining"];
  ans.forEach((t, i) => text(s, [{ text: "✓  ", options: { color: RED, bold: true } }, { text: t }], {
    x: 3.45 + i * 3.1, y: 6.1, w: 2.95, h: 0.64, size: 10.5, valign: "middle", order: 6 + i,
  }));
  notes(s, "Four prior studies and their gaps; Nova-Band answers with upper-arm placement, integrated PPG + IMU + ESP32 and an IoT early-warning dashboard.");
}

// ============================================================ 08 THE SOLUTION
{
  const s = newSlide();
  header(s, "02 · THE NOVA-BAND SYSTEM", "The ", "solution", "Four layers of protection in one band.", 8);
  raised(s, MX, 2.22, 4.1, 4.63, { order: 1 });
  img(s, photo("app-phone"), MX + 0.3, 2.4, 3.5, 4.3, { order: 1 });
  const cards = [
    ["ai-network", "AI & IoT Synergy", "Sensor readings from the band (IoT) are processed continuously by AI into physiological insight."],
    ["shield", "Shared Safety Net", "A dual-layer system: alerts reach the runner and the supervisor at the same time to prevent collapse."],
    ["bell", "Biological Early Warning", "Proactive, instant alerts the moment a runner starts pushing past the body's safe limits."],
    ["spring-tendon", "Soft Network Load", "IMU kinematic tracking of mechanical stress on muscles and tendons — against Achilles tendinopathy & ITBS."],
  ];
  cards.forEach(([ic, t, d], i) => {
    const x = i % 2 ? 8.94 : 4.95, y = i < 2 ? 2.22 : 4.64, o = 2 + i;
    raised(s, x, y, 3.79, 2.2, { order: o });
    iconBtn(s, ic, x + 0.72, y + 0.72, 1.0, o);
    text(s, t, { x: x + 1.4, y: y + 0.38, w: 2.25, h: 0.7, size: 14.5, bold: true, order: o, valign: "middle" });
    text(s, d, { x: x + 0.3, y: y + 1.33, w: 3.2, h: 0.78, size: 10.3, color: INK2, order: o, lsm: 1.1 });
  });
  notes(s, "AI & IoT synergy, Shared Safety Net, Biological Early Warning and Soft Network Load.");
}

// ============================================================ 09 OUR NOVELTY
{
  const s = newSlide();
  header(s, "02 · THE NOVA-BAND SYSTEM", "Our ", "novelty", "Three things a wrist wearable does not do together.", 9);
  const cards = [
    [png("device-on-arm"), "Upper-arm fit", "Worn away from the arm's largest swing, so the optics stay pressed to the skin and motion artifacts drop — a mechanical fix first."],
    [gif("chip"), "Edge FFT on the ESP32", "A Fast Fourier Transform on the device separates heart-rate frequencies from cadence noise before any data leaves the band."],
    [gif("map-pin"), "Shared safety net", "Data syncs to a community dashboard, so an event supervisor sees an alert at the same moment the runner does."],
  ];
  cards.forEach(([f, t, d], i) => {
    const x = MX + i * 4.115, y = 2.22, o = 1 + i;
    raised(s, x, y, 3.9, 4.63, { order: o });
    inset(s, x + 0.25, y + 0.25, 3.4, 2.4, { order: o, bg: BG });
    img(s, f, x + 0.5, y + 0.47, 2.9, 1.96, { order: o });
    badge(s, i + 1, x + 0.55, y + 0.55, 0.44, o);
    text(s, t, { x: x + 0.3, y: y + 2.9, w: 3.3, h: 0.42, size: 16, bold: true, order: o });
    text(s, d, { x: x + 0.3, y: y + 3.38, w: 3.3, h: 1.1, size: 10.8, color: INK2, order: o, lsm: 1.15 });
  });
  notes(s, "Upper-arm fit, edge FFT on the ESP32 and a shared community safety net.");
}

// ============================================================ 10 HOW IT WORKS
{
  const s = newSlide();
  header(s, "02 · THE NOVA-BAND SYSTEM", "How Nova-Band ", "protects runners", "From a beam of light on the skin to an alert on the supervisor's screen.", 10);
  const steps = [
    ["led-sensor", "Acquire", "PPG and IMU sampled together on the upper arm."],
    ["microcontroller", "Filter", "FFT on the ESP32 strips cadence noise from the signal."],
    ["ai-network", "Analyse", "AI turns clean signals into a Readiness Score."],
    ["smartphone", "Notify", "Bluetooth streams metrics to the runner's app."],
    ["wifi-iot", "Protect", "The IoT dashboard watches the whole group."],
  ];
  const cw = 12.13 / 5;
  steps.forEach(([ic, t, d], i) => {
    const cx = MX + cw * (i + 0.5), o = 1 + i;
    iconBtn(s, ic, cx, 3.05, 1.55, o, { depth: 1.1 });
    badge(s, i + 1, cx - 0.55, 2.47, 0.42, o);
    text(s, t, { x: cx - 1.1, y: 4.05, w: 2.2, h: 0.38, size: 15, bold: true, align: "center", order: o });
    text(s, d, { x: cx - 1.05, y: 4.45, w: 2.1, h: 0.75, size: 10.5, color: INK2, align: "center", order: o });
    if (i < 4) text(s, "›", { x: cx + cw / 2 - 0.2, y: 2.72, w: 0.4, h: 0.62, size: 30, bold: true, color: RED, align: "center", valign: "middle", order: o });
  });
  raised(s, MX, 5.72, 12.13, 1.13, { order: 6 });
  iconBtn(s, "heart", MX + 0.72, 6.285, 0.86, 6, { depth: 0.7 });
  text(s, "An alert reaches two people at once", { x: MX + 1.4, y: 5.86, w: 6, h: 0.36, size: 14, bold: true, color: RED, order: 6 });
  text(s, "When a runner crosses a safe limit, the warning goes to the runner and to the event supervisor simultaneously — the Shared Safety Net.",
    { x: MX + 1.4, y: 6.24, w: 10.4, h: 0.5, size: 11, color: INK2, order: 6 });
  notes(s, "Acquire, filter, analyse, notify, protect.");
}

// ============================================================ 11 PPG
{
  const s = newSlide();
  header(s, "02 · THE NOVA-BAND SYSTEM", "Hardware operation ", "(PPG)", "Photoplethysmography: every heartbeat changes how much light the skin gives back.", 11);
  const steps = [
    ["led-sensor", "LED Sensor", "Green LEDs shine into the skin of the upper arm."],
    ["blood-cells", "Blood Absorbs Light", "Blood volume changes with each beat, absorbing light."],
    ["photodetector", "Photodetector", "Captures the light reflected back from the skin."],
    ["microcontroller", "Microcontroller", "The ESP32 filters the signal with an on-device FFT."],
    ["heart", "Heart Beats", "Becomes real-time BPM and feeds the Readiness Score."],
  ];
  steps.forEach(([ic, t, d], i) => {
    const x = MX + i * 2.46, y = 2.22, o = 1 + i;
    raised(s, x, y, 2.26, 3.2, { order: o });
    img(s, gif(ic), x + 0.4, y + 0.38, 1.46, 1.46, { order: o });
    badge(s, i + 1, x + 0.36, y + 0.36, 0.4, o);
    text(s, t, { x: x + 0.12, y: y + 2.0, w: 2.02, h: 0.4, size: 13, bold: true, align: "center", order: o });
    text(s, d, { x: x + 0.15, y: y + 2.42, w: 1.96, h: 0.7, size: 9.8, color: INK2, align: "center", order: o });
    if (i < 4) badge(s, "›", x + 2.36, y + 1.1, 0.34, o, { size: 13 });
  });
  raised(s, MX, 5.65, 12.13, 1.2, { order: 6 });
  text(s, "What the band measures", { x: MX + 0.35, y: 5.78, w: 5, h: 0.34, size: 13.5, bold: true, order: 6 });
  text(s, "An LED shines into the skin; with every heartbeat the blood volume below changes, and so does the light that returns to the photodetector. The ESP32 filters that signal and turns it into heart rate.",
    { x: MX + 0.35, y: 6.12, w: 8.3, h: 0.66, size: 10.8, color: INK2, order: 6 });
  inset(s, 9.55, 5.85, 2.95, 0.8, { order: 7 });
  text(s, [{ text: "2.5–3.5%  ", options: { font: FONT_B, fontFace: FONT_B, color: RED, fontSize: 18 } }, { text: "MAPE", options: { bold: true, color: INK2 } }],
    { x: 9.55, y: 5.85, w: 2.95, h: 0.8, size: 11, align: "center", valign: "middle", order: 7 });
  notes(s, "LED sensor, blood absorbs light, photodetector, microcontroller, heart beats.");
}

// ============================================================ 12 IMU
{
  const s = newSlide();
  header(s, "02 · THE NOVA-BAND SYSTEM", "Hardware operation ", "(IMU)", "Three motion sensors that watch for emergencies.", 12);
  const cards = [
    ["accelerometer", "Accelerometer", "FALLS & COLLAPSE", "Detects drastic changes in motion speed to identify sudden falls or physical collapse."],
    ["gyroscope", "Gyroscope", "POSTURE & BALANCE", "Monitors body posture and tilt to detect loss of balance, dizziness or unsteady movement."],
    ["magnetometer", "Magnetometer", "ORIENTATION", "Determines precise body orientation to assist spatial tracking in emergency situations."],
  ];
  cards.forEach(([ic, t, tag, d], i) => {
    const x = MX + i * 4.115, y = 2.22, o = 1 + i;
    raised(s, x, y, 3.9, 4.63, { order: o });
    inset(s, x + 0.25, y + 0.25, 3.4, 2.35, { order: o, bg: BG });
    img(s, gif(ic), x + 0.95, y + 0.47, 2.0, 1.92, { order: o });
    text(s, t, { x: x + 0.3, y: y + 2.85, w: 3.3, h: 0.45, size: 18, bold: true, order: o });
    text(s, tag, { x: x + 0.3, y: y + 3.3, w: 3.3, h: 0.28, size: 9, bold: true, color: RED, charSpacing: 2, order: o });
    text(s, d, { x: x + 0.3, y: y + 3.65, w: 3.3, h: 0.85, size: 11, color: INK2, order: o, lsm: 1.12 });
  });
  notes(s, "Accelerometer for falls and collapse, gyroscope for posture and balance, magnetometer for orientation.");
}

// ============================================================ 13 MEET OUR PRODUCT
{
  const s = newSlide();
  header(s, "03 · PRODUCT & HARDWARE", "Meet our ", "product", "An upper-arm band that keeps its sensors still while you run.", 13);
  const rows = [
    ["user", "Upper-arm fit", "Sits away from the arm's largest swing — the optics stay in contact at running pace."],
    ["led-sensor", "PPG + IMU in one module", "Heart rate and body movement captured together, filtered on the ESP32."],
    ["gear", "Built to be worn", "Precision 3D-printed, sweat-resistant casing on a porous modular elastic strap."],
  ];
  rows.forEach(([ic, t, d], i) => {
    const y = 2.22 + i * 1.62, o = 1 + i;
    raised(s, MX, y, 6.4, 1.4, { order: o });
    iconBtn(s, ic, MX + 0.8, y + 0.7, 1.0, o);
    text(s, t, { x: MX + 1.55, y: y + 0.25, w: 4.6, h: 0.38, size: 15, bold: true, order: o });
    text(s, d, { x: MX + 1.55, y: y + 0.66, w: 4.6, h: 0.56, size: 11, color: INK2, order: o });
  });
  raised(s, 7.75, 2.28, 4.45, 4.45, { shape: S.OVAL, order: 1, depth: 1.4 });
  img(s, photo("product-side"), 8.35, 2.5, 3.25, 4.0, { order: 2 });
  img(s, gif("orn-ring"), 12.0, 1.85, 0.95, 0.95, { order: 3 });
  pill(s, "NOVA-BAND  ·  PRODUCT", 8.9, 6.52, { order: 4, color: INK2 });
  notes(s, "Upper-arm fit, PPG + IMU in one module, and a 3D-printed casing on a porous elastic strap.");
}

// ============================================================ 14 PRODUCT ANATOMY
{
  const s = newSlide();
  header(s, "03 · PRODUCT & HARDWARE", "Product ", "anatomy", "Five layers inside the module, from the optics to the skin.", 14);
  raised(s, MX, 2.22, 5.2, 4.63, { order: 1 });
  img(s, png("device-exploded"), MX + 0.4, 2.35, 4.4, 4.1, { order: 1 });
  text(s, "Blender model · internal layout illustrative", { x: MX + 0.3, y: 6.5, w: 4.6, h: 0.26, size: 8.5, color: INK3, align: "center", order: 1 });
  const layers = [
    ["Optical window", "Two green LEDs, an IR diode and a photodetector"],
    ["Casing", "Precision 3D-printed polymer, sweat-resistant"],
    ["Li-Po battery", "High-density cell for long endurance runs"],
    ["Mini PCB", "ESP32, IMU and step-down regulator"],
    ["Sensor pod", "Skin side — keeps the optics in contact"],
  ];
  layers.forEach(([t, d], i) => {
    const y = 2.22 + i * 0.955, x = 6.05, o = 2 + i;
    raised(s, x, y, 6.68, 0.8, { r: 0.4, order: o, depth: 0.75 });
    badge(s, i + 1, x + 0.42, y + 0.4, 0.46, o, { size: 12 });
    text(s, t, { x: x + 0.88, y: y + 0.1, w: 5.6, h: 0.32, size: 13.5, bold: true, order: o });
    text(s, d, { x: x + 0.88, y: y + 0.43, w: 5.6, h: 0.28, size: 10.5, color: INK2, order: o });
  });
  notes(s, "Optical window, casing, Li-Po battery, mini PCB with ESP32 and IMU, and the skin-side sensor pod.");
}

// ============================================================ 15 3D DIGITAL TWIN
{
  const s = newSlide();
  header(s, "03 · PRODUCT & HARDWARE", "3D digital ", "twin", "A Blender model rebuilt from the product images — and reused everywhere.", 15);
  raised(s, MX, 2.22, 3.9, 4.63, { order: 1 });
  inset(s, MX + 0.25, 2.47, 3.4, 3.55, { order: 1, bg: BG });
  img(s, photo("product-front"), MX + 0.55, 2.6, 2.8, 3.3, { order: 1 });
  pill(s, "PRODUCT IMAGE", MX + 1.05, 6.22, { order: 1, color: INK2 });
  raised(s, 4.715, 2.22, 3.9, 4.63, { order: 2 });
  inset(s, 4.965, 2.47, 3.4, 3.55, { order: 2, bg: BG });
  img(s, gif("device-spin"), 5.2, 2.72, 2.95, 3.05, { order: 2 });
  pill(s, "BLENDER 3D", 5.99, 6.22, { order: 2, color: INK2 });
  raised(s, 8.83, 2.22, 3.9, 4.63, { order: 3 });
  text(s, "One model, every medium", { x: 9.13, y: 2.5, w: 3.4, h: 0.4, size: 15, bold: true, order: 3 });
  const uses = ["Interactive 3D viewer on the website", "46-asset icon & render library", "Animated loops in this deck", "1920 × 1080 showreel video"];
  uses.forEach((t, i) => {
    inset(s, 9.13, 3.05 + i * 0.66, 3.3, 0.52, { order: 4 + i, r: 0.26 });
    text(s, [{ text: "✓  ", options: { color: RED, bold: true } }, { text: t }], { x: 9.32, y: 3.05 + i * 0.66, w: 3.05, h: 0.52, size: 10.5, valign: "middle", order: 4 + i });
  });
  text(s, "Modelled from the product images: curved pill module, framed optical window, woven strap with stitched keeper.",
    { x: 9.13, y: 5.8, w: 3.35, h: 0.8, size: 9.8, color: INK2, order: 8, lsm: 1.12 });
  notes(s, "The Blender digital twin powers the website viewer, the asset library, this deck's animations and the showreel.");
}

// ============================================================ 16 IN USE
{
  const s = newSlide();
  header(s, "03 · PRODUCT & HARDWARE", "Upper-arm ", "fit", "Why the band lives on the upper arm, and how it is used.", 16);
  raised(s, MX, 2.22, 6.0, 4.63, { order: 1 });
  if (has(proto("gym-arm-43.jpg"))) img(s, proto("gym-arm-43.jpg"), MX + 0.22, 2.44, 5.56, 4.19, { order: 1 });
  else img(s, png("device-on-arm"), MX + 0.3, 2.5, 5.4, 4.1, { order: 1 });
  raised(s, 6.85, 2.22, 5.88, 1.55, { order: 2 });
  text(s, "Why the upper arm?", { x: 7.15, y: 2.36, w: 5.3, h: 0.36, size: 14, bold: true, color: RED, order: 2 });
  text(s, "The wrist swings the most while running, and that swing bleeds into the optical signal. The upper arm moves less, so the sensor stays in contact.",
    { x: 7.15, y: 2.74, w: 5.35, h: 0.92, size: 11, color: INK2, order: 2, lsm: 1.12 });
  const steps = ["Strap the band on the upper arm, module facing out.", "Pair it with the Nova-Band app over Bluetooth.",
    "Run — heart rate, cadence and load stream in real time.", "Alerts reach you and your supervisor if a limit is crossed."];
  steps.forEach((t, i) => {
    const y = 3.98 + i * 0.73, o = 3 + i;
    raised(s, 6.85, y, 5.88, 0.6, { r: 0.3, order: o, depth: 0.6 });
    badge(s, i + 1, 7.2, y + 0.3, 0.38, o, { size: 10 });
    text(s, t, { x: 7.55, y, w: 5.0, h: 0.6, size: 11, valign: "middle", order: o });
  });
  notes(s, "The upper arm swings less than the wrist, so the optical sensor keeps contact.");
}

// ============================================================ 17 SPECIFICATIONS
{
  const s = newSlide();
  header(s, "03 · PRODUCT & HARDWARE", "Specifi", "cations", "What is inside the prototype.", 17);
  const spec = [
    ["chip", "MICROCONTROLLER", "ESP32 on a custom mini PCB"],
    ["led-sensor", "PHYSIOLOGICAL SENSOR", "Optical PPG"],
    ["accelerometer", "MOTION SENSOR", "IMU — accelerometer, gyroscope, magnetometer"],
    ["microcontroller", "PROCESSING", "On-device FFT, C++ firmware"],
    ["gear", "CASING", "Precision 3D-printed polymer"],
    ["spring-tendon", "STRAP", "Porous modular elastic"],
    ["battery", "POWER", "Li-Po + step-down regulator"],
    ["bluetooth", "CONNECTIVITY", "Bluetooth → app → IoT dashboard"],
  ];
  spec.forEach(([ic, l, v], i) => {
    const x = i % 2 ? 6.78 : MX, y = 2.22 + Math.floor(i / 2) * 1.17, o = 1 + Math.floor(i / 2);
    raised(s, x, y, 5.95, 1.0, { r: 0.5, order: o, depth: 0.8 });
    iconBtn(s, ic, x + 0.55, y + 0.5, 0.78, o, { depth: 0.6 });
    text(s, l, { x: x + 1.15, y: y + 0.17, w: 4.6, h: 0.26, size: 8.5, bold: true, color: INK3, charSpacing: 2, order: o });
    text(s, v, { x: x + 1.15, y: y + 0.44, w: 4.6, h: 0.38, size: 13.5, bold: true, order: o });
  });
  notes(s, "ESP32, PPG, IMU, on-device FFT, 3D-printed casing, elastic strap, Li-Po, Bluetooth.");
}


// ============================================================ 18 WORKING PROTOTYPE
{
  const s = newSlide();
  header(s, "03 · PRODUCT & HARDWARE", "Working ", "prototype", "A LILYGO T-Display-S3 Touch in a 3D-printed pod — sketched in LibreCAD, solid-modelled in FreeCAD.");
  raised(s, MX, 2.22, 4.25, 4.63, { order: 1 });
  const hero = has(proto("pod-hero.png")) ? proto("pod-hero.png") : proto("gym-bench.jpg");
  if (has(hero)) img(s, hero, MX + 0.15, 2.4, 3.95, 3.85, { order: 1 });
  pill(s, "PRINTED POD · PETG", MX + 1.0, 6.28, { order: 1, color: INK2 });
  raised(s, 5.05, 2.22, 4.0, 4.63, { order: 2 });
  inset(s, 5.25, 2.42, 3.6, 2.6, { order: 2, bg: "FFFFFF", r: 0.12 });
  img(s, proto("case-sketch.png"), 5.3, 2.47, 3.5, 2.5, { order: 2 });
  text(s, "LibreCAD sketch  ·  NB-CASE-01", { x: 5.25, y: 5.12, w: 3.6, h: 0.3, size: 11, bold: true, align: "center", order: 2 });
  text(s, "Top, front, end and section views, A3 at 2:1. Board values are nominal — measured before printing.",
    { x: 5.3, y: 5.45, w: 3.5, h: 0.8, size: 9.5, color: INK2, align: "center", order: 2, lsm: 1.12 });
  pill(s, "DXF · STEP · STL", 5.93, 6.28, { order: 2, color: INK2 });
  const spec = [
    ["MCU", "ESP32-S3R8 · 240 MHz dual core"],
    ["MEMORY", "16 MB flash · 8 MB PSRAM"],
    ["DISPLAY", "1.9\" IPS 320×170 · touch"],
    ["CASE", "78 × 34 × 15.8 mm · 2 parts + caps"],
    ["STRAP", "38–40 mm band, under-tunnel"],
    ["LINK", "Bluetooth LE · USB-C"],
  ];
  spec.forEach(([k, v], i) => {
    const y = 2.22 + i * 0.78, o = 3 + Math.floor(i / 2);
    raised(s, 9.3, y, 3.43, 0.64, { r: 0.32, order: o, depth: 0.6 });
    text(s, k, { x: 9.55, y: y + 0.08, w: 3.0, h: 0.2, size: 7.5, bold: true, color: INK3, charSpacing: 2, order: o });
    text(s, v, { x: 9.55, y: y + 0.28, w: 3.1, h: 0.3, size: 10.5, bold: true, order: o });
  });
  notes(s, "The working prototype: a LILYGO T-Display-S3 Touch (ESP32-S3R8, 16 MB flash, 8 MB PSRAM, 1.9-inch touch screen) in a two-part printed pod. The case was drawn in LibreCAD and solid-modelled in FreeCAD; a 38–40 mm strap runs through a tunnel under the board.");
}

// ============================================================ 19 ON-DEVICE INTERFACE
{
  const s = newSlide();
  header(s, "03 · PRODUCT & HARDWARE", "On-device ", "interface", "Firmware for the band's own screen — Blender assets, depth of field, 60 fps on both CPU cores.");
  [["ui-live", 0], ["ui-run", 1], ["ui-ready", 2], ["ui-link", 3]].forEach(([n, i]) => {
    img(s, proto(n + ".png"), MX - 0.05 + (i % 2) * 3.85, 2.05 + Math.floor(i / 2) * 2.45, 3.85, 2.4, { order: 1 + i });
  });
  const rows = [
    ["lightbulb", "Blender splash", "A rack-focus intro rendered in Blender, played from flash."],
    ["gyroscope", "Depth of field", "Gym bokeh far, glass cards mid, blurred specks near — three parallax layers."],
    ["microcontroller", "60 frames per second", "Each core draws half the frame; DMA sends it to the ST7789."],
    ["smartphone", "Touch & buttons", "Swipe with spring physics; long-press to start or pause a run."],
  ];
  rows.forEach(([ic, t, d], i) => {
    const y = 2.18 + i * 1.17, x = 8.45, o = 5 + i;
    raised(s, x, y, 4.28, 1.0, { r: 0.5, order: o, depth: 0.8 });
    iconBtn(s, ic, x + 0.52, y + 0.5, 0.76, o, { depth: 0.6 });
    text(s, t, { x: x + 1.05, y: y + 0.13, w: 3.1, h: 0.32, size: 12.5, bold: true, order: o });
    text(s, d, { x: x + 1.05, y: y + 0.45, w: 3.1, h: 0.5, size: 9.5, color: INK2, order: o, lsm: 1.1 });
  });
  text(s, "From the firmware's PC simulator (same C++ as the band). HR is simulated (DEMO) until a PPG sensor is fitted.",
    { x: 3.05, y: 6.98, w: 7.4, h: 0.3, size: 8.5, color: INK3, order: 9 });
  notes(s, "The band's own interface: live heart rate with a beating 3D heart and PPG wave, run metrics, readiness ring, and the pairing page with a QR code to the web app. The firmware renders at about 60 fps by splitting each frame between the two ESP32-S3 cores.");
}

// ============================================================ 20 BAND <-> APP
{
  const s = newSlide();
  header(s, "04 · SOFTWARE & AI", "Connected to the ", "app", "Bluetooth LE or USB, one JSON protocol — and the web app installs like a native app (PWA).");
  raised(s, MX, 2.22, 4.5, 3.05, { order: 1 });
  img(s, proto("ui-link.png"), MX + 0.1, 2.3, 4.3, 2.75, { order: 1 });
  text(s, "NovaBand · pairing page", { x: MX, y: 5.35, w: 4.5, h: 0.3, size: 10.5, bold: true, color: INK2, align: "center", order: 1 });
  // two links in the middle
  [["BLUETOOTH LE", "Web Bluetooth · Android, Windows, macOS"], ["USB-C", "Web Serial · desktop Chrome / Edge"]].forEach(([t, d], i) => {
    const y = 2.55 + i * 1.3, o = 2 + i;
    raised(s, 5.4, y, 3.1, 1.02, { r: 0.51, order: o, depth: 0.7 });
    text(s, [{ text: "⇄  ", options: { color: RED, bold: true } }, { text: t, options: { bold: true } }], { x: 5.65, y: y + 0.14, w: 2.8, h: 0.34, size: 12.5, order: o });
    text(s, d, { x: 5.65, y: y + 0.52, w: 2.8, h: 0.34, size: 9, color: INK2, order: o });
  });
  img(s, proto("app-phone.png"), 8.75, 1.95, 3.95, 5.1, { order: 4 });
  const chips = ["Telemetry 1 Hz · PPG wave 50 Hz", "Standard Heart Rate service 0x180D", "App → band: run, alerts, coach messages"];
  chips.forEach((c, i) => {
    inset(s, MX + (i % 3) * 2.72, 5.85, 2.6, 0.5, { order: 5, r: 0.25 });
    text(s, c, { x: MX + (i % 3) * 2.72, y: 5.85, w: 2.6, h: 0.5, size: 9, align: "center", valign: "middle", order: 5 });
  });
  text(s, "The QR code on the band opens novaband-id.web.app — installable, works offline.", { x: MX, y: 6.55, w: 8.0, h: 0.3, size: 10, color: RED, bold: true, order: 6 });
  notes(s, "The band and the app speak one JSON protocol over Bluetooth LE (Web Bluetooth) or USB (Web Serial). The band also exposes the standard Heart Rate service, so other fitness apps can read it. The web app is a PWA: installable and usable offline.");
}

// ============================================================ 21 IN THE GYM (full bleed)
{
  const s = newSlide();
  s.background = { color: "1C1215" };
  if (has(proto("gym-orbit.jpg"))) s.addImage({ path: proto("gym-orbit.jpg"), x: 0, y: 0, w: W, h: H, altText: ALT["gym-orbit"] });
  s.addShape(S.RECTANGLE, { x: 0, y: 0, w: W, h: 1.45, fill: { color: "1C1215", transparency: 45 }, line: { type: "none" } });
  text(s, [{ text: "In the ", options: { color: "FFFFFF" } }, { text: "gym", options: { color: "F3B8BE" } }],
    { x: MX, y: 0.42, w: 8, h: 0.72, size: 33, bold: true, name: "!!title", valign: "middle" });
  brand(s, true);
  s.addShape(S.ROUNDED_RECTANGLE, { x: MX, y: 5.35, w: 6.2, h: 1.5, rectRadius: 0.22, fill: { color: "1C1215", transparency: 22 },
    line: { color: "FFFFFF", transparency: 70, width: 0.75 }, objectName: nm(1) });
  text(s, "Rendered, not photographed", { x: MX + 0.3, y: 5.5, w: 5.7, h: 0.36, size: 15, bold: true, color: "FFFFFF", order: 1 });
  text(s, "Blender Cycles, from the CLI. The gym, runner and props are Sketchfab models (CC-BY); the pod, its live screen and the band are ours.",
    { x: MX + 0.3, y: 5.9, w: 5.7, h: 0.85, size: 10.5, color: "EAD9DB", order: 1, lsm: 1.12 });
  [["gym-arm", 0], ["gym-bench", 1]].forEach(([n, i]) => {
    if (!has(proto(n + ".jpg"))) return;
    s.addImage({ path: proto(n + ".jpg"), x: 8.1 + i * 2.43, y: 5.35, w: 2.3, h: 1.29, altText: ALT[n], objectName: nm(2 + i),
      line: { color: "FFFFFF", width: 1.5 } });
  });
  page(s, 0, true);
  notes(s, "A frame from the new showreel: a runner on a treadmill wearing the prototype pod on the upper arm. Everything is rendered in Blender Cycles; the environment and props are Sketchfab models under Creative Commons Attribution.");
}

// ============================================================ 18 SMART APPLICATION
{
  const s = newSlide();
  header(s, "04 · SOFTWARE & AI", "Smart ", "application", "The runner app that ships with the band — real-time and explainable.", 18);
  ["p-home", "p-live", "p-ready"].forEach((p, i) => img(s, A("phones", p + ".png"), 0.35 + i * 2.35, 2.05, 2.55, 4.9, { order: 1 + i }));
  const rows = [
    ["footsteps", "Today's performance", "Steps, calories and distance against daily goals."],
    ["led-sensor", "Live PPG signal", "Filtered on the band and streamed while you run."],
    ["gauge", "Readiness profile", "Six factors behind one daily score."],
    ["bell", "Early warning", "Alerts when a safe limit is crossed."],
  ];
  rows.forEach(([ic, t, d], i) => {
    const y = 2.28 + i * 1.15, x = 7.75, o = 4 + i;
    raised(s, x, y, 4.98, 0.96, { r: 0.48, order: o, depth: 0.8 });
    iconBtn(s, ic, x + 0.5, y + 0.48, 0.74, o, { depth: 0.6 });
    text(s, t, { x: x + 1.05, y: y + 0.14, w: 3.8, h: 0.34, size: 13.5, bold: true, order: o });
    text(s, d, { x: x + 1.05, y: y + 0.5, w: 3.8, h: 0.3, size: 10.5, color: INK2, order: o });
  });
  text(s, "Screens captured from the live demo  ·  novaband-id.web.app", { x: 7.75, y: 6.95, w: 4.2, h: 0.26, size: 8.5, color: INK3, order: 8 });
  notes(s, "Real screens from the live demo app: home, live session and readiness.");
}

// ============================================================ 19 READINESS & EARLY WARNING
{
  const s = newSlide();
  header(s, "04 · SOFTWARE & AI", "Readiness score & ", "early warning", "Physiology and movement, read together — so every run stays inside safe limits.", 19);
  const flow = [
    ["heart", "Read", "Heart rate from PPG; cadence and load from the IMU."],
    ["ai-network", "Analyse", "Six factors combined into one Readiness Score."],
    ["bell", "Warn", "Alert runner and supervisor when a limit is crossed."],
  ];
  flow.forEach(([ic, t, d], i) => {
    const x = MX + i * 2.5, y = 2.22, o = 1 + i;
    raised(s, x, y, 2.3, 2.78, { order: o });
    iconBtn(s, ic, x + 1.15, y + 0.85, 1.25, o);
    text(s, t, { x: x + 0.1, y: y + 1.6, w: 2.1, h: 0.38, size: 15, bold: true, align: "center", order: o });
    text(s, d, { x: x + 0.15, y: y + 2.0, w: 2.0, h: 0.66, size: 10, color: INK2, align: "center", order: o });
    if (i < 2) badge(s, "›", x + 2.4, y + 0.85, 0.34, o, { size: 13 });
  });
  raised(s, MX, 5.2, 7.3, 1.65, { order: 4 });
  text(s, "THE SIX FACTORS  ·  DEMO APP", { x: MX + 0.3, y: 5.33, w: 5, h: 0.26, size: 8.5, bold: true, color: RED, charSpacing: 2, order: 4 });
  const chips = ["Heart-rate variability", "Resting heart rate", "Acute : chronic load", "Recovery quality", "Kinematic consistency", "Accumulated fatigue"];
  chips.forEach((c, i) => {
    const x = MX + 0.3 + (i % 3) * 2.27, y = 5.72 + Math.floor(i / 3) * 0.5;
    inset(s, x, y, 2.12, 0.4, { order: 5 + (i % 3), r: 0.2 });
    text(s, c, { x, y, w: 2.12, h: 0.4, size: 9.8, align: "center", valign: "middle", order: 5 + (i % 3) });
  });
  img(s, gif("gauge"), 8.1, 2.4, 1.55, 1.55, { order: 8 });
  text(s, [{ text: "85", options: { fontFace: FONT_B, color: RED, fontSize: 30 } }, { text: "\nReady to train", options: { fontSize: 10.5, color: INK2, bold: true } }],
    { x: 8.05, y: 4.0, w: 1.7, h: 0.95, align: "center", order: 8 });
  img(s, A("phones", "p-ready.png"), 9.85, 2.05, 2.9, 4.9, { order: 9 });
  notes(s, "Read, analyse, warn. The six readiness factors are those used in the demo application.");
}

// ============================================================ 20 COMMUNITY DASHBOARD
{
  const s = newSlide();
  header(s, "04 · SOFTWARE & AI", "Community ", "dashboard", "The Shared Safety Net for event supervisors and running groups.", 20);
  img(s, A("phones", "p-comm.png"), 0.4, 2.05, 2.9, 4.9, { order: 1 });
  const rows = [
    ["map-pin", "Group map", "Every runner's position and status on one map."],
    ["user", "Member status", "Heart rate, readiness and distance for each runner."],
    ["bell", "Simultaneous alerts", "The supervisor is notified at the same moment as the runner."],
  ];
  rows.forEach(([ic, t, d], i) => {
    const y = 2.22 + i * 1.62, x = 3.55, o = 2 + i;
    raised(s, x, y, 5.45, 1.4, { order: o });
    iconBtn(s, ic, x + 0.78, y + 0.7, 1.0, o);
    text(s, t, { x: x + 1.5, y: y + 0.26, w: 3.8, h: 0.36, size: 14.5, bold: true, order: o });
    text(s, d, { x: x + 1.5, y: y + 0.66, w: 3.75, h: 0.55, size: 10.8, color: INK2, order: o });
  });
  [["476", "runners connected"], ["3", "active alerts"]].forEach(([n, l], i) => {
    const y = 2.22 + i * 2.43, o = 5 + i;
    raised(s, 9.25, y, 3.48, 2.2, { order: o });
    text(s, n, { x: 9.25, y: y + 0.35, w: 3.48, h: 0.95, size: 44, font: FONT_B, color: RED, align: "center", valign: "middle", order: o });
    text(s, l, { x: 9.25, y: y + 1.3, w: 3.48, h: 0.34, size: 13, bold: true, align: "center", order: o });
    text(s, "demo data", { x: 9.25, y: y + 1.66, w: 3.48, h: 0.28, size: 9, color: INK3, align: "center", order: o });
  });
  notes(s, "The IoT dashboard aggregates every member's metrics: group map, member status and simultaneous alerts. Figures are demo data.");
}

// ============================================================ 21 METHOD & TIMELINE
{
  const s = newSlide();
  header(s, "05 · EVIDENCE & MARKET", "Method & ", "timeline", "Research & Development with a quantitative experimental approach.", 21);
  const stages = [
    ["calendar", "Design Stage", ["Ergonomic casing designed and 3D-printed", "Upper-arm placement to damp shocks", "PPG, IMU and ESP32 selected"]],
    ["chip", "Integration Stage", ["Mini PCB, Li-Po and step-down assembled", "Sensor fusion + FFT programmed in C++", "Bluetooth link to app and IoT dashboard"]],
    ["clipboard", "Validation Stage", ["MAPE vs high-speed motion capture", "SUS usability test, 60 respondents", "Findings feed the next design iteration"]],
  ];
  stages.forEach(([ic, t, b], i) => {
    const x = MX + i * 4.115, y = 2.22, o = 1 + i;
    raised(s, x, y, 3.9, 3.42, { order: o });
    iconBtn(s, ic, x + 0.75, y + 0.72, 1.0, o);
    text(s, String(i + 1), { x: x + 2.9, y: y + 0.25, w: 0.7, h: 0.9, size: 40, font: FONT_B, color: "E2D5D6", align: "right", order: o });
    text(s, t, { x: x + 0.3, y: y + 1.45, w: 3.3, h: 0.42, size: 16, bold: true, italic: true, color: RED, order: o });
    text(s, b.map((q, k) => ({ text: q, options: { bullet: { indent: 12 }, breakLine: k < b.length - 1 } })),
      { x: x + 0.3, y: y + 1.95, w: 3.35, h: 1.35, size: 10.5, color: INK2, order: o, paraSpaceAfter: 4 });
  });
  raised(s, MX, 5.85, 12.13, 1.0, { order: 4 });
  ["R&D  ·  quantitative experimental", "MAPE vs high-speed motion capture", "SUS  ·  60 respondents"].forEach((c, i) => {
    inset(s, MX + 0.3 + i * 3.9, 6.08, 3.65, 0.54, { order: 5 + i, r: 0.27 });
    text(s, c, { x: MX + 0.3 + i * 3.9, y: 6.08, w: 3.65, h: 0.54, size: 11, bold: true, align: "center", valign: "middle", order: 5 + i });
  });
  notes(s, "Design, integration and validation stages; validation via MAPE against high-speed motion capture and SUS with 60 respondents.");
}

// ============================================================ 22 RESULTS
{
  const s = newSlide();
  header(s, "05 · EVIDENCE & MARKET", "Result & ", "discussion", "Accurate in the field, comfortable to wear.", 22);
  raised(s, MX, 2.22, 5.2, 4.63, { order: 1 });
  text(s, "Hardware accuracy · MAPE (%)", { x: MX + 0.3, y: 2.4, w: 4.6, h: 0.34, size: 13.5, bold: true, order: 1 });
  s.addChart(pres.charts.BAR, [{ name: "MAPE upper bound (%)", labels: ["Smartwatch · steps  42%", "Smartwatch · calories  44%", "Nova-Band  3.5%"], values: [42, 44, 3.5] }], {
    x: MX + 0.15, y: 2.8, w: 4.9, h: 2.75, barDir: "bar", chartColors: [ROSE, ROSE, RED], barGapWidthPct: 55,
    showValue: false, catAxisLabelColor: INK, catAxisLabelFontSize: 10.5, catAxisLabelFontFace: FONT,
    catAxisOrientation: "maxMin", valAxisHidden: true, valAxisMaxVal: 55, valAxisMinVal: 0, valGridLine: { style: "none" },
    catGridLine: { style: "none" }, showLegend: false, catAxisLineShow: false, objectName: nm(1),
  });
  text(s, "Nova-Band: 2.5–3.5% — below the 5% limit for professional sports instruments. Consumer values are the upper bounds of reported ranges.",
    { x: MX + 0.3, y: 5.7, w: 4.6, h: 0.95, size: 10, color: INK2, order: 1, lsm: 1.12 });
  raised(s, 5.98, 2.22, 3.45, 4.63, { order: 2 });
  text(s, "Usability · SUS", { x: 6.2, y: 2.4, w: 2.4, h: 0.34, size: 13.5, bold: true, order: 2 });
  img(s, gif("medal"), 8.55, 2.3, 0.78, 0.78, { order: 2 });
  s.addChart(pres.charts.DOUGHNUT, [{ name: "SUS", labels: ["Score", "Remaining"], values: [84.5, 15.5] }], {
    x: 6.25, y: 2.95, w: 2.9, h: 2.5, holeSize: 72, chartColors: [RED, TRACK], showLegend: false, showValue: false,
    showPercent: false, showLabel: false, dataBorder: { pt: 0.5, color: BG }, objectName: nm(2),
  });
  text(s, [{ text: "84.5", options: { fontFace: FONT_B, fontSize: 28, color: RED } }, { text: "\n/ 100", options: { fontSize: 10.5, color: INK2 } }],
    { x: 6.9, y: 3.72, w: 1.6, h: 0.95, align: "center", valign: "middle", order: 2 });
  text(s, "Grade A · Acceptable", { x: 6.0, y: 5.55, w: 3.4, h: 0.36, size: 13, bold: true, align: "center", order: 3 });
  text(s, "60 respondents · 10 SUS statements · above the 68 threshold", { x: 6.15, y: 5.92, w: 3.1, h: 0.62, size: 9.8, color: INK2, align: "center", order: 3 });
  raised(s, 9.6, 2.22, 3.13, 4.63, { order: 4 });
  s.addImage({ path: photo("testing"), x: 9.78, y: 2.4, w: 2.77, h: 3.85, sizing: { type: "cover", w: 2.77, h: 3.85 }, rounding: false, objectName: nm(4), altText: ALT.testing });
  pill(s, "TESTING DOCUMENTATION", 9.83, 6.37, { order: 5, size: 8, color: INK2 });
  notes(s, "MAPE 2.5–3.5% against consumer ranges of up to 42–44%; SUS 84.5, grade A, 60 respondents.");
}

// ============================================================ 23 MARKET
{
  const s = newSlide();
  header(s, "05 · EVIDENCE & MARKET", "Market ", "opportunity", "Running events are where group safety matters most.", 23);
  raised(s, 0.95, 2.25, 4.6, 4.6, { shape: S.OVAL, order: 1, depth: 1.3 });
  raised(s, 1.65, 3.2, 3.2, 3.2, { shape: S.OVAL, order: 2, depth: 1.0 });
  raised(s, 2.35, 4.2, 1.8, 1.8, { shape: S.OVAL, order: 3, depth: 0.8 });
  img(s, gif("target-tiers"), 2.5, 4.3, 1.5, 1.5, { order: 3 });
  text(s, "TAM", { x: 2.6, y: 2.5, w: 1.3, h: 0.4, size: 15, font: FONT_B, color: DEEP, align: "center", order: 1 });
  text(s, "SAM", { x: 2.6, y: 3.4, w: 1.3, h: 0.4, size: 14, font: FONT_B, color: RED, align: "center", order: 2 });
  const rows = [
    ["globe", "1,818", "TAM · Indonesia", "running events held nationwide in 2025"],
    ["map-pin", "302", "SAM · Central Java", "running events in the province"],
    ["target-tiers", "18", "SOM · Surakarta", "running events across the city"],
  ];
  rows.forEach(([ic, n, t, d], i) => {
    const y = 2.25 + i * 1.5, x = 6.3, o = 4 + i;
    raised(s, x, y, 6.43, 1.28, { order: o });
    iconBtn(s, ic, x + 0.72, y + 0.64, 0.92, o, { depth: 0.7 });
    text(s, n, { x: x + 1.35, y: y + 0.17, w: 2.1, h: 0.95, size: 34, font: FONT_B, color: RED, valign: "middle", order: o });
    text(s, t, { x: x + 3.5, y: y + 0.28, w: 2.8, h: 0.34, size: 13.5, bold: true, order: o });
    text(s, d, { x: x + 3.5, y: y + 0.65, w: 2.8, h: 0.4, size: 10.5, color: INK2, order: o });
  });
  text(s, "Source: 2025 running-event data, verified by the team.", { x: 6.3, y: 6.7, w: 5, h: 0.26, size: 8.5, color: INK3, order: 7 });
  notes(s, "TAM 1,818 events in Indonesia (2025), SAM 302 in Central Java, SOM 18 in Surakarta.");
}

// ============================================================ 24 PROJECTION
{
  const s = newSlide();
  header(s, "05 · EVIDENCE & MARKET", "Business ", "projection", "Fixed cost, total cost and revenue, 2026–2030.", 24);
  raised(s, MX, 2.22, 8.1, 4.63, { order: 1 });
  const yrs = ["2026", "2027", "2028", "2029", "2030"];
  s.addChart(pres.charts.LINE, [
    { name: "Fixed cost", labels: yrs, values: [4, 4, 4, 4, 4] },
    { name: "Total cost", labels: yrs, values: [4, 6, 8, 10, 12] },
    { name: "Revenue", labels: yrs, values: [4, 7, 9, 13, 17] },
  ], {
    x: MX + 0.25, y: 2.4, w: 7.6, h: 4.25, chartColors: [ROSE, MID, DEEP], lineSize: 3, lineDataSymbol: "circle",
    lineDataSymbolSize: 8, showLegend: true, legendPos: "t", legendFontSize: 11, legendFontFace: FONT, legendColor: INK2,
    valAxisMaxVal: 20, valAxisMinVal: 0, valAxisMajorUnit: 5, valAxisLabelColor: INK3, valAxisLabelFontSize: 10,
    catAxisLabelColor: INK2, catAxisLabelFontSize: 10.5, valGridLine: { color: TRACK, size: 0.75 }, catGridLine: { style: "none" },
    valAxisLineShow: false, objectName: nm(1),
  });
  raised(s, 8.95, 2.22, 3.78, 2.2, { order: 2 });
  img(s, gif("coins"), 9.15, 2.4, 1.0, 1.0, { order: 2 });
  text(s, "Revenue above total cost from 2027", { x: 10.2, y: 2.45, w: 2.35, h: 0.95, size: 13, bold: true, color: RED, valign: "middle", order: 2 });
  text(s, "The gap widens every year, to 17 vs 12 by 2030.", { x: 9.2, y: 3.5, w: 3.3, h: 0.7, size: 10.8, color: INK2, order: 2 });
  raised(s, 8.95, 4.65, 3.78, 2.2, { order: 3 });
  img(s, gif("bar-chart"), 9.15, 4.8, 1.0, 1.0, { order: 3 });
  text(s, "Fixed cost held flat", { x: 10.2, y: 4.85, w: 2.35, h: 0.95, size: 13, bold: true, valign: "middle", order: 3 });
  text(s, "Values read from the chart in the ISIF deck; units as in the source.", { x: 9.2, y: 5.9, w: 3.3, h: 0.7, size: 9.8, color: INK3, order: 3 });
  notes(s, "Revenue grows from 4 to 17 while total cost grows from 4 to 12; values read from the ISIF deck chart, units as in the source.");
}

// ============================================================ 25 PARTNERS
{
  const s = newSlide();
  header(s, "PARTNERS", "Our ", "partnership", "Collaborators supporting research, validation and testing.", 25);
  const partners = [
    [photo("logo-reka"), "REKA Mersif", "Collaborator"],
    [photo("crest-sman1"), "SMA Negeri 1 Surakarta", "Research team"],
    [photo("logo-uns"), "Universitas Sebelas Maret", "Collaborator"],
    [photo("logo-mersif-enuma-light"), "Mersif Academy · Enuma Technology", "Collaborators"],
    [gif("school"), "SMA Negeri 5 Yogyakarta", "ISIF 2026 partner school"],
  ];
  partners.forEach(([f, t, r], i) => {
    const x = MX + i * 2.46, y = 2.35, o = 1 + i;
    raised(s, x, y, 2.26, 3.3, { order: o });
    inset(s, x + 0.2, y + 0.2, 1.86, 1.75, { order: o, bg: BG });
    img(s, f, x + 0.42, y + 0.42, 1.42, 1.31, { order: o });
    text(s, t, { x: x + 0.12, y: y + 2.1, w: 2.02, h: 0.62, size: 12, bold: true, align: "center", order: o, valign: "middle" });
    text(s, r, { x: x + 0.12, y: y + 2.75, w: 2.02, h: 0.3, size: 10, color: RED, align: "center", order: o });
  });
  raised(s, MX, 5.95, 12.13, 0.9, { order: 6 });
  img(s, gif("chain-link"), MX + 0.25, 6.0, 0.8, 0.8, { order: 6 });
  text(s, [{ text: "Partnership · ISIF 2026   ", options: { bold: true, color: RED } }, { text: "Built by students of SMA Negeri 1 Surakarta together with university, industry and school partners." }],
    { x: MX + 1.2, y: 5.95, w: 10.7, h: 0.9, size: 11.5, valign: "middle", order: 6 });
  notes(s, "REKA Mersif, SMA Negeri 1 Surakarta, UNS, Mersif Academy, Enuma Technology and SMA Negeri 5 Yogyakarta.");
}

// ============================================================ 26 CONCLUSION
{
  const s = newSlide();
  header(s, "CONCLUSION", "Conclusion and ", "copyright", null, 26);
  const rows = [
    ["chip", "System integration", "PPG (heart rate) and IMU (body movement) on an ESP32, worn on the upper arm, collect physiological and motion data simultaneously."],
    ["ai-network", "AI analysis", "AI processes activity patterns and physiological responses together, in real time, during training."],
    ["medal", "Impact & final result", "An accurate, practical, ergonomic and data-driven wearable for real-time runner performance monitoring."],
  ];
  rows.forEach(([ic, t, d], i) => {
    const y = 1.95 + i * 1.66, o = 1 + i;
    raised(s, MX, y, 7.4, 1.46, { order: o });
    iconBtn(s, ic, MX + 0.8, y + 0.73, 1.0, o);
    text(s, t, { x: MX + 1.55, y: y + 0.2, w: 5.6, h: 0.36, size: 15, bold: true, order: o });
    text(s, d, { x: MX + 1.55, y: y + 0.6, w: 5.6, h: 0.7, size: 11, color: INK2, order: o, lsm: 1.12 });
  });
  raised(s, 8.25, 1.95, 4.48, 4.9, { order: 4 });
  text(s, "COPYRIGHT & IP", { x: 8.55, y: 2.15, w: 3, h: 0.26, size: 8.5, bold: true, color: RED, charSpacing: 2, order: 4 });
  inset(s, 8.55, 2.55, 3.88, 3.95, { order: 4, bg: BG });
  img(s, gif("lightbulb"), 9.9, 2.75, 1.15, 1.15, { order: 5 });
  s.addText("N", { shape: S.ROUNDED_RECTANGLE, rectRadius: 0.16, x: 9.47, y: 4.1, w: 0.62, h: 0.62, fill: { color: RED }, color: "FFFFFF",
    fontFace: FONT_B, fontSize: 22, align: "center", valign: "middle", margin: 0, isTextBox: true, objectName: nm(5) });
  text(s, [{ text: "Nova", options: { color: INK } }, { text: "-", options: { color: RED } }, { text: "Band", options: { color: INK } }],
    { x: 10.2, y: 4.1, w: 2.2, h: 0.62, size: 22, bold: true, valign: "middle", order: 5 });
  text(s, "© 2026 Team Nova-Band\nSMA Negeri 1 Surakarta", { x: 8.7, y: 5.0, w: 3.6, h: 0.75, size: 10.5, color: INK2, align: "center", order: 6 });
  notes(s, "System integration, AI analysis, and the final impact.");
}


// ============================================================ 3D ASSET CREDITS
{
  const s = newSlide();
  header(s, "CREDITS", "3D asset ", "credits", "Sketchfab models used for the showreel and renders — Creative Commons Attribution (CC-BY).");
  const credPath = path.join(ROOT, "build", "sketchfab", "credits.json");
  const cred = has(credPath) ? JSON.parse(fs.readFileSync(credPath, "utf8")) : {};
  // only the models that appear in the renders (a few downloads were evaluated and not used)
  const USED = ["training-gym", "runner", "treadmill", "dumbbell-rack", "kettlebell", "bottle", "sports-bag", "shoes", "phone"];
  const keys = USED.filter((k) => k in cred);
  const col = Math.ceil(keys.length / 2);
  keys.forEach((k, i) => {
    const c = cred[k], x = i < col ? MX : 6.78, y = 2.2 + (i % col) * 0.72, o = 1 + Math.floor((i % col) / 2);
    raised(s, x, y, 5.95, 0.6, { r: 0.3, order: o, depth: 0.55 });
    text(s, [{ text: c.title, options: { bold: true, color: INK } }, { text: "   by " + c.author, options: { color: INK2 } }],
      { x: x + 0.3, y, w: 4.4, h: 0.6, size: 10.5, valign: "middle", order: o });
    text(s, (c.license || "").replace("Attribution", "BY"), { x: x + 4.6, y, w: 1.2, h: 0.6, size: 8.5, bold: true, color: RED, align: "right", valign: "middle", order: o });
  });
  text(s, "Links for every model: build/sketchfab/credits.json  ·  sketchfab.com", { x: MX, y: 6.95, w: 8, h: 0.28, size: 8.5, color: INK3, order: 8 });
  notes(s, "Credits for the Sketchfab models used in the renders and the showreel, all under Creative Commons Attribution.");
}

// ============================================================ THANK YOU
{
  const s = newSlide();
  s.background = { color: RED };
  const DK = "3D050A", LT = "A94446";
  img(s, gif("corner-rings-wine"), -1.3, -1.4, 2.85, 2.85, { name: "!!corner" });
  brand(s, true);
  text(s, "Thank you", { x: 0.7, y: 1.6, w: 6.6, h: 1.3, size: 62, font: FONT_B, color: "FFFFFF", order: 1, name: "!!title", valign: "middle" });
  text(s, "Monitor. Analyze. Improve.", { x: 0.75, y: 2.95, w: 6, h: 0.5, size: 20, color: CREAM, italic: true, order: 2 });
  text(s, "Real-time physiological monitoring for safer running — one band, one community at a time.",
    { x: 0.75, y: 3.55, w: 5.9, h: 0.75, size: 13, color: "F1D9D9", order: 3 });
  text(s, "TEAM NOVA-BAND", { x: 0.75, y: 4.55, w: 4, h: 0.26, size: 9.5, bold: true, color: CREAM, charSpacing: 2, order: 4 });
  text(s, "Maheswara Nala Wisadewa · Almira Edgina Nareswari Haryadi · Azra Daniswara Tyandaru · Dela Astiara · Rizkyta Aufa Mutiagassania · Satriya Javas Wibisono",
    { x: 0.75, y: 4.83, w: 5.9, h: 0.7, size: 10.5, color: "F1D9D9", order: 4, lsm: 1.2 });
  s.addText("novaband-id.web.app", { shape: S.ROUNDED_RECTANGLE, rectRadius: 0.24, x: 0.75, y: 5.8, w: 2.75, h: 0.48, fill: { color: "FFFFFF" },
    color: RED, fontFace: FONT, bold: true, fontSize: 12.5, align: "center", valign: "middle", margin: 0, isTextBox: true, objectName: nm(5),
    shadow: { type: "outer", color: DK, opacity: 0.45, blur: 10, offset: 4, angle: 90 } });
  raised(s, 7.25, 1.1, 5.5, 4.25, { bg: RED, dark: DK, light: LT, darkOp: 0.7, lightOp: 0.55, order: 2, r: 0.36 });
  img(s, photo("team"), 7.45, 1.35, 5.1, 3.85, { order: 3, align: "bottom" });
  img(s, gif("device-spin-wine"), 8.95, 5.6, 2.1, 1.65, { order: 6 });
  page(s, 27, true);
  notes(s, "Thank you. Team Nova-Band, SMA Negeri 1 Surakarta — novaband-id.web.app");
}

fs.mkdirSync(path.dirname(OUT), { recursive: true });
pres.writeFile({ fileName: OUT }).then((f) => console.log("wrote", f));
