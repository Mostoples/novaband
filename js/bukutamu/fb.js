/* Buku tamu pameran — shared Firebase setup (named app, so it never clashes
   with js/firebase-init.js on the landing page). The web API key is not a
   secret; firestore.rules is what protects the data. */
const V = "12.4.0";
const base = "https://www.gstatic.com/firebasejs/" + V + "/";
const cfg = {
  apiKey: "AIzaSyB6JPBKeHo4lVuRHx91yS6NdvIqxWIJuT0",
  authDomain: "novaband-id.firebaseapp.com",
  projectId: "novaband-id",
  storageBucket: "novaband-id.firebasestorage.app",
  messagingSenderId: "257524197285",
  appId: "1:257524197285:web:2f710e395620d3ea47ea4c",
};

export async function firebase() {
  const [A, F] = await Promise.all([import(base + "firebase-app.js"), import(base + "firebase-firestore.js")]);
  const app = A.getApps().find((a) => a.name === "bukutamu") || A.initializeApp(cfg, "bukutamu");
  return { app, db: F.getFirestore(app), F };
}

export async function auth(app) {
  const Au = await import(base + "firebase-auth.js");
  const a = Au.getAuth(app);
  if (!a.currentUser) {
    await new Promise((res) => { const off = Au.onAuthStateChanged(a, () => { off(); res(); }); });
  }
  if (!a.currentUser) await Au.signInAnonymously(a);
  return a.currentUser;
}

/* public cards, newest first; calls back on every change */
export async function watchGuests(limitN, cb, onErr) {
  const { db, F } = await firebase();
  const q = F.query(F.collection(db, "bukutamu_publik"), F.orderBy("dibuat", "desc"), F.limit(limitN));
  return F.onSnapshot(q, (snap) => cb(snap.docs.map((d) => ({ id: d.id, ...d.data() }))), onErr);
}

export function waktu(ts) {
  const d = ts && ts.toDate ? ts.toDate() : new Date();
  return d.toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" });
}
export function tanggal(ts) {
  const d = ts && ts.toDate ? ts.toDate() : new Date();
  return d.toLocaleDateString("id-ID", { day: "numeric", month: "long", year: "numeric" });
}
export const esc = (s) => String(s || "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
