/* Landing page: the 8 newest guestbook visitors (public cards only). The
   section is always there (how to sign the guestbook + link to /hadir/); the
   grid keeps its "be the first" note until someone signs, and any failure
   just leaves that note — the landing page never depends on it. */
import { watchGuests, waktu, esc } from "./fb.js";

const sec = document.getElementById("tamu"), grid = document.getElementById("tamuGrid");
if (sec && grid) {
  watchGuests(8, (rows) => {
    if (!rows.length) return;
    grid.innerHTML = rows.map((r) => `<article class="tamu-card">
      <img src="${r.foto ? esc(r.foto) : "assets/img/mascot-wink.webp"}" alt="" loading="lazy" class="${r.foto ? "" : "nophoto"}">
      <b>${esc(r.nama)}</b><span>${esc(r.instansi || "")}</span><time>${waktu(r.dibuat)}</time></article>`).join("");
  }, () => {}).catch(() => {});
}

/* "Buku Tamu" links: lazy images above this section load while the page
   scrolls and push it down, so re-check the landing point a few times. */
function goTamu(smooth) {
  if (!sec) return;
  sec.scrollIntoView({ behavior: smooth ? "smooth" : "auto", block: "start" });
  for (const t of [700, 1400, 2400]) {
    setTimeout(() => {
      const top = sec.getBoundingClientRect().top;
      if (Math.abs(top - 80) > 40) sec.scrollIntoView({ behavior: "auto", block: "start" });
    }, t);
  }
}
document.addEventListener("click", (e) => {
  const a = e.target.closest('a[href="#tamu"]');
  if (!a) return;
  e.preventDefault();
  history.replaceState(null, "", "#tamu");
  goTamu(true);
});
if (location.hash === "#tamu") addEventListener("load", () => goTamu(false));
