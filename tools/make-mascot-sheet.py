"""
Nova-Band mascot: character sheet + web cut-outs from the Blender renders.

    blender -b -P blender/mascot.py -- --shot all        # -> build/mascot/*.png
    python tools/make-mascot-sheet.py                    # -> build/mascot/nova-mascot-sheet.png
                                                         #    assets/img/mascot-sheet.webp
                                                         #    assets/img/mascot-{hero,run,wink,armband}.webp

Layout follows the brief: hero pose with tagline, logo + title, a
front/side/back/side turnaround, four expressions, a running pose, the
armband close-up, the palette, and a wine panel with the three pillars.
"""
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "build", "mascot")
FONTS = os.path.join(ROOT, "build", "fonts")
OUT_SHEET = os.path.join(SRC, "nova-mascot-sheet.png")
WEB = os.path.join(ROOT, "assets", "img")

W = H = 2048
BG = (238, 232, 233)
PANEL = (246, 242, 242)
CARD = (229, 223, 224)
WINE = (123, 32, 33)
WINE_D = (75, 7, 15)
CREAM = (232, 214, 200)
INK = (34, 28, 30)
GREY = (110, 100, 104)


def font(name, size):
    for n in (name, "Poppins-SemiBold.ttf"):
        p = os.path.join(FONTS, n)
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.truetype("arial.ttf", size)


def load(name):
    return Image.open(os.path.join(SRC, name + ".png")).convert("RGBA")


def trim(im, pad=6, alpha_min=24):
    """Crop to the figure. The shadow catcher leaves a faint alpha floor, so
    the box is taken from reasonably opaque pixels only."""
    a = im.split()[3].point(lambda v: 255 if v > alpha_min else 0)
    box = a.getbbox()
    if not box:
        return im
    l, t, r, b = box
    return im.crop((max(l - pad, 0), max(t - pad, 0), min(r + pad, im.width), min(b + pad, im.height)))


def fit(im, w, h):
    k = min(w / im.width, h / im.height)
    return im.resize((max(1, int(im.width * k)), max(1, int(im.height * k))), Image.LANCZOS)


def place(canvas, im, box, anchor="bottom"):
    x0, y0, x1, y1 = box
    im = fit(im, x1 - x0, y1 - y0)
    x = x0 + (x1 - x0 - im.width) // 2
    y = y1 - im.height if anchor == "bottom" else y0 + (y1 - y0 - im.height) // 2
    canvas.alpha_composite(im, (x, y))


def cover(im, w, h, focus=(0.5, 0.5)):
    """Scale to cover w x h and crop around `focus` (fractions)."""
    k = max(w / im.width, h / im.height)
    im = im.resize((int(im.width * k + 0.5), int(im.height * k + 0.5)), Image.LANCZOS)
    x = int((im.width - w) * focus[0])
    y = int((im.height - h) * focus[1])
    return im.crop((x, y, x + w, y + h))


def on_bg(im, col):
    bg = Image.new("RGBA", im.size, col + (255,))
    bg.alpha_composite(im)
    return bg


def rrect(d, box, r, fill):
    d.rounded_rectangle(box, r, fill=fill)


def sheared_text(canvas, xy, text, fnt, fill, shear=0.2):
    """Poppins has no italic; fake the sporty slant with a shear."""
    l, t, r, b = fnt.getbbox(text)
    w, h = r + int(h_pad := (b * shear)) + 8, b + 8
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(layer).text((int(h_pad), 0), text, font=fnt, fill=fill)
    layer = layer.transform(layer.size, Image.AFFINE, (1, shear, 0, 0, 1, 0), Image.BICUBIC)
    canvas.alpha_composite(layer, (int(xy[0]), int(xy[1])))
    return w


def n_mark(d, x, y, s, fill, cut=None):
    """The slanted 'N' brand mark, s = height."""
    k = 0.28 * s
    pts_l = [(x, y + s), (x + 0.26 * s, y), (x + 0.5 * s, y), (x + 0.24 * s, y + s)]
    pts_d = [(x + 0.26 * s, y), (x + 0.5 * s, y), (x + 0.86 * s, y + s), (x + 0.62 * s, y + s)]
    pts_r = [(x + 0.62 * s + k * 0.0, y + s), (x + 0.88 * s, y), (x + 1.12 * s, y), (x + 0.86 * s, y + s)]
    for p in (pts_l, pts_d, pts_r):
        d.polygon(p, fill=fill)


