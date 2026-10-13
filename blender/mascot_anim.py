# ============================================================
# Nova the mascot, animated: short looping clips for the app and the
# explainer film. Reuses the procedural mascot from mascot.py and keys
# the joint empties frame by frame (forward kinematics), plus blinking
# eyelids and a talking mouth on small pivot empties.
#
#   python blender/mascot_anim.py --anim all --samples 32        # every clip, one Blender each
#   blender -b -P blender/mascot_anim.py -- --anim wave --test 12  # one test frame
#
# Clips: idle, wave, run, talk, flex, thumbs, cheer, alert
# Output: build/mascot_anim/<clip>/f_####.png (transparent, shadow catcher)
# ============================================================
import math
import os
import sys

ANIMS = ["idle", "wave", "run", "talk", "flex", "thumbs", "cheer", "alert"]

try:
    import bpy
except ImportError:
    import subprocess
    import time
    blender = os.environ.get("BLENDER", r"C:\Program Files\Blender Foundation\Blender 4.0\blender.exe")
    argv = sys.argv[1:]
    which = argv[argv.index("--anim") + 1] if "--anim" in argv else "all"
    rest = [a for i, a in enumerate(argv) if a != "--anim" and (i == 0 or argv[i - 1] != "--anim")]
    out_root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "build", "mascot_anim")
    for n in (ANIMS if which == "all" else which.split(",")):
        t0 = time.time()
        d = os.path.join(out_root, n)
        for attempt in range(40):         # Blender 4.0 sometimes crashes mid-clip; resume where it stopped
            r = subprocess.run([blender, "-b", "-P", os.path.abspath(__file__), "--", "--anim", n] + rest,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if r.returncode == 0:
                break
        ok = len([f for f in os.listdir(d) if f.startswith("f_") and os.path.getsize(os.path.join(d, f)) > 0])
        print("%-7s %3d frames  exit %d  %5.0fs" % (n, ok, r.returncode, time.time() - t0), flush=True)
    sys.exit(0)

import importlib.util
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def arg(name, default=None):
    return ARGS[ARGS.index(name) + 1] if name in ARGS else default


ANIM = arg("--anim", "idle")
SAMPLES = int(arg("--samples", 32))
TEST = arg("--test")
RES = [int(v) for v in arg("--res", "720x900").split("x")]
OUT = os.path.join(os.path.dirname(HERE), "build", "mascot_anim", ANIM)
os.makedirs(OUT, exist_ok=True)

spec = importlib.util.spec_from_file_location("nb_mascot", os.path.join(HERE, "mascot.py"))
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)
M.EXPR["talk"] = (-34, -34, -3, "open", (0.0, 0.0))
rad = math.radians
TAU = 2 * math.pi

STAND = M.POSES["stand"]


def loop(keys, t):
    """Periodic Catmull-Rom through evenly spaced keys, t in [0, 1)."""
    n = len(keys)
    x = (t % 1.0) * n
    i = int(x)
    u = x - i
    p0, p1, p2, p3 = keys[(i - 1) % n], keys[i % n], keys[(i + 1) % n], keys[(i + 2) % n]
    return 0.5 * ((2 * p1) + (-p0 + p2) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u * u +
                  (-p0 + 3 * p1 - 3 * p2 + p3) * u * u * u)


def smooth(a, b, x):
    x = min(max((x - a) / (b - a), 0.0), 1.0)
    return x * x * (3 - 2 * x)


def bump(t, at, w):
    """0..1..0 around `at` (periodic), half-width w."""
    d = abs(((t - at + 0.5) % 1.0) - 0.5)
    return smooth(w, 0.0, d)


def blink(t, *ats):
    return max(bump(t, a, 0.045) for a in ats)


def base():
    return {j: tuple(v) for j, v in STAND.items()}


