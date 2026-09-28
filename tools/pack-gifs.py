"""
Turn the Blender loops (build/deck/anim/<name>/f_####.png) into the animated
GIFs the deck embeds (deck/assets/anim/<name>.gif).

    python tools/pack-gifs.py              # everything
    python tools/pack-gifs.py heart bell   # a subset

Why GIF: it is the only animated image PowerPoint plays by itself, in the
editor and in the slide show, with no click and no video controls.

Why it still looks clean: GIF has no soft transparency, so every loop is
composited onto the deck's exact flat neumorphic background colour. The
palette is built so that colour is an exact entry — flat areas then map
with zero error and never dither — and the script verifies it. Placed on
a slide or a card of that same colour, the GIF has no visible edge.
"""
import glob
import json
import os
import sys

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "build", "deck", "anim")
OUT = os.path.join(ROOT, "deck", "assets", "anim")
os.makedirs(OUT, exist_ok=True)

BG = (238, 232, 233)          # the deck's neumorphic surface  #EEE8E9
WINE = (123, 32, 33)          # the closing slide              #7B2021
SHADOW_ON = {BG: (122, 88, 94), WINE: (58, 8, 14)}   # warm shadow tint per ground
FPS = 25
ONLY = set(sys.argv[1:])

# loops that also get a version matted on the wine closing slide
WINE_VARIANTS = {"device-spin", "orn-ring", "corner-rings", "heart"}

# Longest side after packing. Icons show at ~1.2 in (~170 px on a 1080p
# show), so 240 px keeps them crisp at 1.4x without bloating the deck.
MAX_SIDE = {"device-spin": 520, "orn-pills": 300, "orn-ring": 260,
            "corner-rings": 500, "corner-wave": 560}

# Slow loops keep every 2nd frame (12.5 fps): at their speed the step is
# invisible, and the file halves. Icons and the device keep all 25 fps.
# the wine variants sit small on the closing slide
WINE_SIDE = {"device-spin": 320}

FRAME_STEP = {"corner-wave": 2, "corner-rings": 2, "orn-pills": 2, "orn-ring": 2}
# The dotted wave is only rose dots + shadow: 64 colours hold it.
COLORS = {"corner-wave": 64}
ICON_SIDE = 240

# 128 colours: measured against 256 and 64 on the heart loop — 256 is 30%
# larger for no visible gain, 64 bands in the soft shadows.
NCOLORS = 128


def feather(a, inner=0.70):
    """
    Fade translucent (shadow) pixels toward the frame edge; objects stay untouched.
    The fade is ELLIPTICAL: a rectangular ramp leaves rectangular contours in the
    shadow's faint tail, which quantisation turns into a visible box.
    """
    h, w = a.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    r = np.sqrt(((xx - (w - 1) / 2) / (w / 2)) ** 2 + ((yy - (h - 1) / 2) / (h / 2)) ** 2)
    ramp = np.clip((1.0 - r) / (1.0 - inner), 0, 1)
    ramp = ramp * ramp * (3 - 2 * ramp)
    alpha = a[..., 3]
    shadowish = alpha < 0.8
    alpha[shadowish] *= ramp[shadowish]
    return a


def composite(rgba, ground):
    """Straight-alpha over a flat ground; shadow-catcher pixels take a warm tint."""
    a = rgba.astype(np.float32) / 255.0
    a = feather(a)
    rgb, alpha = a[..., :3], a[..., 3:4]
    # shadow catcher writes black with partial alpha: recolour it
    is_shadow = (alpha[..., 0] < 0.98) & (rgb.max(axis=2) < 0.08)
    tint = np.array(SHADOW_ON[ground], np.float32) / 255.0
    rgb[is_shadow] = tint
    g = np.array(ground, np.float32) / 255.0
    out = (np.clip(rgb * alpha + g * (1 - alpha), 0, 1) * 255 + 0.5).astype(np.uint8)
    # A shadow tail 1-3 levels off the ground reads as a flat, slightly darker
    # plateau once quantised. Snap it to the exact ground colour.
    near = np.abs(out.astype(np.int16) - np.array(ground, np.int16)).max(axis=2) <= 3
    out[near] = ground
    return out