def speed_lines(d, x, y, n, length, gap, col, slope=-0.25, width=5):
    for i in range(n):
        L = length * (0.55 + 0.45 * ((i * 37) % 10) / 10)
        x0, y0 = x + (i % 3) * 30, y + i * gap
        d.line([(x0, y0), (x0 + L, y0 + L * slope)], fill=col, width=width)


def label(d, xy, text, size=26, fill=GREY, anchor="mm", spacing=6):
    f = font("Poppins-Medium.ttf", size)
    spaced = (" " * 0).join(text)
    d.text(xy, text.upper(), font=f, fill=fill, anchor=anchor)


def multiline_slant(canvas, x, y, lines, fnt, fill, step, shear=0.18, rot=0):
    layer = Image.new("RGBA", (900, step * len(lines) + 80), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for i, s in enumerate(lines):
        d.text((10 + i * 4, 10 + i * step), s, font=fnt, fill=fill)
    if rot:
        layer = layer.rotate(rot, resample=Image.BICUBIC, expand=True)
    canvas.alpha_composite(layer, (x, y))


def icon_disc(canvas, name, cx, cy, r):
    d = ImageDraw.Draw(canvas)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(255, 255, 255, 230), width=4)
    p = os.path.join(ROOT, "assets", "3d", name + ".webp")
    if os.path.exists(p):
        ic = Image.open(p).convert("RGBA")
        ic = fit(trim(ic, 2, 40), int(r * 1.25), int(r * 1.25))
        canvas.alpha_composite(ic, (cx - ic.width // 2, cy - ic.height // 2))


def main():
    shots = {n: load(n) for n in ("hero", "run", "front", "side", "back", "side2",
                                  "expr-smirk", "expr-wink", "expr-fierce", "expr-happy", "armband")}
    cv = Image.new("RGBA", (W, H), BG + (255,))
    d = ImageDraw.Draw(cv)
    G = 28                                  # gutter

    # ---------------------------------------------------------- left: hero
    L = (G, G, 760, 1330)
    rrect(d, L, 26, PANEL)
    fr = font("Fraunces-Italic.ttf", 60)
    multiline_slant(cv, L[0] + 22, L[1] + 18, ["Faster", "Healthier", "Stronger", "Together"], fr, WINE_D + (255,),
                    64, rot=8)
    speed_lines(d, L[0] + 40, L[1] + 330, 3, 110, 20, WINE + (255,), slope=-0.1, width=4)
    place(cv, trim(shots["hero"], 12, 8), (L[0] + 150, L[1] + 250, L[2] - 10, L[3] - 30))

    # ---------------------------------------------------------- top right: brand
    X0 = L[2] + G
    n_mark(d, X0 + 30, G + 70, 96, WINE)
    sheared_text(cv, (X0 + 170, G + 52), "NovaBand", font("Poppins-ExtraBold.ttf", 104), WINE + (255,), shear=0.16)
    fs = font("Poppins-Medium.ttf", 36)
    for i, s in enumerate(["An AIoT-Driven Upper-Arm Wearable",
                           "for Real-Time Physiological Monitoring",
                           "and Running Performance"]):
        d.text((X0 + 32, G + 222 + i * 50), s, font=fs, fill=INK)
    # mascot name tag
    tag_x = W - G - 300
    rrect(d, (tag_x, G + 60, W - G, G + 200), 70, WINE)
    d.text((tag_x + 150, G + 112), "NOVA", font=font("Poppins-ExtraBold.ttf", 58), fill=(255, 255, 255), anchor="mm")
    d.text((tag_x + 150, G + 160), "maskot resmi", font=font("Poppins-Medium.ttf", 26), fill=CREAM, anchor="mm")

    # ---------------------------------------------------------- turnaround
    T = (X0, 400, W - G, 1010)
    rrect(d, T, 22, CARD)
    cw = (T[2] - T[0]) // 4
    turn = [("front", "Front"), ("side", "Side"), ("back", "Back"), ("side2", "Side")]
    cuts = {n: trim(shots[n], 10, 8) for n, _ in turn}
    # one common scale so the four views read at the same height
    k = min(min((cw - 30) / im.width, (T[3] - T[1] - 94) / im.height) for im in cuts.values())
    for i, (n, lab) in enumerate(turn):
        x = T[0] + i * cw
        im = cuts[n].resize((int(cuts[n].width * k), int(cuts[n].height * k)), Image.LANCZOS)
        cv.alpha_composite(im, (x + (cw - im.width) // 2, T[3] - 70 - im.height))
        label(d, (x + cw // 2, T[3] - 36), lab, 26)

    # ---------------------------------------------------------- expressions
    label(d, (X0 + 4, 1046), "Expressions", 26, anchor="lm")
    E = (X0, 1072, W - G, 1330)
    ew = (E[2] - E[0] - 3 * 16) // 4
    for i, n in enumerate(("expr-smirk", "expr-wink", "expr-fierce", "expr-happy")):
        x = E[0] + i * (ew + 16)
        tile = cover(on_bg(shots[n], CARD), ew, E[3] - E[1], focus=(0.5, 0.35))
        mask = Image.new("L", tile.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, tile.width - 1, tile.height - 1), 18, fill=255)
        cv.paste(tile, (x, E[1]), mask)

    # ---------------------------------------------------------- bottom left: run
    B = (G, 1330 + G, 860, H - G)
    rrect(d, B, 26, PANEL)
    speed_lines(d, B[0] + 30, B[1] + 300, 9, 260, 34, (201, 163, 163, 255), slope=-0.18, width=5)
    multiline_slant(cv, B[0] + 24, B[1] + 20, ["Real-time", "data. Real", "progress."],
                    font("Fraunces-Italic.ttf", 50), WINE_D + (255,), 54, rot=8)
    place(cv, trim(shots["run"], 12, 8), (B[0] + 300, B[1] + 30, B[2] - 20, B[3] - 20))

    # ---------------------------------------------------------- armband close-up
    A_ = (B[2] + G, 1330 + G, 1420, H - G)
    tile = cover(on_bg(shots["armband"], CARD), A_[2] - A_[0], A_[3] - A_[1] - 64, focus=(0.42, 0.5))
    mask = Image.new("L", tile.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, tile.width - 1, tile.height - 1), 22, fill=255)
    cv.paste(tile, (A_[0], A_[1]), mask)
    label(d, (A_[0] + 6, A_[3] - 28), "Upper-arm wearable", 26, anchor="lm")

    # ---------------------------------------------------------- palette
    px = A_[2] + 70
    for i, c in enumerate((WINE_D, WINE, CREAM, INK)):
        cy = A_[1] + 80 + i * 130
        d.ellipse((px - 46, cy - 46, px + 46, cy + 46), fill=c)

    # ---------------------------------------------------------- wine panel
    P = (px + 90, 1330 + G, W - G, H - G)
    rrect(d, P, 18, WINE_D)
    fb = font("Poppins-Medium.ttf", 26)
    rows = (("heart", ["Real-time", "physiological", "monitoring"]),
            ("footsteps", ["Running", "performance", "tracking"]),
            ("chip", ["AIoT", "powered"]))
    y = P[1] + 50
    for icon, lines in rows:
        icon_disc(cv, icon, P[0] + 74, y + 48, 42)
        for k, s in enumerate(lines):
            d.text((P[0] + 140, y + 6 + k * 32), s.upper(), font=fb, fill=(246, 236, 236))
        y += 150
        d.line([(P[0] + 30, y - 22), (P[2] - 30, y - 22)], fill=(255, 255, 255, 110), width=2)
    sheared_text(cv, (P[0] + 40, P[3] - 190), "NovaBand", font("Fraunces-Italic.ttf", 72), (255, 255, 255, 255),
                 shear=0.0)
    d.text((P[2] - 34, P[3] - 76), "YOUR PERFORMANCE,", font=font("Poppins-Medium.ttf", 22), fill=CREAM,
           anchor="rm")
    d.text((P[2] - 34, P[3] - 46), "OUR PRIORITY.", font=font("Poppins-Medium.ttf", 22), fill=CREAM, anchor="rm")

    cv.convert("RGB").save(OUT_SHEET)
    os.makedirs(WEB, exist_ok=True)
    cv.convert("RGB").resize((1400, 1400), Image.LANCZOS).save(os.path.join(WEB, "mascot-sheet.webp"),
                                                               quality=86, method=6)
    # transparent cut-outs for the site (shadow kept, trimmed)
    for n, out, h in (("hero", "mascot-hero", 1100), ("run", "mascot-run", 900),
                      ("expr-wink", "mascot-wink", 640), ("armband", "mascot-armband", 800)):
        im = shots[n] if n.startswith(("expr", "armband")) else trim(shots[n], 16, 4)
        if im.height > h:
            im = im.resize((int(im.width * h / im.height), h), Image.LANCZOS)
        im.save(os.path.join(WEB, out + ".webp"), quality=88, method=6)
    print("sheet ->", OUT_SHEET)


if __name__ == "__main__":
    main()
