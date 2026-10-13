# ============================================================
# Nova for the recap's 3D opening (tools/make-intro.py), a tournament-style
# title: Nova sprints at a low orbiting camera, leaps, lands on the beat and
# holds a champion flex while the logo builds behind.
#   python blender/intro_nova.py                     # driver: renders, resumes after crashes
#   blender -b -P blender/intro_nova.py -- --job intro [--test 119] [--samples 20]
# 200 frames @ 25 fps, transparent (shadow catcher floor), 1920x1080
#   -> build/intro_nova/f_####.png
# ============================================================
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import nova_scene as NS  # noqa: E402

N = 200
LAND = 119                 # frame Nova touches down after the leap (the compositor's beat)
OUT = os.path.join(NS.ROOT, "build", "intro_nova")

if NS.bpy is None:
    os.makedirs(OUT, exist_ok=True)
    NS.drive(os.path.abspath(__file__), ["intro"], [OUT], extra=sys.argv[1:])
    sys.exit(0)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
arg = lambda n, d=None: ARGS[ARGS.index(n) + 1] if n in ARGS else d
MA, M = NS.MA, NS.M


def sm(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def lerp(a, b, w):
    return a + (b - a) * w


def pose_at(f):
    run = MA.run(((f - 1) % 24) / 24)
    cheer = MA.cheer(min(max((f - 84) / 50, 0), 1))
    flex = MA.flex(((max(f, 134) - 134) % 66) / 66)
    if f < 80:
        return run
    if f < 90:
        return NS.blend(run, cheer, sm((f - 80) / 10))
    if f < 128:
        return cheer
    if f < 140:
        return NS.blend(cheer, flex, sm((f - 128) / 12))
    return flex


# camera keys: frame, azimuth, elevation (deg), distance, target height
CAM = [(1, 78, -7, 4.9, 1.0), (84, 22, -3, 4.1, 1.0), (108, 6, 1, 4.6, 1.3),
       (134, -8, 3, 4.4, 1.05), (200, -15, 4, 4.0, 1.05)]


def cam_at(f):
    for (f0, *a), (f1, *b) in zip(CAM, CAM[1:]):
        if f0 <= f <= f1:
            w = sm((f - f0) / (f1 - f0))
            return [lerp(x, y, w) for x, y in zip(a, b)]
    return CAM[-1][1:]


def dramatic_lights():
    """Studio lights -> stadium night: warm gold key, hot red rims, a cool fill."""
    for name, col, k in (("key", (1.0, 0.86, 0.66), 1.3), ("rim", (1.0, 0.25, 0.3), 6.0),
                         ("rim2", (1.0, 0.72, 0.35), 5.5), ("fill", (0.55, 0.7, 1.0), 0.45), ("top", (1.0, 0.95, 0.9), 1.0)):
        o = bpy.data.objects.get(name)
        if o:
            o.data.color = col
            o.data.energy *= k


def main():
    sc, lids = NS.build_nova("happy", "stand")
    M.studio((0, 0, 1.0), 1.15, 78, -7, 35, (1920, 1080))
    dramatic_lights()
    sc.render.film_transparent = True
    sc.world.node_tree.nodes["Background"].inputs[1].default_value = 0.12
    cam = sc.camera
    tgt = bpy.data.objects["cam_target"]
    for f in range(1, N + 1):
        NS.key_pose(f, pose_at(f), lids)
        az, el, dist, tz = cam_at(f)
        a, e = math.radians(az), math.radians(el)
        tgt.location = Vector((0, 0, tz))
        tgt.keyframe_insert("location", frame=f)
        cam.location = tgt.location + Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e))) * dist
        cam.keyframe_insert("location", frame=f)
    NS.linear_keys()
    sc.cycles.samples = int(arg("--samples", "20"))
    sc.cycles.use_adaptive_sampling = True
    sc.render.fps = 25
    sc.render.use_motion_blur = True
    sc.render.motion_blur_shutter = 0.4
    sc.frame_start, sc.frame_end = 1, N
    test = arg("--test")
    NS.render_frames(sc, OUT, N, int(test) if test else None)


main()
