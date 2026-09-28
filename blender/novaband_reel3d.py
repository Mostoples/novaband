# ============================================================
# NovaBand — 3D shots for the showreel (Blender CLI, Cycles)
#
#   blender -b -P blender/novaband_reel3d.py
#   blender -b -P blender/novaband_reel3d.py -- --shots orbit --samples 24 --frames 20
#
# Renders three RGBA shots to build/reel/<shot>/frame_####.png:
#   orbit     camera arcs around the band, PPG LEDs beating at 1.5 Hz
#   exploded  the module stack separates into its layers
#   arm       the band on a clay mannequin arm
# The 2D compositor (tools/make-showreel.py) lays them on the white
# page background and adds the typography.
#
# Reuses the asset library's scene, materials and device builder so the
# video and the website look like the same product.
# ============================================================
import bpy
import math
import os
import sys
import importlib.util
from mathutils import Vector

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(SCRIPT_DIR)
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def arg(name, default=None):
    return ARGS[ARGS.index(name) + 1] if name in ARGS else default


spec = importlib.util.spec_from_file_location("nb_assets", os.path.join(SCRIPT_DIR, "novaband_assets.py"))
A = importlib.util.module_from_spec(spec)
spec.loader.exec_module(A)

SHOTS = (arg("--shots", "orbit,exploded,arm")).split(",")
SAMPLES = int(arg("--samples", 40))
RES = (int(arg("--width", 1920)), int(arg("--height", 1080)))
FRAME_CAP = int(arg("--frames", 0))      # >0 for quick previews
FPS = 30
LENGTH = {"orbit": 150, "exploded": 150, "arm": 120}


def ease(t):
    return t * t * (3 - 2 * t)


def camera_rig(centre, radius, az0, az1, el, frames, lens=60, fill=1.12):
    """Camera on an orbiting arm around the target; fits the vertical FOV of 16:9."""
    sc = bpy.context.scene
    target = bpy.data.objects.new("reel_target", None)
    target.location = centre
    sc.collection.objects.link(target)
    arm = bpy.data.objects.new("reel_arm", None)
    arm.location = centre
    sc.collection.objects.link(arm)

    cam_d = bpy.data.cameras.new("reel_cam")
    cam_d.lens = lens
    cam_d.sensor_fit = "HORIZONTAL"
    cam = bpy.data.objects.new("reel_cam", cam_d)
    sc.collection.objects.link(cam)
    vfov = 2 * math.atan(18.0 * RES[1] / RES[0] / lens)
    dist = radius / math.sin(vfov / 2) * fill
    e = math.radians(el)
    cam.parent = arm
    cam.location = (0, -math.cos(e) * dist, math.sin(e) * dist)
    t = cam.constraints.new("TRACK_TO")
    t.target = target
    t.track_axis = "TRACK_NEGATIVE_Z"
    t.up_axis = "UP_Y"
    sc.camera = cam

    arm.rotation_euler = (0, 0, math.radians(az0))
    arm.keyframe_insert("rotation_euler", frame=1)
    arm.rotation_euler = (0, 0, math.radians(az1))
    arm.keyframe_insert("rotation_euler", frame=frames)
    for fc in arm.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"
            kp.easing = "EASE_IN_OUT"
    return cam


def beat_leds(frames):
    """Same double-thump curve as the website hero and the old showreel."""
    period = FPS / 1.5
    for name, base, peak in (("NB_LedGreen", 3.0, 12.0), ("NB_LedIR", 1.5, 5.0)):
        m = bpy.data.materials.get(name)
        if not m:
            continue
        sock = m.node_tree.nodes["Principled BSDF"].inputs.get("Emission Strength")
        if sock is None:
            continue
        b = 0
        while b * period < frames:
            start = 1 + b * period
            for off, v in ((0.0, peak), (0.18, base * 0.75), (0.32, base + (peak - base) * 0.42),
                           (0.55, base), (0.95, base)):
                sock.default_value = v
                sock.keyframe_insert("default_value", frame=start + off * period)
            b += 1


def setup(name, spec_kw):
    sc = A.reset()
    A.MATS.clear()
    sc.cycles.samples = SAMPLES
    col = bpy.data.collections.new(name)
    sc.collection.children.link(col)
    return sc, col


def shot_orbit():
    sc, col = setup("orbit", {})
    root = A.build_device(col)
    root.rotation_euler = (math.radians(72), 0, math.radians(0))
    centre, radius = A.normalise(col)
    A.studio(centre, radius, dict(shadow=True, lens=60, az=0, el=34))
    beat_leds(LENGTH["orbit"])
    camera_rig(centre, radius, -38, 42, 30, LENGTH["orbit"], fill=0.78)
    return sc, LENGTH["orbit"]


def shot_exploded():
    sc, col = setup("exploded", {})
    A.build_device(col, exploded=True)
    # A.build_device placed every layer at its exploded height. Record that,
    # then key each layer from "tucked inside the case" to its final spot.
    top = A.NB.TOP_Z
    moving = {}
    for o in col.all_objects:
        base = o.name.split(".")[0]
        if o.type in {"MESH", "CURVE"} and not o.hide_render:
            moving[o] = o.location.z
    centre, radius = A.normalise(col)
    A.studio(centre, radius, dict(shadow=True, lens=60, az=0, el=26))
    n = LENGTH["exploded"]
    for i, (o, zf) in enumerate(sorted(moving.items(), key=lambda kv: kv[1])):
        base = o.name.split(".")[0]
        # assembled position: shell parts drop back by their lift, internals tuck inside
        o.location.z = zf - A.EXPLODE_LIFT[base] if base in A.EXPLODE_LIFT else top + 0.004
        o.keyframe_insert("location", index=2, frame=14)
        o.location.z = zf
        o.keyframe_insert("location", index=2, frame=int(70 + i * 3))
        for fc in o.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "BACK"
                kp.easing = "EASE_OUT"
                kp.back = 0.9
    beat_leds(n)
    camera_rig(centre, radius, -24, 14, 26, n, fill=0.95)
    return sc, n


def shot_arm():
    sc, col = setup("arm", {})
    A.build_device(col, arm=True)
    centre, radius = A.normalise(col)
    A.studio(centre, radius, dict(shadow=True, lens=60, az=0, el=22))
    beat_leds(LENGTH["arm"])
    camera_rig(centre, radius, 28, 70, 18, LENGTH["arm"], fill=0.58)
    return sc, LENGTH["arm"]


BUILDERS = {"orbit": shot_orbit, "exploded": shot_exploded, "arm": shot_arm}

for shot in SHOTS:
    print("\n[reel] building %s" % shot, flush=True)
    sc, n = BUILDERS[shot]()
    out = os.path.join(PROJECT, "build", "reel", shot)
    os.makedirs(out, exist_ok=True)
    sc.render.resolution_x, sc.render.resolution_y = RES
    sc.render.fps = FPS
    sc.frame_start = 1
    sc.frame_end = min(n, FRAME_CAP) if FRAME_CAP else n
    sc.render.filepath = os.path.join(out, "frame_")
    sc.render.use_persistent_data = True          # keeps BVH between frames: big speed-up
    bpy.ops.render.render(animation=True)
    print("[reel] %s done -> %s" % (shot, out), flush=True)
print("REEL3D DONE")
