"""
Record the Nova-Band app on an Android-sized screen (Pixel-class, 412 x 885 CSS px
under a 30 px status bar) for the showreel and the ads.

    python tools/serve.py   (or any static server on :8777)
    python tools/record-app.py            # -> build/app_rec/f_*.jpg + frames.json + marks.json

Chromium's CDP screencast pushes a frame on every repaint; frames.json keeps
their timestamps so the composer can resample to a constant frame rate.
marks.json holds the time each scripted step starts.
"""
import asyncio
import base64
import json
import os
import shutil
import time

from playwright.async_api import async_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "build", "app_rec")
URL = os.environ.get("NB_URL", "http://localhost:8777/app.html")
VW, VH, DPR = 412, 885, 2


async def main():
    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(OUT)
    frames, marks = [], {}
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="msedge")
        ctx = await b.new_context(viewport={"width": VW, "height": VH}, device_scale_factor=DPR, is_mobile=True,
                                  has_touch=True, color_scheme="dark",
                                  user_agent="Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 "
                                             "(KHTML, like Gecko) Chrome/129.0 Mobile Safari/537.36")
        pg = await ctx.new_page()
        await pg.goto(URL)
        await pg.wait_for_timeout(1500)                      # fonts, first paint
        await pg.evaluate("localStorage.setItem('novaband-theme','dark')")
        await pg.reload()
        await pg.wait_for_timeout(300)
        cdp = await ctx.new_cdp_session(pg)
        t0 = time.time()

        done = False

        async def ack(sid):
            try:
                await cdp.send("Page.screencastFrameAck", {"sessionId": sid})
            except Exception:
                pass

        def on_frame(ev):
            k = len(frames)
            path = os.path.join(OUT, "f_%05d.jpg" % k)
            with open(path, "wb") as f:
                f.write(base64.b64decode(ev["data"]))
            frames.append(round(time.time() - t0, 3))
            if not done:
                asyncio.ensure_future(ack(ev["sessionId"]))

        cdp.on("Page.screencastFrame", on_frame)
        await cdp.send("Page.startScreencast", {"format": "jpeg", "quality": 92, "maxWidth": VW * DPR,
                                                 "maxHeight": VH * DPR, "everyNthFrame": 1})

        def mark(name):
            marks[name] = round(time.time() - t0, 3)
            print("%-8s %6.2f" % (name, marks[name]), flush=True)

        async def scroll(y, ms=1400):
            await pg.evaluate("y => window.scrollTo({top: y, behavior: 'smooth'})", y)
            await pg.wait_for_timeout(ms)

        async def tab(panel):
            await pg.evaluate("p => { window.scrollTo(0, 0); document.querySelector('[data-panel=' + p + ']').click(); }", panel)
            await pg.wait_for_timeout(700)

        mark("home")
        await pg.wait_for_timeout(4200)                      # Nova waves, bubble types
        await scroll(560, 1500)
        await scroll(1250, 1700)
        await scroll(0, 1400)

        mark("connect")
        await pg.click("#btn-connect")
        await pg.wait_for_timeout(2200)
        await pg.click("#cx-sim")
        await pg.wait_for_timeout(1400)

        mark("run")
        await pg.click("#btn-session")
        await pg.wait_for_timeout(3000)
        await tab("p-live")
        await pg.wait_for_timeout(2500)
        await scroll(420, 1600)
        await pg.wait_for_timeout(1400)
        await scroll(0, 900)

        mark("alert")
        await tab("p-home")
        await pg.evaluate("""() => { const r = document.getElementById('thr-hr'); r.value = 150;
                                     r.dispatchEvent(new Event('input', {bubbles: true})); }""")
        await pg.evaluate("document.querySelector(\"[data-preset='88']\").click()")
        for _ in range(60):
            if await pg.query_selector("#alerts .alert.danger"):
                break
            await pg.wait_for_timeout(250)
        mark("alert_on")
        await pg.wait_for_timeout(3600)
        await pg.evaluate("document.querySelector('.rail').scrollIntoView({behavior: 'smooth', block: 'start'})")
        await pg.wait_for_timeout(2600)

        mark("ready")
        await pg.evaluate("document.querySelector(\"[data-preset='35']\").click()")
        await tab("p-ready")
        await pg.wait_for_timeout(2600)
        await scroll(380, 1500)
        await pg.wait_for_timeout(1200)

        mark("comm")
        await tab("p-comm")
        await pg.wait_for_timeout(2400)
        await scroll(300, 1400)
        await pg.wait_for_timeout(1000)

        mark("finish")
        await tab("p-home")
        await pg.click("#btn-session")
        await pg.wait_for_timeout(5200)
        mark("end")
        done = True
        await cdp.send("Page.stopScreencast")
        await pg.wait_for_timeout(300)
        await b.close()
    json.dump(frames, open(os.path.join(OUT, "frames.json"), "w"))
    json.dump(marks, open(os.path.join(OUT, "marks.json"), "w"), indent=1)
    print(len(frames), "frames", frames[-1], "s")


if __name__ == "__main__":
    asyncio.run(main())
