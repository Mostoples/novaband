# ============================================================
# Detailed Nova for the 10 s looping ad (tools/make-ad.py).
#   python blender/ad_nova.py                 # driver: prepares the band screen, renders, resumes after crashes
#   blender -b -P blender/ad_nova.py -- --job ad [--test 40]
# 240 frames @ 24 fps, transparent, 800x1000 -> build/ad_nova/f_####.png
# Loop: run (beat 1) -> stop gesture (beat 2) -> wave (beat 3) -> back to run.
# Every cycle length divides 240 frames, so frame 241 == frame 1.
# ============================================================
import math
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import nova_scene as NS  # noqa: E402

ROOT = NS.ROOT
N = 240
OUT = os.path.join(ROOT, "build", "ad_nova")
SCREEN = os.path.join(ROOT, "build", "ad_screen")


def prepare_screen():
    """Band screen frames for the loop: run page, then the alert page, then live."""
    os.makedirs(SCREEN, exist_ok=True)
    plan = [("run", 1, 80), ("alert", 70, 80), ("live", 20, 80)]
    k = 1
    for scen, first, count in plan:
        for i in range(count):
            src = os.path.join(ROOT, "build", "sim", scen, "f_%04d.png" % (first + i))
            shutil.copyfile(src, os.path.join(SCREEN, "f_%04d.png" % k))
            k += 1


if NS.bpy is None:
    prepare_screen()
    NS.drive(os.path.abspath(__file__), ["ad"], [OUT], extra=sys.argv[1:])
    sys.exit(0)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
arg = lambda n, d=None: ARGS[ARGS.index(n) + 1] if n in ARGS else d
MA, M = NS.MA, NS.M
TAU = 2 * math.pi


def sm(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def pose_at(f):
    ph = (f - 1) / N
    run = MA.run(((f - 1) % 24) / 24)
    stop = MA.alert(((f - 1) % 48) / 48)
    wave = MA.wave(((f - 1) % 48) / 48)
    segs = [(0.0, run), (1 / 3, stop), (2 / 3, wave)]
    X = 0.045                                            # blend half-width (phase)
    for i, (a, p) in enumerate(segs):
        b = segs[(i + 1) % 3][0] or 1.0
        nxt = segs[(i + 1) % 3][1]
        if a <= ph < b:
            if ph > b - X:
                return NS.blend(p, nxt, sm((ph - (b - X)) / (2 * X)))
            if ph < a + X:
                prv = segs[i - 1][1]
                return NS.blend(prv, p, sm((ph - (a - X)) / (2 * X)))
            return p
    return run


def main():
    sc, lids = NS.build_nova("smirk", "stand", screen=os.path.join(SCREEN, "f_0001.png"), screen_frames=N)
    tz, hh = 1.05, 1.2
    M.studio((0, 0, tz), hh, -18, 4, 70, (800, 1000))
    cam = sc.camera
    tgt = Vector((0, 0, tz))
    base = cam.location - tgt
    dist = base.length
    for f in range(1, N + 1):
        NS.key_pose(f, pose_at(f), lids)
        a = math.radians(-18 + 9 * math.sin(TAU * (f - 1) / N))
        e = math.radians(4)
        cam.location = tgt + Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e))) * dist
        cam.keyframe_insert("location", frame=f)
    NS.linear_keys()
    sc.cycles.samples = int(arg("--samples", "24"))
    sc.cycles.use_adaptive_sampling = True
    sc.render.fps = 24
    sc.frame_start, sc.frame_end = 1, N
    test = arg("--test")
    NS.render_frames(sc, OUT, N, int(test) if test else None)


main()
