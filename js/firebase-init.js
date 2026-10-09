/* ============================================================
   NovaBand — Firebase bootstrap
   ============================================================
   Loaded as a module (type="module"), so it never blocks rendering
   and an older browser simply skips it. Nothing on the site depends
   on Firebase yet: this only initialises the app so that analytics,
   Firestore or Auth can be added later without touching the pages.

   About the config below: a Firebase Web API key is NOT a secret.
   It identifies the project in client code and is meant to ship in
   the browser bundle. What actually protects the project is the
   Firestore/Storage security rules and the API key restrictions in
   the Google Cloud console — configure those before storing any
   real user data.
   ============================================================ */

const firebaseConfig = {
  apiKey: "AIzaSyB6JPBKeHo4lVuRHx91yS6NdvIqxWIJuT0",
  authDomain: "novaband-id.firebaseapp.com",
  projectId: "novaband-id",
  storageBucket: "novaband-id.firebasestorage.app",
  databaseURL: "https://novaband-id-default-rtdb.asia-southeast1.firebasedatabase.app",
  messagingSenderId: "257524197285",
  appId: "1:257524197285:web:2f710e395620d3ea47ea4c"
};

/* The site is framework-free, so the SDK comes from the CDN as an ES
   module rather than through a bundler. Pinned on purpose. */
const SDK = "https://www.gstatic.com/firebasejs/12.4.0/firebase-app.js";

try {
  const { initializeApp } = await import(SDK);
  const app = initializeApp(firebaseConfig);

  /* Exposed so future scripts can pick it up without re-initialising. */
  window.novabandFirebase = app;

  /* Run sessions: anonymous sign-in, then users/{uid}/sessions/{id} in Firestore (owner-only rules,
     see firestore.rules). Writes are keyed by id, so retrying a sync can never duplicate a session. */
  const V = "https://www.gstatic.com/firebasejs/12.4.0/";
  const [{ getAuth, signInAnonymously }, { getFirestore, doc, setDoc }, rtdb] =
    await Promise.all([import(V + "firebase-auth.js"), import(V + "firebase-firestore.js"), import(V + "firebase-database.js")]);
  const auth = getAuth(app), db = getFirestore(app), rt = rtdb.getDatabase(app);
  const uid = async () => auth.currentUser ? auth.currentUser.uid : (await signInAnonymously(auth)).user.uid;
  window.NovaCloud = {
    /* Realtime Database, read-only from the web: the ESPs write /devices/<role>/{live,info,runs}.
       watch(path, cb, lastN?) -> unsubscribe fn; cb(value|null). Reads are public (no login needed). */
    watch: (path, cb, lastN) => {
      const r = rtdb.ref(rt, path);
      return rtdb.onValue(lastN ? rtdb.query(r, rtdb.orderByKey(), rtdb.limitToLast(lastN)) : r,
        (snap) => cb(snap.val()), (e) => console.warn("[NovaBand] RTDB:", e && e.message));
    },
    saveSession: async (id, data) => {
      const u = await uid();
      await setDoc(doc(db, "users", u, "sessions", String(id)), data);
      return u;
    }
  };
  document.dispatchEvent(new CustomEvent("novaband:cloud-ready"));
  document.dispatchEvent(new CustomEvent("novaband:firebase-ready", { detail: { app } }));
} catch (err) {
  /* Offline, blocked, or the CDN is unreachable — the site is fully
     functional without Firebase, so this must never be fatal. */
  console.warn("[NovaBand] Firebase not initialised:", err && err.message);
}
