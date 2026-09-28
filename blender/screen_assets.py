# ============================================================
# Nova-Band — Blender assets for the T-Display-S3 screen (320 x 170)
#
#   blender -b -P blender/screen_assets.py -- [--only splash,bg,spin] [--samples 64]
#
#   splash  60 frames, 2.4 s at 25 fps: the band in a dark studio, bokeh
#           particles in front of and behind it, the focus racking from the
#           near particles onto the device while it turns and the LED fires.
#           The left third stays dark: the firmware writes the wordmark there.
#   bg      the Sketchfab gym, focused 30 cm from the lens at f/0.9 so the
#           whole room dissolves into bokeh; 480 px wide for page parallax.
#   spin    36-frame turntable of the band, transparent, for the UI sprite.
#
# Renders at 2x and lets tools/fw_assets.py downsample (clean edges on a
# 1.9" panel). Output: build/screen/<name>/...
# ============================================================
import bpy
import importlib.util
import math
import os
import sys
from mathutils import Vector

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(SCRIPT_DIR)
OUT = os.path.join(PROJECT, "build", "screen")
SF = os.path.join(PROJECT, "build", "sketchfab")
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
arg = lambda k, d=None: ARGS[ARGS.index(k) + 1] if k in ARGS else d
ONLY = set(filter(None, (arg("--only", "") or "").split(",")))
SAMPLES = int(arg("--samples", 64))
TAU = 2 * math.pi

sys.argv = sys.argv[:1]          # novaband_hero parses its own args at import
spec = importlib.util.spec_from_file_location("nb_hero", os.path.join(SCRIPT_DIR, "novaband_hero.py"))
H = importlib.util.module_from_spec(spec)
spec.loader.exec_module(H)
A = H.A
srgb = A.srgb


def base_scene(transparent):
    sc = A.reset()
    A.MATS.clear()
    sc.render.film_transparent = transparent
    sc.cycles.samples = SAMPLES
    sc.render.use_persistent_data = True
    return sc


def emissive(name, rgb, strength):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    e = nt.nodes.new("ShaderNodeEmission")
    e.inputs[0].default_value = rgb
    e.inputs[1].default_value = strength
    o = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(e.outputs[0], o.inputs[0])
    return m


def camera(sc, loc, target, lens, fstop=None, focus=None):
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    sc.collection.objects.link(cam)
    cam.data.lens = lens
    cam.location = loc
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    if fstop:
        cam.data.dof.use_dof = True
        cam.data.dof.aperture_fstop = fstop
        cam.data.dof.aperture_blades = 7          # heptagon bokeh, like a real lens
        cam.data.dof.aperture_ratio = 1.0
        cam.data.dof.focus_distance = focus
    sc.camera = cam
    return cam


def area(sc, name, loc, target, size, power, color=(1, 1, 1), sy=None):
    d = bpy.data.lights.new(name, "AREA")
    d.energy, d.size, d.color = power, size, color
    if sy:
        d.shape, d.size_y = "RECTANGLE", sy
    o = bpy.data.objects.new(name, d)
    sc.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    return o


def render_frames(sc, folder, f0, f1):
    d = os.path.join(OUT, folder)
    os.makedirs(d, exist_ok=True)
    if arg("--test"):                                # a single frame to judge the look
        f0 = f1 = int(arg("--test"))
    sc.frame_start, sc.frame_end = f0, f1
    sc.render.filepath = os.path.join(d, "f_")
    bpy.ops.render.render(animation=True)


