/* Landing page: the 8 newest guestbook visitors (public cards only). The
   section stays hidden until there is someone to show, and any failure just
   leaves it hidden — the landing page never depends on it. */
import { watchGuests, waktu, esc } from "./fb.js";

const sec = document.getElementById("tamu"), grid = document.getElementById("tamuGrid");
if (sec && grid) {
  watchGuests(8, (rows) => {
    sec.hidden = rows.length === 0;
    grid.innerHTML = rows.map((r) => `<article class="tamu-card">
      <img src="${r.foto ? esc(r.foto) : "assets/img/mascot-wink.webp"}" alt="" loading="lazy" class="${r.foto ? "" : "nophoto"}">
      <b>${esc(r.nama)}</b><span>${esc(r.instansi || "")}</span><time>${waktu(r.dibuat)}</time></article>`).join("");
  }, () => { sec.hidden = true; }).catch(() => { sec.hidden = true; });
}
