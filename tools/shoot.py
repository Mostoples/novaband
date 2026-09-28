"""
Visual QA: full-page screenshots of the site with the local Chrome.

    python -m http.server 5174 --bind 127.0.0.1     (in another shell)
    python tools/shoot.py                            -> build/shots/*.png

Scrolls each page top to bottom first so scroll-reveal animations and
lazy images fire, then captures the whole page. Also walks every tab of
the app and records console errors, which are printed at the end.
"""
import os
import sys
from playwright.sync_api import sync_playwright

BASE = os.environ.get("NB_BASE", "http://127.0.0.1:5174")
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "build", "shots")
os.makedirs(OUT, exist_ok=True)
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
ONLY = sys.argv[1:] or ["index", "app", "mobile", "dark"]

errors = []


def settle(page):
    """Scroll through the page so IntersectionObserver-driven content appears."""
    h = page.evaluate("document.documentElement.scrollHeight")
    y = 0
    while y < h:
        page.mouse.wheel(0, 700)
        page.wait_for_timeout(120)
        y += 700
        h = page.evaluate("document.documentElement.scrollHeight")
    page.wait_for_timeout(900)
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(700)


def watch(page, tag):
    page.on("console", lambda m: m.type == "error" and errors.append("[%s] console: %s" % (tag, m.text)))
    page.on("pageerror", lambda e: errors.append("[%s] pageerror: %s" % (tag, e)))
    page.on("requestfailed", lambda r: errors.append("[%s] failed: %s" % (tag, r.url)))


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROME, args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"])

    if "index" in ONLY:
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        watch(page, "index")
        page.goto(BASE + "/index.html", wait_until="networkidle")
        settle(page)
        page.screenshot(path=os.path.join(OUT, "index-hero.png"))
        # Chrome caps a full-page capture near 16k px, and this page is taller,
        # so walk it in viewport-sized tiles instead.
        page.add_style_tag(content="html{scroll-behavior:auto!important}")
        total = page.evaluate("document.documentElement.scrollHeight")
        y, k = 0, 0
        while y < total:
            page.evaluate("window.scrollTo(0, %d)" % y)
            page.wait_for_timeout(450)
            page.screenshot(path=os.path.join(OUT, "idx_%02d.png" % k))
            y += 860
            k += 1
        page.close()

    if "dark" in ONLY:
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        watch(page, "dark")
        page.add_init_script("localStorage.setItem('novaband-theme','dark')")
        page.goto(BASE + "/index.html", wait_until="networkidle")
        settle(page)
        page.screenshot(path=os.path.join(OUT, "index-dark-hero.png"))
        page.goto(BASE + "/app.html", wait_until="networkidle")
        page.wait_for_timeout(1200)
        page.screenshot(path=os.path.join(OUT, "app-dark.png"), full_page=True)
        page.close()

    if "mobile" in ONLY:
        page = browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2)
        watch(page, "mobile")
        page.goto(BASE + "/index.html", wait_until="networkidle")
        settle(page)
        page.screenshot(path=os.path.join(OUT, "mobile-index.png"), full_page=True)
        page.goto(BASE + "/app.html", wait_until="networkidle")
        page.wait_for_timeout(1200)
        page.screenshot(path=os.path.join(OUT, "mobile-app.png"), full_page=True)
        page.close()

    if "app" in ONLY:
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        watch(page, "app")
        page.goto(BASE + "/app.html", wait_until="networkidle")
        page.wait_for_timeout(800)
        page.click("#btn-session")                 # connect + start the simulated run
        page.wait_for_timeout(4000)
        for panel in ["p-home", "p-live", "p-ready", "p-comm", "p-device", "p-account"]:
            page.click('.side-item[data-panel="%s"]' % panel)
            page.wait_for_timeout(1400)
            page.screenshot(path=os.path.join(OUT, "app-%s.png" % panel), full_page=True)
        page.close()

    browser.close()

print("shots ->", OUT)
print("ERRORS:", len(errors))
for e in errors:
    print("  ", e)