def build_palette(frames, ground, ncol=None):
    ncol = ncol or NCOLORS
    """NCOLORS-1 adaptive colours from a sample of frames + the exact ground colour."""
    sample = frames[:: max(1, len(frames) // 12)]
    h = sum(f.shape[0] for f in sample)
    w = max(f.shape[1] for f in sample)
    montage = np.zeros((h, w, 3), np.uint8)
    montage[:] = ground
    y = 0
    for f in sample:
        montage[y:y + f.shape[0], :f.shape[1]] = f
        y += f.shape[0]
    q = Image.fromarray(montage).quantize(colors=ncol - 1, method=Image.Quantize.MEDIANCUT,
                                          dither=Image.Dither.NONE)
    pal = q.getpalette()[: (ncol - 1) * 3]
    pal += list(ground)                       # last index = exact ground
    img = Image.new("P", (1, 1))
    img.putpalette(pal)
    return img


def pack(name, ground, suffix=""):
    files = sorted(glob.glob(os.path.join(SRC, name, "f_*.png")))
    if not files:
        return None
    step = FRAME_STEP.get(name, 1)
    files = files[::step]
    frames = [composite(np.asarray(Image.open(f).convert("RGBA")), ground) for f in files]

    # crop to the union of everything that ever differs from the ground
    diff = np.zeros(frames[0].shape[:2], bool)
    for f in frames:
        diff |= np.abs(f.astype(np.int16) - np.array(ground, np.int16)).max(axis=2) > 2
    ys, xs = np.where(diff)
    pad = 6
    y0, y1 = max(ys.min() - pad, 0), min(ys.max() + pad + 1, diff.shape[0])
    x0, x1 = max(xs.min() - pad, 0), min(xs.max() + pad + 1, diff.shape[1])
    frames = [f[y0:y1, x0:x1] for f in frames]

    side = MAX_SIDE.get(name, ICON_SIDE)
    if suffix == "-wine":
        side = WINE_SIDE.get(name, side)
    h, w = frames[0].shape[:2]
    if max(h, w) > side:
        k = side / max(h, w)
        size = (max(1, round(w * k)), max(1, round(h * k)))
        frames = [np.asarray(Image.fromarray(f).resize(size, Image.LANCZOS)) for f in frames]

    ncol = COLORS.get(name, NCOLORS)
    pal = build_palette(frames, ground, ncol)
    out = []
    g = np.array(ground, np.uint8)
    for f in frames:
        # no dithering: its noise changes every frame and defeats GIF's
        # frame-to-frame compression; 255 wine/rose shades band very little
        q = Image.fromarray(f).quantize(palette=pal, dither=Image.Dither.NONE)
        # Pillow maps through a reduced-precision colour cube, so an exact match
        # is not guaranteed; pin every pixel that IS the ground to its exact entry.
        idx = np.array(q)
        idx[(f == g).all(axis=2)] = ncol - 1
        q2 = Image.fromarray(idx, "P")
        q2.putpalette(pal.getpalette())
        out.append(q2)

    # the whole point: the ground must come out bit-exact, or the GIF shows a box
    first = out[0].convert("RGB")
    corner = first.getpixel((0, 0))
    assert corner == ground, "%s: ground drifted to %s" % (name, corner)

    path = os.path.join(OUT, name + suffix + ".gif")
    out[0].save(path, save_all=True, append_images=out[1:], duration=int(1000 * step / FPS),
                loop=0, disposal=1)
    return dict(file=os.path.basename(path), w=int(x1 - x0), h=int(y1 - y0),
                frames=len(out), kb=round(os.path.getsize(path) / 1024))


def main():
    names = sorted(d for d in os.listdir(SRC) if os.path.isdir(os.path.join(SRC, d)))
    names = [n for n in names if not ONLY or n in ONLY]
    man_path = os.path.join(OUT, "manifest.json")
    manifest = json.load(open(man_path)) if os.path.exists(man_path) else {}
    total = 0
    for n in names:
        info = pack(n, BG)
        if not info:
            continue
        manifest[n] = info
        total += info["kb"]
        print("%-16s %4dx%-4d %3d fr %5d KB" % (n, info["w"], info["h"], info["frames"], info["kb"]))
        if n in WINE_VARIANTS:
            wi = pack(n, WINE, "-wine")
            manifest[n + "-wine"] = wi
            total += wi["kb"]
            print("%-16s %4dx%-4d %3d fr %5d KB" % (n + "-wine", wi["w"], wi["h"], wi["frames"], wi["kb"]))
    json.dump(manifest, open(man_path, "w"), indent=1)
    print("\n%d gifs, %.1f MB this run" % (len(names), total / 1024))


if __name__ == "__main__":
    main()