# --------------------------------------------------------------- clips
# Each returns (frames, expression, build pose, camera, fn(t) -> (joint rotations, root z, blink, mouth))
def idle(t):
    s = math.sin(TAU * t)
    p = base()
    p["spine"] = (1.5 * s, 0, 2.5 * math.sin(TAU * t + 1))
    p["root"] = (0, 0, 2.5 * math.sin(TAU * t))
    p["head"] = (-2 + 2.5 * math.sin(2 * TAU * t), 0, 12 * math.sin(TAU * t + 0.6))
    p["shoulder.L"] = (0, -7 - 2 * s, 0)
    p["shoulder.R"] = (0, 7 + 2 * s, 0)
    p["elbow.L"] = (-8 - 5 * s, 0, 0)
    p["elbow.R"] = (-8 - 5 * s, 0, 0)
    return p, 0.006 * s, blink(t, 0.55), 0


def wave(t):
    w = math.sin(2 * TAU * t)
    p = base()
    p["shoulder.R"] = (-14, 100, 0)
    p["elbow.R"] = (0, 52 + 22 * w, 0)
    p["wrist.R"] = (0, 12 * math.sin(2 * TAU * t - 0.6), 0)
    p["spine"] = (0, -3 + 1.5 * w, 3)
    p["head"] = (-3, -7 + 3 * math.sin(TAU * t), -6)
    p["shoulder.L"] = (0, -8, 0)
    return p, 0.008 * abs(w), blink(t, 0.7), 0


def run(t):
    def leg(ph):
        return {"hip": loop([-72, -22, 32, -18], ph), "knee": loop([95, 30, 82, 118], ph),
                "ankle": loop([-12, 6, 28, 18], ph)}
    L, R = leg(t), leg(t + 0.5)
    p = {"root": (14, 0, 0), "neck": (-6, 0, 0)}
    for s, d in (("L", L), ("R", R)):
        p["hip." + s] = (d["hip"], 0, 0)
        p["knee." + s] = (d["knee"], 0, 0)
        p["ankle." + s] = (d["ankle"], 0, 0)
    p["shoulder.L"] = (loop([48, 0, -58, 0], t), -10, 0)
    p["elbow.L"] = (loop([-86, -92, -96, -92], t), 0, 0)
    p["shoulder.R"] = (loop([-58, 0, 48, 0], t), 10, 0)
    p["elbow.R"] = (loop([-96, -92, -86, -92], t), 0, 0)
    p["spine"] = (0, 0, 6 * math.cos(TAU * t))
    p["head"] = (-2, 0, -5 * math.cos(TAU * t))
    return p, 0.06 + 0.035 * math.cos(2 * TAU * t), 0, 0


def talk(t):
    s = math.sin(TAU * t)
    p = base()
    p["shoulder.L"] = (-28 + 6 * math.sin(2 * TAU * t), -48 + 8 * s, 0)
    p["elbow.L"] = (-42 + 10 * math.sin(2 * TAU * t + 1), 0, 0)
    p["wrist.L"] = (0, 0, -25)
    p["shoulder.R"] = (-4, 9 + 2 * s, 0)
    p["elbow.R"] = (-16 - 6 * math.sin(2 * TAU * t), 0, 0)
    p["head"] = (2.5 * math.sin(4 * TAU * t), 0, 9 + 7 * s)
    p["spine"] = (1.2 * s, 0, 3 + 2 * s)
    # syllables: a few overlapping beats, closed briefly between phrases
    m = abs(math.sin(9 * TAU * t)) * (0.55 + 0.45 * abs(math.sin(3 * TAU * t + 0.4)))
    m *= smooth(0.0, 0.06, (t + 0.03) % 1.0) * smooth(0.0, 0.06, (0.97 - t) % 1.0)
    m *= 1 - bump(t, 0.5, 0.05)
    return p, 0.004 * s, blink(t, 0.3, 0.8), m


