/* ============================================================
   Buku tamu pameran Nova-Band (bukutamu/index.html)
   Opened from the QR at the stand: /bukutamu/?k=<event code>.
   Anonymous sign-in gives each phone one uid = one entry; the entry is two
   documents in one batch (public card + private contact), and firestore.rules
   only accepts it when the event code is right.
   ============================================================ */
import { firebase, auth } from "./fb.js";
import { Booth, FILTERS } from "./selfie.js";

const $ = (id) => document.getElementById(id);
const steps = ["sLoad", "sNoCode", "sForm", "sSelfie", "sDone"];
const show = (id) => steps.forEach((s) => ($(s).hidden = s !== id));
const DONE_KEY = "novaband-bukutamu";

// event code: from the QR link, kept for this tab, then removed from the address bar
const url = new URL(location.href);
let kode = url.searchParams.get("k") || sessionStorage.getItem("bt-k") || "";
if (url.searchParams.get("k")) { sessionStorage.setItem("bt-k", kode); history.replaceState(null, "", location.pathname); }
const acara = "Pameran Nova-Band " + new Date().toISOString().slice(0, 10);

let fb, user, booth, photo = "";

async function boot() {
  try {
    fb = await firebase();
    user = await auth(fb.app);
    const mine = await fb.F.getDoc(fb.F.doc(fb.db, "bukutamu_publik", user.uid));
    if (mine.exists()) return done(mine.data(), true);
  } catch (e) {
    console.warn("[bukutamu]", e);
    $("loadMsg").textContent = "Koneksi bermasalah. Coba muat ulang halaman ini.";
    return;
  }
  if (!kode) return show("sNoCode");
  show("sForm");
  $("fNama").focus();
}

/* ---------- step 1: form ---------- */
$("fNoHp").addEventListener("change", (e) => { $("fHp").disabled = e.target.checked; if (e.target.checked) $("fHp").value = ""; });
function readForm() {
  const nama = $("fNama").value.trim().replace(/\s+/g, " ");
  const org = $("fOrg").value.trim().replace(/\s+/g, " ");
  const hpRaw = $("fHp").value.replace(/[^\d+]/g, "");
  const ig = $("fIg").value.trim().replace(/^@+/, "").replace(/\s/g, "");
  if (!nama) return { err: "Nama wajib diisi." };
  if (!$("fNoHp").checked && hpRaw && (hpRaw.length < 8 || hpRaw.length > 16)) return { err: "Nomor HP sepertinya belum benar (8–16 angka)." };
  if (!$("fSetuju").checked) return { err: "Centang persetujuan dulu ya." };
  return { nama, org, hp: $("fNoHp").checked || !hpRaw ? "-" : hpRaw, ig: ig ? "@" + ig : "" };
}
let data = null;
$("sForm").addEventListener("submit", (e) => {
  e.preventDefault();
  const r = readForm();
  $("formErr").hidden = !r.err; $("formErr").textContent = r.err || "";
  if (r.err) return;
  data = r;
  openSelfie();
});

/* ---------- step 2: selfie ---------- */
const chips = $("filters");
chips.innerHTML = FILTERS.map((f) => `<button type="button" data-f="${f.id}">${f.label}</button>`).join("");
chips.addEventListener("click", (e) => {
  const b = e.target.closest("button"); if (!b || !booth) return;
  booth.filter = b.dataset.f; markChip();
});
const markChip = () => chips.querySelectorAll("button").forEach((b) => b.classList.toggle("on", booth && b.dataset.f === booth.filter));

async function openSelfie() {
  show("sSelfie");
  review(false);
  $("camErr").hidden = true;
  if (!booth) booth = new Booth($("video"), $("preview"));
  booth.name = data.nama; booth.org = data.org;
  markChip();
  if (booth.stream) return;
  try { await booth.start(); }
  catch (e) {
    console.warn("[bukutamu] kamera", e);
    $("camErr").hidden = false;
    $("camErr").textContent = "Kamera tidak bisa dibuka. Izinkan kamera di browser, atau lanjut tanpa foto.";
  }
}
function review(on) {
  $("shootRow").hidden = on; $("reviewRow").hidden = !on;
  $("shot").hidden = !on; $("preview").hidden = on; chips.hidden = on;
}
$("shootBtn").addEventListener("click", async () => {
  if (!booth || !booth.stream) return;
  $("shootBtn").disabled = true;
  photo = await booth.shoot((n) => { booth.countdown = n; });
  $("flash").classList.remove("go"); void $("flash").offsetWidth; $("flash").classList.add("go");
  $("shot").src = photo;
  review(true);
  $("shootBtn").disabled = false;
});
$("retake").addEventListener("click", () => { photo = ""; review(false); });
$("back").addEventListener("click", () => show("sForm"));
$("noPhoto").addEventListener("click", () => { photo = ""; submit(); });
$("send").addEventListener("click", submit);

/* ---------- submit ---------- */
let sending = false;
async function submit() {
  if (sending) return;
  sending = true;
  const btns = [$("send"), $("noPhoto")];
  btns.forEach((b) => (b.disabled = true));
  $("send").textContent = "Mengirim…";
  const { F, db } = fb;
  const now = F.serverTimestamp();
  const pub = { nama: data.nama, instansi: data.org, foto: photo, acara, dibuat: now };
  const priv = { nama: data.nama, hp: data.hp, instagram: data.ig, instansi: data.org, setuju: true, kode, acara, dibuat: now };
  try {
    const b = F.writeBatch(db);
    b.set(F.doc(db, "bukutamu_publik", user.uid), pub);
    b.set(F.doc(db, "bukutamu_privat", user.uid), priv);
    await Promise.race([b.commit(), new Promise((_, rej) => setTimeout(() => rej(new Error("timeout")), 25000))]);
    try { localStorage.setItem(DONE_KEY, "1"); } catch (e) { /* private mode */ }
    if (booth) booth.stop();
    done(pub, false);
  } catch (e) {
    console.warn("[bukutamu] simpan", e);
    const denied = e && e.code === "permission-denied";
    $("camErr").hidden = false;
    $("camErr").textContent = denied
      ? "Tidak bisa disimpan: kode QR tidak berlaku atau HP ini sudah pernah mengisi. Scan ulang QR di stand."
      : "Gagal mengirim (sinyal lemah?). Coba tekan Kirim lagi.";
    btns.forEach((b) => (b.disabled = false));
    $("send").textContent = "Kirim ✔";
  }
  sending = false;
}

function done(d, already) {
  show("sDone");
  $("doneTitle").textContent = already ? "Kamu sudah terdaftar ✅" : "Terima kasih! 🎉";
  $("doneMsg").innerHTML = already
    ? "HP ini sudah mengisi buku tamu sebagai <b></b>. Satu HP untuk satu tamu."
    : "Halo <b></b>, namamu sudah tercatat di buku tamu Nova-Band.";
  $("doneMsg").querySelector("b").textContent = d.nama;
  if (d.foto) {
    $("doneImg").src = d.foto; $("doneImg").hidden = false;
    $("save").href = d.foto; $("save").hidden = false;
  }
}

boot();
window.BukuTamu = { show, booth: () => booth };   // for testing
