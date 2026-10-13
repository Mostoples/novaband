"""
ENGLISH, full-resolution tour of the Nova-Band app for the portrait reel
(tools/make-portrait-reel.py). The app stays Indonesian; every on-screen text is
swapped to English on the fly from tools/app-strings-en.json.

Chromium's screencast only delivers CSS-pixel frames (412 px wide), so this
captures real screenshots at 1080 px instead and builds a 25 fps sequence
itself: scrolls are stepped one frame at a time (perfectly smooth), holds are
sampled at ~8 fps and repeated. taps.json lists where/when a finger taps, for
the touch ripples in the reel.

    python tools/serve.py 8777 &
    python tools/record-app-en.py         # -> build/app_rec_en/v_#####.jpg + taps.json
"""
import asyncio
import json
import os
import shutil

from playwright.async_api import async_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "build", "app_rec_en")
URL = os.environ.get("NB_URL", "http://localhost:8777/app.html")
VW, VH, DPR, FPS = 412, 892, 1080 / 412, 25
EN = json.load(open(os.path.join(ROOT, "tools", "app-strings-en.json"), encoding="utf-8"))

# exact text -> English; longer Indonesian phrases are also replaced inside dynamic strings
TRANSLATE = r"""(MAP) => {
  const phrases = Object.keys(MAP).filter(k => k.length >= 5 && MAP[k] !== k).sort((a, b) => b.length - a.length);
  const tr = (t) => {
    const k = t.replace(/\s+/g, ' ').trim();
    if (MAP[k] !== undefined) return t.match(/^\s*/)[0] + MAP[k] + t.match(/\s*$/)[0];
    let o = t;
    for (const p of phrases) if (o.includes(p)) o = o.split(p).join(MAP[p]);
    return o.replace(/(\d),(\d)/g, '$1.$2');
  };
  const fix = (root) => {
    const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    let n; while ((n = w.nextNode())) { const v = n.nodeValue; if (/[a-zA-Z]|\d,\d/.test(v)) { const t = tr(v); if (t !== v) n.nodeValue = t; } }
    root.querySelectorAll && root.querySelectorAll('[placeholder]').forEach(e => e.placeholder = tr(e.placeholder));
  };
  const go = () => { document.documentElement.lang = 'en'; fix(document.body); new MutationObserver(ms => { for (const m of ms) {
      if (m.type === 'characterData') { const v = m.target.nodeValue, t = tr(v); if (t !== v) m.target.nodeValue = t; }
      else m.addedNodes.forEach(x => x.nodeType === 3 ? (x.nodeValue = tr(x.nodeValue)) : fix(x)); } })
    .observe(document.body, { subtree: true, childList: true, characterData: true }); };
  if (document.body) go(); else addEventListener('DOMContentLoaded', go);
}"""


class Rec:
    def __init__(self, pg):
        self.pg, self.n, self.taps, self.marks = pg, 0, [], {}

    async def shot(self, repeat=1):
        b = await self.pg.screenshot(type="jpeg", quality=88)
        for _ in range(repeat):
            with open(os.path.join(OUT, "v_%05d.jpg" % self.n), "wb") as f:
                f.write(b)
            self.n += 1

    async def hold(self, sec):
        end = self.n + round(sec * FPS)
        while self.n < end:
            await self.shot(min(3, end - self.n))

    async def scroll_to(self, y1, sec):
        y0 = await self.pg.evaluate("scrollY")
        n = round(sec * FPS)
        for i in range(1, n + 1):
            k = i / n
            k = k * k * (3 - 2 * k)
            await self.pg.evaluate("y => window.scrollTo({top: y, behavior: 'instant'})", y0 + (y1 - y0) * k)
            await self.shot()
        self.taps.append({"f": self.n - n, "type": "swipe", "dir": 1 if y1 > y0 else -1, "len": n})

    async def tap(self, sel, js=False):
        box = await self.pg.evaluate("""s => { const e = document.querySelector(s); const r = e.getBoundingClientRect();
                                             return [r.x + r.width / 2, r.y + r.height / 2]; }""", sel)
        self.taps.append({"f": self.n, "type": "tap", "x": box[0] / VW, "y": box[1] / VH})
        await self.hold(0.25)
        await self.pg.evaluate("s => document.querySelector(s).click()", sel)
        await self.pg.wait_for_timeout(350)

    def mark(self, name):
        self.marks[name] = self.n


async def main():
    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(OUT)
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="msedge")
        ctx = await b.new_context(viewport={"width": VW, "height": VH}, device_scale_factor=DPR, is_mobile=True,
                                  has_touch=True, color_scheme="dark",
                                  user_agent="Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 "
                                             "(KHTML, like Gecko) Chrome/129.0 Mobile Safari/537.36")
        await ctx.add_init_script(script="(" + TRANSLATE + ")(" + json.dumps(EN, ensure_ascii=False) + ")")
        pg = await ctx.new_page()
        await pg.goto(URL)
        await pg.wait_for_timeout(1500)
        await pg.evaluate("localStorage.setItem('novaband-theme','dark')")
        await pg.reload()
        await pg.wait_for_timeout(1500)
        # off camera: connect the simulated band and start a run, so the screens are alive
        await pg.click("#btn-connect"); await pg.wait_for_timeout(1500)
        await pg.click("#cx-sim"); await pg.wait_for_timeout(1500)
        await pg.click("#btn-session"); await pg.wait_for_timeout(6000)
        await pg.evaluate("window.scrollTo(0, 0)")
        r = Rec(pg)
        page_h = lambda: pg.evaluate("document.documentElement.scrollHeight - innerHeight")

        r.mark("home")
        await r.hold(2.6)
        await r.scroll_to(min(1500, await page_h()), 3.6)
        await r.hold(1.0)
        await r.scroll_to(0, 1.6)

        r.mark("live")
        await r.tap('[data-panel="p-live"]')
        await r.hold(2.2)
        await r.scroll_to(min(700, await page_h()), 2.4)
        await r.hold(0.8)

        r.mark("alert")
        await pg.evaluate("""() => { const t = document.getElementById('thr-hr'); t.value = 150;
                                     t.dispatchEvent(new Event('input', {bubbles: true})); }""")
        await pg.evaluate("""document.querySelector('[data-preset="88"]').click()""")
        await r.tap('[data-panel="p-home"]')
        for _ in range(40):
            if await pg.query_selector("#alerts .alert.danger"):
                break
            await pg.wait_for_timeout(250)
        await pg.evaluate("window.scrollTo(0, 0)")
        await r.hold(3.2)

        r.mark("ready")
        await pg.evaluate("""document.querySelector('[data-preset="35"]').click()""")
        await r.tap('[data-panel="p-ready"]')
        await r.hold(2.0)
        await r.scroll_to(min(650, await page_h()), 2.4)
        await r.hold(1.2)

        r.mark("comm")
        await r.tap('[data-panel="p-comm"]')
        await r.hold(2.0)
        await r.scroll_to(min(700, await page_h()), 2.4)
        await r.hold(1.4)

        r.mark("end")
        await b.close()
    json.dump({"taps": r.taps, "marks": r.marks, "frames": r.n, "fps": FPS}, open(os.path.join(OUT, "taps.json"), "w"), indent=1)
    print(r.n, "frames =", round(r.n / FPS, 1), "s", r.marks)


if __name__ == "__main__":
    asyncio.run(main())
