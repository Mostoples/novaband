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
  document.dispatchEvent(new CustomEvent("novaband:firebase-ready", { detail: { app } }));
} catch (err) {
  /* Offline, blocked, or the CDN is unreachable — the site is fully
     functional without Firebase, so this must never be fatal. */
  console.warn("[NovaBand] Firebase not initialised:", err && err.message);
}