# ------------------------------------------------------------------ splash
def splash():
    sc = base_scene(False)
    sc.world.node_tree.nodes["Background"].inputs[0].default_value = (0.004, 0.001, 0.0015, 1)
    sc.world.node_tree.nodes["Background"].inputs[1].default_value = 1.0
    col = bpy.data.collections.new("band")
    sc.collection.children.link(col)
    root = H.build(col)
    H.orient(root, -40)
    centre, radius = A.normalise(col)            # band ~ unit sphere, resting on z = 0
    holder = bpy.data.objects["holder"]
    holder.location.x += 1.15                    # right of frame: the wordmark goes left

    # dark glossy floor: the band's reflection anchors it in space
    bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 0, 0))
    floor = bpy.context.active_object
    fm = bpy.data.materials.new("floor")
    fm.use_nodes = True
    b = fm.node_tree.nodes["Principled BSDF"]
    A.set_input(b, "Base Color", srgb("#0b0507"))
    A.set_input(b, "Roughness", 0.28)
    floor.data.materials.append(fm)

    # bokeh field: emissive specks near the lens and far behind the band
    import random
    rnd = random.Random(7)
    cols = [srgb("#ff8a8a"), srgb("#c9a3a3"), srgb("#ffd9c9"), srgb("#b3202c"), srgb("#ffffff")]
    for i in range(70):
        near = i < 22
        if near:
            loc = Vector((rnd.uniform(-2.4, 2.8), rnd.uniform(-5.0, -3.4), rnd.uniform(0.15, 2.0)))
            r = rnd.uniform(0.006, 0.014)
        else:
            loc = Vector((rnd.uniform(-9, 9), rnd.uniform(5, 14), rnd.uniform(0.3, 6)))
            r = rnd.uniform(0.03, 0.09)
        bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=loc, segments=12, ring_count=6)
        s = bpy.context.active_object
        s.data.materials.append(emissive("sp%d" % i, rnd.choice(cols), rnd.uniform(1.5, 5.0)))
    # soft strip lights far behind -> long glowing bars in the bokeh
    for k, x in enumerate((-6.5, -2.5, 3.0, 7.0)):
        bpy.ops.mesh.primitive_cube_add(size=1, location=(x, 16, 3.5 + (k % 2) * 1.2))
        bar = bpy.context.active_object
        bar.scale = (1.8, 0.05, 0.08)
        bar.data.materials.append(emissive("bar%d" % k, srgb("#ffd6c8"), 3.0))

    # key from front-left, a wine rim from behind that sweeps across, a top light
    key = area(sc, "key", (-3.0, -4.0, 3.6), (1.1, 0, 0.8), 3.0, 420, (1.0, 0.95, 0.93))
    key.visible_glossy = False                   # no white slab reflected in the floor
    rim = area(sc, "rim", (4.5, 3.0, 1.6), (1.1, 0, 0.8), 1.2, 420, (1.0, 0.35, 0.38), sy=4.0)
    rim.visible_glossy = False
    area(sc, "top", (1.1, 0.5, 5.0), (1.1, 0, 0.5), 2.0, 90).visible_glossy = False

    cam = camera(sc, (0.15, -8.0, 0.95), (0.62, 0, 0.5), 78, fstop=0.14, focus=2.6)
    n = 60
    # camera push-in, rack focus near specks -> band, band turns 30 deg, rim sweeps
    for f in range(1, n + 1):
        t = (f - 1) / (n - 1)
        ease = t * t * (3 - 2 * t)
        cam.location.y = -8.0 + 1.3 * ease
        cam.keyframe_insert("location", index=1, frame=f)
        rack = min(max((t - 0.18) / 0.42, 0), 1)
        rack = rack * rack * (3 - 2 * rack)
        target_d = (Vector((1.15, -0.4, 0.55)) - cam.location).length
        cam.data.dof.focus_distance = 2.4 + (target_d - 2.4) * rack
        cam.data.dof.keyframe_insert("focus_distance", frame=f)
        holder.rotation_euler[2] = math.radians(-18 + 30 * ease)
        holder.keyframe_insert("rotation_euler", index=2, frame=f)
        rim.location.x = 5.5 - 7.0 * ease
        rim.keyframe_insert("location", index=0, frame=f)
    led = bpy.data.materials["NB_LedGreen"].node_tree.nodes["Principled BSDF"].inputs["Emission Strength"]
    for f in range(1, n + 1):
        p = max(0.0, (f - 38) / 8.0)
        led.default_value = 1.0 + 14 * math.exp(-3 * p) * (1 if f >= 38 else 0)
        led.keyframe_insert("default_value", frame=f)
    sc.render.resolution_x, sc.render.resolution_y = 640, 340
    sc.cycles.samples = max(SAMPLES, 160)            # dark frames show noise first
    render_frames(sc, "splash", 1, n)


# ------------------------------------------------------------------ bg (Sketchfab gym, all bokeh)
def bg():
    sc = base_scene(False)
    bpy.ops.import_scene.gltf(filepath=os.path.join(SF, "training-gym", "scene.gltf"))
    bpy.context.view_layer.update()
    lo, hi = A.world_bbox(list(sc.objects))
    ctr = (lo + hi) / 2
    w = sc.world.node_tree.nodes["Background"]
    w.inputs[0].default_value = (0.9, 0.93, 1.0, 1)
    w.inputs[1].default_value = 2.5                  # daylight through the big windows
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    sun.data.energy, sun.data.angle = 4.0, math.radians(3)
    sun.rotation_euler = (math.radians(55), 0, math.radians(140))
    sc.collection.objects.link(sun)
    for k in range(4):                               # warm ceiling fixtures
        p = bpy.data.objects.new("p%d" % k, bpy.data.lights.new("p%d" % k, "POINT"))
        p.data.energy, p.data.color = 900, (1.0, 0.82, 0.62)
        p.location = (lo.x + (hi.x - lo.x) * (0.2 + 0.2 * k), ctr.y, hi.z - 1.2)
        sc.collection.objects.link(p)
    eye = Vector((lo.x + (hi.x - lo.x) * 0.85, lo.y + (hi.y - lo.y) * 0.8, lo.z + 1.5))
    tgt = Vector((ctr.x, ctr.y - 1.0, lo.z + 2.0))
    camera(sc, eye, tgt, 24, fstop=0.9, focus=0.3)
    sc.render.resolution_x, sc.render.resolution_y = 960, 340
    sc.cycles.samples = max(SAMPLES, 96)
    d = os.path.join(OUT, "bg")
    os.makedirs(d, exist_ok=True)
    sc.render.filepath = os.path.join(d, "gym.png")
    bpy.ops.render.render(write_still=True)


# ------------------------------------------------------------------ spin sprite
def spin():
    sc = base_scene(True)
    col = bpy.data.collections.new("band")
    sc.collection.children.link(col)
    root = H.build(col)
    H.orient(root, 0)
    centre, radius = A.normalise(col)
    H.studio(centre, radius, -4, 12, 70, (256, 256), dof=False)
    for o in list(bpy.data.objects):                 # no shadow catcher: sprite floats
        if o.name.startswith("catcher"):
            bpy.data.objects.remove(o)
    h = bpy.data.objects["holder"]
    n = 36
    for f in range(1, n + 2):
        h.rotation_euler[2] = TAU * (f - 1) / n
        h.keyframe_insert("rotation_euler", index=2, frame=f)
    for fc in h.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"
    render_frames(sc, "spin", 1, n)


for name, fn in (("splash", splash), ("bg", bg), ("spin", spin)):
    if not ONLY or name in ONLY:
        fn()
        print("SCREEN DONE", name)