def flex(t):
    s = math.sin(TAU * t)
    p = base()
    p["shoulder.L"] = (0, -84 + 4 * s, -90)            # ZYX: twist so the band faces the camera, then lift
    p["elbow.L"] = (95 + 12 * math.sin(2 * TAU * t), 0, 0)
    p["head"] = (-6 + 4 * s, 0, 18 + 10 * s)
    p["spine"] = (0, 3, -6)
    p["shoulder.R"] = (0, 12, 0)
    p["elbow.R"] = (-20, 0, 0)
    return p, 0.006 * abs(math.sin(2 * TAU * t)), blink(t, 0.62), 0


def thumbs(t):
    s2 = math.sin(2 * TAU * t)
    p = {k: tuple(v) for k, v in M.POSES["thumbs"].items()}
    p["shoulder.R"] = (-22 + 7 * s2, 32, 10)
    p["elbow.R"] = (-122 + 9 * s2, 0, 0)
    p["head"] = (-3 + 4 * s2, 6, 4 + 4 * math.sin(TAU * t))
    return p, 0.01 * abs(s2), blink(t, 0.4), 0


def cheer(t):
    air = smooth(0.2, 0.3, t) * smooth(0.72, 0.62, t)
    z = 0.24 * max(0.0, math.sin(math.pi * (t - 0.24) / 0.46)) if 0.24 < t < 0.7 else 0.0
    c = bump(t, 0.13, 0.11) + bump(t, 0.8, 0.11)
    p = base()
    for s, sx in (("L", -1), ("R", 1)):
        p["hip." + s] = (-38 * c + 10 * air, 3 * sx, 0)
        p["knee." + s] = (64 * c + 25 * air, 0, 0)
        p["ankle." + s] = (-26 * c + 15 * air, 0, 0)
        p["shoulder." + s] = (-10 * air, sx * (7 + 148 * air), 0)
        p["elbow." + s] = (-10 - 20 * c, 0, 0)
    p["head"] = (-8 * air + 4 * c, 0, 0)
    p["spine"] = (6 * c, 0, 0)
    return p, z - 0.11 * c, 0, 0


def alert(t):
    p = base()
    p["shoulder.R"] = (-78 + 4 * math.sin(2 * TAU * t), 12, 0)
    p["elbow.R"] = (-38, 0, 0)
    p["wrist.R"] = (0, 0, 0)
    p["head"] = (2, 0, 9 * math.sin(2 * TAU * t))
    p["spine"] = (-2, 0, 0)
    return p, 0.0, blink(t, 0.85), 0


CLIPS = {
    # name: (frames, expression, build pose (tail / thumb), camera (target z, half h, az, el), fn)
    "idle":   (72, "smirk", "stand", (1.0, 1.1, -18, 4), idle),
    "wave":   (48, "happy", "stand", (1.08, 1.2, -16, 4), wave),
    "run":    (24, "fierce", "run", (1.02, 1.12, 38, 5), run),
    "talk":   (96, "talk", "stand", (1.0, 1.1, -14, 4), talk),
    "flex":   (48, "smirk", "stand", (1.05, 1.15, -20, 4), flex),
    "thumbs": (48, "smirk", "thumbs", (1.0, 1.1, -24, 5), thumbs),
    "cheer":  (48, "happy", "stand", (1.2, 1.32, -14, 4), cheer),
    "alert":  (48, "fierce", "stand", (1.02, 1.12, -14, 4), alert),
}


# --------------------------------------------------------------- pivots for lids / mouth
def pivot(name, M_rest, objs):
    """An oriented frame on the head (rest pose) with a child we can key; reparent objs to the child."""
    drop = Matrix.Translation(Vector((0, 0, -M.HEAD_DROP)))
    frame = bpy.data.objects.new(name + "_frame", None)
    M.COLL.objects.link(frame)
    frame.parent = M.EMP["head"]
    bpy.context.view_layer.update()
    frame.matrix_world = drop @ M_rest
    ctl = bpy.data.objects.new(name, None)
    M.COLL.objects.link(ctl)
    ctl.parent = frame
    ctl.rotation_mode = "XYZ"
    bpy.context.view_layer.update()
    for o in objs:
        mw = o.matrix_world.copy()
        o.parent = ctl
        o.matrix_parent_inverse = ctl.matrix_world.inverted() @ mw @ o.matrix_basis.inverted()
    return ctl


