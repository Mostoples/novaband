# ============================================================
# Nova seen from behind, for the "Nova Run" motion-capture runner (game.html):
# a 12-frame run cycle, a tucked jump and a slide, transparent.
#   python blender/game_sprites.py                    # driver (resumes after crashes)
#   blender -b -P blender/game_sprites.py -- --job sprites [--test 1]
# Output: build/game_sprites/f_####.png (frames 1-12 run, 13 jump, 14 slide)
#   -> tools/make-game-sprites.py packs them into assets/game/nova-sheet.webp
# ============================================================
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import nova_scene as NS  # noqa: E402

N = 14
OUT = os.path.join(NS.ROOT, "build", "game_sprites")

if NS.bpy is None:
    os.makedirs(OUT, exist_ok=True)
    NS.drive(os.path.abspath(__file__), ["sprites"], [OUT], extra=sys.argv[1:])
    sys.exit(0)

import bpy  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
arg = lambda n, d=None: ARGS[ARGS.index(n) + 1] if n in ARGS else d
MA, M = NS.MA, NS.M


def jump():
    """Knees tucked, arms up and out: reads clearly from behind."""
    p = MA.base()
    for s, sx in (("L", -1), ("R", 1)):
        p["hip." + s] = (-58, 4 * sx, 0)
        p["knee." + s] = (92, 0, 0)
        p["ankle." + s] = (20, 0, 0)
        p["shoulder." + s] = (-20, sx * 128, 0)
        p["elbow." + s] = (-25, 0, 0)
    p["head"] = (-10, 0, 0)
    return p, 0.0, 0, 0


def slide():
    """Deep symmetric crouch, arms tucked back: the duck-under pose."""
    p = MA.base()
    p["root"] = (12, 0, 0)
    for s, sx in (("L", -1), ("R", 1)):
        p["hip." + s] = (-105, 6 * sx, 0)
        p["knee." + s] = (128, 0, 0)
        p["ankle." + s] = (-30, 0, 0)
        p["shoulder." + s] = (35, sx * 28, 0)
        p["elbow." + s] = (-40, 0, 0)
    p["spine"] = (22, 0, 0)
    p["head"] = (-20, 0, 0)
    return p, -0.38, 0, 0


def pose_at(f):
    if f <= 12:
        rots, rz, bl, mo = MA.run((f - 1) / 12)
        return rots, rz - 0.06, 0, 0                       # keep the feet on the ground line
    return jump() if f == 13 else slide()


def main():
    sc, lids = NS.build_nova("happy", "stand")
    # behind Nova, a little above: the runner camera of the game
    M.studio((0, 0, 0.95), 1.22, 180, 12, 50, (400, 520))
    catcher = bpy.data.objects.get("catcher")
    if catcher:
        bpy.data.objects.remove(catcher, do_unlink=True)   # the game draws its own blob shadow
    sc.render.film_transparent = True
    for f in range(1, N + 1):
        NS.key_pose(f, pose_at(f), lids)
    NS.linear_keys()
    for fc in (fc for ob in bpy.data.objects if ob.animation_data and ob.animation_data.action
               for fc in ob.animation_data.action.fcurves):
        for k in fc.keyframe_points:
            k.interpolation = "CONSTANT"                   # every frame is its own pose
    sc.cycles.samples = int(arg("--samples", "24"))
    sc.cycles.use_adaptive_sampling = True
    sc.frame_start, sc.frame_end = 1, N
    test = arg("--test")
    NS.render_frames(sc, OUT, N, int(test) if test else None)


main()