def build(clip):
    frames, expr, pose, cam, fn = CLIPS[clip]
    sc = M.A.reset()
    M.COLL = bpy.data.collections.new("mascot")
    sc.collection.children.link(M.COLL)
    M.materials()
    M.build_rig()
    M.build_torso()
    M.build_chest_logo()
    M.build_hips()
    for s in ("L", "R"):
        M.build_arm(s)
        M.build_hand(s, thumb_up=(pose == "thumbs" and s == "R"))
        M.build_leg(s)
    M.build_tail(pose)
    M.build_head(expr)
    bpy.context.view_layer.update()

    lids = {}
    lid_open = M.EXPR[expr][:2]
    slant = M.EXPR[expr][2]
    for s, sx, deg in (("L", 1, lid_open[0]), ("R", -1, lid_open[1])):
        o = bpy.data.objects.get("Lid." + s)
        if o is None or deg > 60:
            continue
        c = Vector((0.08 * sx, -0.168, 1.708))
        Mr = (Matrix.Translation(c) @ Matrix.Rotation(rad(15 * sx), 4, "Z")
              @ Matrix.Rotation(rad(-slant * sx), 4, "Y"))
        lids[s] = (pivot("LidPivot." + s, Mr, [o]), 78 - deg)
    mouth = None
    mo = [bpy.data.objects.get(n) for n in ("MouthOpen", "Tongue")]
    mo = [o for o in mo if o]
    if expr == "talk" and mo:
        y = M.front_y(0, 1.566)
        mouth = pivot("MouthPivot", Matrix.Translation(Vector((0, y, 1.575))), mo)

    if clip == "flex":
        M.EMP["shoulder.L"].rotation_mode = "ZYX"

    tz, hh, az, el = cam
    M.studio((0, 0, tz), hh, az, el, 70, RES)
    sc.cycles.samples = SAMPLES
    sc.cycles.use_adaptive_sampling = True
    sc.render.fps = 24
    sc.frame_start, sc.frame_end = 1, frames

    for f in range(1, frames + 1):
        t = (f - 1) / frames
        rots, rz, bl, m = fn(t)
        for j, e in M.EMP.items():
            x, y_, z = rots.get(j, (0, 0, 0))
            e.rotation_euler = (rad(x), rad(y_), rad(z))
            e.keyframe_insert("rotation_euler", frame=f)
        root = M.EMP["root"]
        root.location = (0, 0, rz)
        root.keyframe_insert("location", frame=f)
        for s, (ctl, close) in lids.items():
            ctl.rotation_euler = (rad(close * bl), 0, 0)
            ctl.keyframe_insert("rotation_euler", frame=f)
        if mouth:
            mouth.scale = (1.0, 1.0, 0.12 + 0.95 * m)
            mouth.keyframe_insert("scale", frame=f)
    for ob in bpy.data.objects:
        if ob.animation_data and ob.animation_data.action:
            for fc in ob.animation_data.action.fcurves:
                for k in fc.keyframe_points:
                    k.interpolation = "LINEAR"
    return sc, frames


def main():
    sc, frames = build(ANIM)
    todo = [int(TEST)] if TEST else range(1, frames + 1)
    for f in todo:
        path = os.path.join(OUT, ("test_%04d.png" if TEST else "f_%04d.png") % f)
        if not TEST and os.path.exists(path) and os.path.getsize(path) > 0:
            continue
        sc.frame_set(f)
        sc.render.filepath = path
        bpy.ops.render.render(write_still=True)
    print("ANIM DONE", ANIM, frames)


if __name__ == "__main__":
    main()
