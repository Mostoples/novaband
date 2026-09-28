# ============================================================
# NovaBand — UI asset library (Blender CLI, Cycles)
#
#   blender -b -P blender/novaband_assets.py
#   blender -b -P blender/novaband_assets.py -- --only heart,chip --samples 32
#   blender -b -P blender/novaband_assets.py -- --list
#
# Every asset is modelled from primitives in this file, rendered on a
# transparent background with a shadow catcher, and written to
# build/assets3d/<name>.png. tools/pack-assets.py turns those masters
# into the web-sized WebP files under assets/3d/.
#
# Style: "clean clay" — matte white and cream bodies with the deck's
# dark red as the accent, soft studio light, a single contact shadow.
# Each asset is normalised to a unit bounding sphere before framing, so
# lights and camera are identical across the whole set and the icons
# read as one family.
# ============================================================

import bpy
import bmesh
import math
import os
import sys
import importlib.util
from mathutils import Vector, Matrix

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(SCRIPT_DIR)
OUT = os.path.join(PROJECT, "build", "assets3d")
os.makedirs(OUT, exist_ok=True)

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def arg(name, default=None):
    return ARGS[ARGS.index(name) + 1] if name in ARGS else default


ONLY = set(filter(None, (arg("--only", "") or "").split(",")))
SAMPLES = int(arg("--samples", 96))
ICON_RES = int(arg("--res", 768))

# ---------------------------------------------------------------
# Palette — taken from the ISIF deck, converted sRGB -> linear
# ---------------------------------------------------------------
def srgb(h, a=1.0):
    h = h.lstrip("#")
    c = []
    for i in (0, 2, 4):
        v = int(h[i:i + 2], 16) / 255.0
        c.append(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4)
    return (c[0], c[1], c[2], a)


P = {
    "wine":   srgb("#7b2021"),   # primary red of the deck
    "wineD":  srgb("#4b070f"),   # darkest wine
    "wineM":  srgb("#962a2c"),
    "rose":   srgb("#c9a3a3"),   # the dotted-wave decoration colour
    "cream":  srgb("#f3e3d3"),
    "white":  srgb("#f5f3f1"),
    "ink":    srgb("#1b1417"),
    "steel":  srgb("#c8c4c6"),
    "green":  srgb("#35e06b"),
    "blood":  srgb("#c81d25"),
    "gold":   srgb("#d9a25b"),
}

# ---------------------------------------------------------------
# Scene, render and colour management
# ---------------------------------------------------------------
def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for dev_type in ("OPTIX", "CUDA"):
        try:
            prefs.compute_device_type = dev_type
            prefs.get_devices()
            gpus = [d for d in prefs.devices if d.type == dev_type]
            if gpus:
                for d in prefs.devices:
                    d.use = d.type == dev_type
                sc.cycles.device = "GPU"
                break
        except Exception:
            continue
    sc.cycles.samples = SAMPLES
    sc.cycles.use_denoising = True
    try:
        sc.cycles.denoiser = "OPTIX"
    except Exception:
        sc.cycles.denoiser = "OPENIMAGEDENOISE"
    sc.cycles.max_bounces = 8
    sc.render.film_transparent = True
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    sc.render.image_settings.color_depth = "8"

    vs = sc.view_settings
    # "Standard" keeps the brand reds exact; AgX would drift them brown.
    vs.view_transform = "Standard"
    vs.look = "None"
    vs.exposure = 0.0
    vs.gamma = 1.0

    world = bpy.data.worlds.new("World")
    sc.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (1.0, 0.985, 0.98, 1.0)
    bg.inputs[1].default_value = 0.32
    return sc


def set_input(node, names, value):
    for n in ([names] if isinstance(names, str) else names):
        if n in node.inputs:
            node.inputs[n].default_value = value
            return


MATS = {}


def mat(key, color=None, rough=0.5, metal=0.0, coat=0.0, emit=None,
        strength=0.0, transmission=0.0, ior=1.45, alpha=1.0):
    """Materials are cached by key so every asset shares one look."""
    if key in MATS:
        return MATS[key]
    m = bpy.data.materials.new(key)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    set_input(b, "Base Color", color or P["white"])
    set_input(b, "Roughness", rough)
    set_input(b, "Metallic", metal)
    set_input(b, "IOR", ior)
    set_input(b, "Alpha", alpha)
    if coat:
        set_input(b, ["Coat Weight", "Clearcoat"], coat)
        set_input(b, ["Coat Roughness", "Clearcoat Roughness"], 0.08)
    if transmission:
        set_input(b, ["Transmission Weight", "Transmission"], transmission)
    if emit:
        set_input(b, ["Emission Color", "Emission"], emit)
        set_input(b, "Emission Strength", strength)
    MATS[key] = m
    return m


def M(name):
    """Named look library."""
    return {
        "wine":   lambda: mat("wine", P["wine"], rough=0.34, coat=0.55),
        "wineD":  lambda: mat("wineD", P["wineD"], rough=0.38, coat=0.4),
        "wineM":  lambda: mat("wineM", P["wineM"], rough=0.34, coat=0.5),
        "rose":   lambda: mat("rose", P["rose"], rough=0.55),
        "cream":  lambda: mat("cream", P["cream"], rough=0.52),
        "white":  lambda: mat("white", P["white"], rough=0.45, coat=0.2),
        "ink":    lambda: mat("ink", P["ink"], rough=0.18, coat=1.0),
        "steel":  lambda: mat("steel", P["steel"], rough=0.22, metal=1.0),
        "gold":   lambda: mat("gold", P["gold"], rough=0.25, metal=1.0),
        "blood":  lambda: mat("blood", P["blood"], rough=0.3, coat=0.6),
        "glass":  lambda: mat("glass", (1, 1, 1, 1), rough=0.02, transmission=1.0, ior=1.45),
        "led":    lambda: mat("led", P["green"], rough=0.2, emit=P["green"], strength=9.0),
        "ledR":   lambda: mat("ledR", P["wineM"], rough=0.2, emit=srgb("#ff4d5e"), strength=6.0),
        "screen": lambda: mat("screen", P["wineD"], rough=0.25, emit=P["wineD"], strength=0.6),
        "glowW":  lambda: mat("glowW", P["white"], rough=0.3, emit=(1, 1, 1, 1), strength=2.2),
    }[name]()


# ---------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------
def link(obj, col):
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    col.objects.link(obj)
    return obj


def smooth(obj):
    if obj.type == "MESH":
        for p in obj.data.polygons:
            p.use_smooth = True
        if hasattr(obj.data, "use_auto_smooth"):
            obj.data.use_auto_smooth = True
            obj.data.auto_smooth_angle = math.radians(40)
    return obj


def bevel(obj, width, seg=6, limit="ANGLE", angle=40):
    m = obj.modifiers.new("Bevel", "BEVEL")
    m.width = width
    m.segments = seg
    m.limit_method = limit
    if limit == "ANGLE":
        m.angle_limit = math.radians(angle)
    return obj


def subsurf(obj, lv=2):
    m = obj.modifiers.new("Sub", "SUBSURF")
    m.levels = lv
    m.render_levels = lv
    return obj


def assign(obj, material):
    if obj.data is not None and hasattr(obj.data, "materials"):
        obj.data.materials.clear()
        obj.data.materials.append(material)
    return obj


def mesh_obj(name, bm, col, material):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    return assign(ob, material)


def rbox(col, name, size, loc=(0, 0, 0), material=None, r=0.1, seg=6, rot=(0, 0, 0)):
    """Rounded box. size = full extents."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
    ob = mesh_obj(name, bm, col, material or M("white"))
    ob.location = loc
    ob.rotation_euler = rot
    if r:
        bevel(ob, min(r, min(size) * 0.49), seg, limit="NONE")
    return smooth(ob)


def cyl(col, name, radius, depth, loc=(0, 0, 0), material=None, verts=64,
        rot=(0, 0, 0), r=0.0, seg=4):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=verts,
                          radius1=radius, radius2=radius, depth=depth)
    ob = mesh_obj(name, bm, col, material or M("white"))
    ob.location = loc
    ob.rotation_euler = rot
    if r:
        bevel(ob, min(r, depth * 0.49), seg, limit="ANGLE", angle=60)
    return smooth(ob)


def cone(col, name, r1, r2, depth, loc=(0, 0, 0), material=None, rot=(0, 0, 0), verts=48):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=verts,
                          radius1=r1, radius2=r2, depth=depth)
    ob = mesh_obj(name, bm, col, material or M("white"))
    ob.location = loc
    ob.rotation_euler = rot
    return smooth(ob)


def sphere(col, name, radius, loc=(0, 0, 0), material=None, scale=(1, 1, 1)):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=48, v_segments=24, radius=radius)
    ob = mesh_obj(name, bm, col, material or M("white"))
    ob.location = loc
    ob.scale = scale
    return smooth(ob)


def torus(col, name, R, r, loc=(0, 0, 0), material=None, rot=(0, 0, 0),
          scale=(1, 1, 1), maj=96, mnr=24):
    bm = bmesh.new()
    # bmesh has no torus op: build it from a revolved circle
    verts = []
    for i in range(maj):
        a = 2 * math.pi * i / maj
        ring = []
        for j in range(mnr):
            b = 2 * math.pi * j / mnr
            x = (R + r * math.cos(b)) * math.cos(a)
            y = (R + r * math.cos(b)) * math.sin(a)
            z = r * math.sin(b)
            ring.append(bm.verts.new((x, y, z)))
        verts.append(ring)
    for i in range(maj):
        for j in range(mnr):
            a = verts[i][j]
            b = verts[(i + 1) % maj][j]
            c = verts[(i + 1) % maj][(j + 1) % mnr]
            d = verts[i][(j + 1) % mnr]
            bm.faces.new((a, b, c, d))
    ob = mesh_obj(name, bm, col, material or M("white"))
    ob.location = loc
    ob.rotation_euler = rot
    ob.scale = scale
    return smooth(ob)


def arc_tube(col, name, R, r, a0, a1, loc=(0, 0, 0), material=None, rot=(0, 0, 0),
             seg=64, mnr=16):
    """A partial torus with rounded caps — gauges, wifi arcs, rings."""
    pts = []
    for i in range(seg + 1):
        a = a0 + (a1 - a0) * i / seg
        pts.append((R * math.cos(a), R * math.sin(a), 0))
    return stroke(col, name, pts, r, loc=loc, material=material, rot=rot)


def stroke(col, name, pts, radius, loc=(0, 0, 0), material=None, rot=(0, 0, 0),
           smooth_curve=False):
    """A tube along a polyline — for symbols, needles, arrows, graph lines."""
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = radius
    cu.bevel_resolution = 6
    cu.use_fill_caps = True
    sp = cu.splines.new("NURBS" if smooth_curve else "POLY")
    sp.points.add(len(pts) - 1)
    for i, p in enumerate(pts):
        sp.points[i].co = (p[0], p[1], p[2], 1)
    if smooth_curve:
        sp.use_endpoint_u = True
        sp.order_u = 3
    ob = bpy.data.objects.new(name, cu)
    col.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = rot
    return assign(ob, material or M("wine"))


def puff(col, name, pts2d, depth, material=None, loc=(0, 0, 0), rot=(0, 0, 0),
         round_=0.45, seg=8):
    """Extrude a 2D outline and round every edge: the inflated-icon look."""
    bm = bmesh.new()
    vs = [bm.verts.new((x, y, -depth / 2)) for x, y in pts2d]
    f = bm.faces.new(vs)
    bmesh.ops.recalc_face_normals(bm, faces=[f])
    ext = bmesh.ops.extrude_face_region(bm, geom=[f])
    top = [e for e in ext["geom"] if isinstance(e, bmesh.types.BMVert)]
    for v in top:
        v.co.z += depth
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    ob = mesh_obj(name, bm, col, material or M("wine"))
    ob.location = loc
    ob.rotation_euler = rot
    # A bevel on a dense outline either clamps to nothing or folds through
    # itself. Re-meshing to voxels and relaxing the surface rounds every
    # edge by the same amount and cannot self-intersect.
    rm = ob.modifiers.new("Remesh", "REMESH")
    rm.mode = "VOXEL"
    rm.voxel_size = max(depth * 0.05, 0.0035)
    rm.use_smooth_shade = True
    ls = ob.modifiers.new("Relax", "LAPLACIANSMOOTH")
    ls.iterations = int(8 + round_ * 34)
    ls.lambda_factor = 0.9
    ls.lambda_border = 0.0
    ls.use_volume_preserve = True
    ls.use_normalized = True
    return smooth(ob)


def text(col, name, body, size, loc=(0, 0, 0), material=None, rot=(0, 0, 0),
         extrude=0.02, bevel_depth=0.004):
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = body
    cu.size = size
    cu.extrude = extrude
    cu.bevel_depth = bevel_depth
    cu.bevel_resolution = 3
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    ob = bpy.data.objects.new(name, cu)
    col.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = rot
    return assign(ob, material or M("wine"))


def lathe(col, name, profile, material=None, loc=(0, 0, 0), steps=96):
    """Revolve an (r, z) profile around Z — bells, bulbs, cups."""
    bm = bmesh.new()
    vs = [bm.verts.new((r, 0, z)) for r, z in profile]
    for a, b in zip(vs, vs[1:]):
        bm.edges.new((a, b))
    ob = mesh_obj(name, bm, col, material or M("white"))
    s = ob.modifiers.new("Screw", "SCREW")
    s.steps = steps
    s.render_steps = steps
    s.use_merge_vertices = True
    s.use_smooth_shade = True
    s.axis = "Z"
    ob.location = loc
    subsurf(ob, 1)
    return ob


def metaball(col, name, balls, material=None, res=0.02):
    mb = bpy.data.metaballs.new(name)
    mb.resolution = res
    mb.render_resolution = res
    for (x, y, z, r) in balls:
        e = mb.elements.new()
        e.co = (x, y, z)
        e.radius = r
    ob = bpy.data.objects.new(name, mb)
    col.objects.link(ob)
    return assign(ob, material or M("white"))


def arrow(col, name, direction, length, radius, material):
    """Shaft + cone head along a unit direction, from the origin."""
    d = Vector(direction).normalized()
    tip = d * length
    shaft = stroke(col, name + "_s", [(0, 0, 0), tuple(d * (length - radius * 3))],
                   radius, material=material)
    head = cone(col, name + "_h", radius * 2.6, 0.0, radius * 5.5, material=material)
    head.location = d * (length - radius * 2.6)
    head.rotation_mode = "QUATERNION"
    head.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(d)
    return [shaft, head]


# ---------------------------------------------------------------
# 2D outlines for the puffed icons
# ---------------------------------------------------------------
def heart_pts(n=96, s=0.06):
    pts = []
    for i in range(n):
        t = 2 * math.pi * i / n
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((x * s, y * s))
    return pts[::-1]


def circle_pts(r, n=64, cx=0, cy=0):
    return [(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n))
            for i in range(n)]


def teardrop_pts(n=80, w=0.62, h=1.0, sharp=1.6):
    """Map pin / flame silhouette: round bottom, pointed top (flipped for pins)."""
    pts = []
    for i in range(n):
        t = 2 * math.pi * i / n
        x = w * math.sin(t) * (math.sin(t / 2) ** sharp)
        y = -h * math.cos(t)
        pts.append((x, y))
    return pts


def shield_pts(n=40):
    """Heater shield, traced once around: right flank down, left flank up, top edge across."""
    top_y = 0.82
    right = []
    for i in range(n + 1):
        y = top_y - (top_y + 1.0) * i / n              # 0.82 -> -1.0
        x = 0.8 if y > 0.12 else 0.8 * max((y + 1.0) / 1.12, 0.0) ** 0.62
        right.append((x, y))
    left = [(-x, y) for x, y in reversed(right)][1:]   # skip the shared bottom point
    top = [(-0.8 + 1.6 * i / n, top_y - 0.06 * (1 - ((-0.8 + 1.6 * i / n) / 0.8) ** 2))
           for i in range(1, n)]                       # shallow dip toward the middle
    return right + left + top


def rounded_rect_pts(w, h, r, n=10):
    pts = []
    corners = [(w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90),
               (-w / 2 + r, -h / 2 + r, 180), (w / 2 - r, -h / 2 + r, 270)]
    for cx, cy, a0 in corners:
        for i in range(n + 1):
            a = math.radians(a0 + 90 * i / n)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


# ============================================================
# ASSETS
# Each builder receives a fresh collection and adds geometry near the
# origin; framing, grounding and scaling happen afterwards.
# ============================================================
ASSETS = {}


def asset(name, kind="icon", az=38, el=24, res=None, lens=85, shadow=True):
    def deco(fn):
        ASSETS[name] = dict(fn=fn, kind=kind, az=az, el=el, res=res, lens=lens,
                            shadow=shadow)
        return fn
    return deco


# ---------------- physiology ----------------
@asset("heart")
def a_heart(c):
    h = puff(c, "heart", heart_pts(), 0.55, M("wine"), rot=(math.radians(90), 0, 0))
    # an ECG trace riding across the front of the heart
    pts = [(-0.85, -0.29, 0.1), (-0.35, -0.29, 0.1), (-0.2, -0.29, 0.45),
           (-0.05, -0.29, -0.35), (0.12, -0.29, 0.25), (0.25, -0.29, 0.1),
           (0.85, -0.29, 0.1)]
    stroke(c, "ecg", pts, 0.035, material=M("white"))


def rbc_profile(R=0.5, n=24):
    """Biconcave red-cell cross-section (Evans-Fung shape), revolved by lathe()."""
    top = []
    for i in range(n + 1):
        r = R * i / n
        x = min(r / R, 0.999)
        h = R * math.sqrt(1 - x * x) * (0.1 + 1.0 * x * x - 0.55 * x ** 4)
        top.append((r, max(h, 0.035 if i < n else 0.0)))
    bot = [(r, -h) for r, h in reversed(top[:-1])]
    return top + bot


@asset("blood-cells")
def a_blood(c):
    for i, (loc, rot, s_) in enumerate([
            ((0, 0, 0), (62, 0, 18), 1.0), ((0.95, 0.4, 0.3), (25, -35, 0), 0.78),
            ((-0.85, 0.6, 0.38), (-15, 55, 0), 0.72)]):
        cell = lathe(c, "cell%d" % i, [(r * s_, z * s_) for r, z in rbc_profile(0.62)],
                     material=M("blood"), loc=loc)
        cell.rotation_euler = [math.radians(a) for a in rot]


@asset("led-sensor")
def a_led(c):
    rbox(c, "board", (1.3, 1.3, 0.16), material=M("wineD"), r=0.06)
    rbox(c, "pad", (0.7, 0.7, 0.08), loc=(0, 0, 0.11), material=M("ink"), r=0.03)
    dome = sphere(c, "dome", 0.24, loc=(0, 0, 0.14), material=M("led"))
    dome.scale = (1, 1, 0.8)
    for i, R in enumerate((0.45, 0.66, 0.87)):
        arc_tube(c, "wave%d" % i, R, 0.035, math.radians(35), math.radians(145),
                 loc=(0, 0, 0.35), rot=(math.radians(90), 0, 0),
                 material=M("wine") if i else M("wineM"))


@asset("photodetector")
def a_pd(c):
    rbox(c, "body", (1.1, 1.1, 0.3), material=M("white"), r=0.1)
    rbox(c, "window", (0.62, 0.62, 0.06), loc=(0, 0, 0.17), material=M("ink"), r=0.04)
    rbox(c, "cell", (0.34, 0.34, 0.03), loc=(0, 0, 0.2), material=M("wineM"), r=0.02)
    for i in range(4):
        a = math.pi / 2 * i
        rbox(c, "pin%d" % i, (0.14, 0.22, 0.06),
             loc=(0.62 * math.cos(a), 0.62 * math.sin(a), -0.08),
             rot=(0, 0, a), material=M("steel"), r=0.02)
    for i, R in enumerate((0.55, 0.78)):
        arc_tube(c, "sig%d" % i, R, 0.03, math.radians(20), math.radians(160),
                 loc=(0, 0.2, 0.38), rot=(math.radians(90), 0, 0), material=M("wine"))


@asset("chip")
def a_chip(c):
    rbox(c, "pcb", (1.7, 1.25, 0.08), material=M("wineD"), r=0.05)
    rbox(c, "can", (0.95, 0.8, 0.14), loc=(-0.2, 0, 0.1), material=M("steel"), r=0.03)
    text(c, "label", "ESP32", 0.2, loc=(-0.2, 0, 0.18), material=M("ink"),
         extrude=0.004, bevel_depth=0.0)
    # antenna meander
    pts = []
    for i in range(7):
        x = 0.42 + 0.06 * i
        pts += [(x, -0.4, 0.06), (x, 0.4, 0.06)] if i % 2 == 0 else [(x, 0.4, 0.06), (x, -0.4, 0.06)]
    stroke(c, "ant", pts, 0.012, material=M("gold"))
    for i in range(9):
        x = -0.7 + 0.13 * i
        for side in (-1, 1):
            rbox(c, "pad%d%d" % (i, side), (0.06, 0.12, 0.03),
                 loc=(x, side * 0.58, 0.05), material=M("gold"), r=0.01, seg=2)


@asset("microcontroller")
def a_mcu(c):
    rbox(c, "body", (1.2, 1.2, 0.22), material=M("ink"), r=0.05)
    circle = cyl(c, "dot", 0.07, 0.02, loc=(-0.42, -0.42, 0.12), material=M("wineM"))
    text(c, "t", "MCU", 0.26, loc=(0, 0, 0.12), material=M("white"),
         extrude=0.003, bevel_depth=0)
    for i in range(8):
        off = -0.44 + i * 0.126
        for (x, y, rz) in ((off, 0.7, 0), (off, -0.7, 0), (0.7, off, 90), (-0.7, off, 90)):
            rbox(c, "pin%d_%.2f_%.2f" % (i, x, y), (0.07, 0.24, 0.05), loc=(x, y, -0.02),
                 rot=(0, 0, math.radians(rz)), material=M("steel"), r=0.015, seg=2)


# ---------------- motion sensors ----------------
@asset("accelerometer")
def a_acc(c):
    rbox(c, "board", (1.0, 1.0, 0.16), material=M("white"), r=0.08)
    rbox(c, "ic", (0.42, 0.42, 0.1), loc=(0, 0, 0.12), material=M("ink"), r=0.03)
    for name, d, m in (("x", (1, 0, 0.0), M("wine")), ("y", (0, 1, 0.0), M("wineM")),
                       ("z", (0, 0, 1), M("wineD"))):
        for o in arrow(c, "ax_" + name, d, 1.05, 0.045, m):
            o.location = Vector(o.location) + Vector((0, 0, 0.18))
        tip = Vector(d) * 1.28 + Vector((0, 0, 0.18))
        text(c, "lbl_" + name, name.upper(), 0.24, loc=tuple(tip), material=m,
             rot=(math.radians(90), 0, math.radians(38)), extrude=0.03)


@asset("gyroscope")
def a_gyro(c):
    torus(c, "r1", 0.9, 0.05, material=M("wine"), rot=(math.radians(90), 0, 0))
    torus(c, "r2", 0.76, 0.05, material=M("wineM"), rot=(math.radians(90), 0, math.radians(90)))
    torus(c, "r3", 0.62, 0.05, material=M("wineD"), rot=(0, 0, 0))
    sphere(c, "core", 0.3, material=M("cream"))
    cyl(c, "axis", 0.03, 2.2, material=M("steel"))
    sphere(c, "cap1", 0.06, loc=(0, 0, 1.1), material=M("steel"))
    cone(c, "stand", 0.35, 0.08, 0.3, loc=(0, 0, -1.2), material=M("white"))


@asset("magnetometer")
def a_compass(c):
    cyl(c, "base", 1.0, 0.22, material=M("white"), r=0.08)
    torus(c, "rim", 1.0, 0.07, loc=(0, 0, 0.1), material=M("wine"))
    cyl(c, "face", 0.9, 0.02, loc=(0, 0, 0.12), material=M("cream"))
    for i in range(12):
        a = 2 * math.pi * i / 12
        rbox(c, "tick%d" % i, (0.04, 0.14 if i % 3 == 0 else 0.08, 0.02),
             loc=(0.76 * math.sin(a), 0.76 * math.cos(a), 0.14),
             rot=(0, 0, -a), material=M("wineD"), r=0.01, seg=2)
    n = puff(c, "needleN", [(0, 0.72), (0.12, 0), (-0.12, 0)], 0.06, M("wine"),
             loc=(0, 0, 0.19), round_=0.3)
    s = puff(c, "needleS", [(0, -0.72), (-0.12, 0), (0.12, 0)], 0.06, M("white"),
             loc=(0, 0, 0.19), round_=0.3)
    for o in (n, s):
        o.rotation_euler = (0, 0, math.radians(-35))
    cyl(c, "hub", 0.08, 0.1, loc=(0, 0, 0.22), material=M("steel"))
    cyl(c, "top", 0.1, 0.12, loc=(0, 1.02, 0.1), material=M("steel"),
        rot=(math.radians(90), 0, 0))


# ---------------- connectivity / system ----------------
@asset("smartphone", el=20, az=30)
def a_phone(c):
    rbox(c, "body", (1.0, 0.1, 2.0), material=M("ink"), r=0.13, seg=8)
    rbox(c, "screen", (0.9, 0.01, 1.88), loc=(0, -0.052, 0), material=M("screen"), r=0.1)
    # UI cards on screen
    for i, (y, w, h, m) in enumerate([
            (0.62, 0.74, 0.38, "wine"), (0.12, 0.34, 0.42, "wineM"),
            (0.12, 0.34, 0.42, "wineM"), (-0.4, 0.74, 0.4, "wine"),
            (-0.78, 0.74, 0.14, "wineM")]):
        x = 0 if i not in (1, 2) else (-0.2 if i == 1 else 0.2)
        rbox(c, "card%d" % i, (w, 0.01, h), loc=(x, -0.06, y), material=M(m), r=0.04, seg=3)
    pts = [(-0.34 + 0.68 * i / 20, -0.068, -0.44 + 0.1 * math.sin(i * 1.3) + (0.14 if i == 11 else 0))
           for i in range(21)]
    stroke(c, "hr", pts, 0.012, material=M("glowW"))
    rbox(c, "island", (0.26, 0.012, 0.06), loc=(0, -0.058, 0.88), material=M("ink"), r=0.03)


def cloud_pts(n=160):
    """Outline of a union of circles with a flat base, traced by ray-casting from the middle."""
    circles = [(-0.62, -0.02, 0.42), (0.0, 0.2, 0.56), (0.62, 0.0, 0.44),
               (-0.98, -0.16, 0.26), (0.98, -0.14, 0.27), (0.0, -0.12, 0.5)]
    base = -0.42
    pts = []
    for i in range(n):
        th = 2 * math.pi * i / n
        dx, dy = math.cos(th), math.sin(th)
        best = 0.0
        for cx, cy, r in circles:
            b = dx * cx + dy * cy
            disc = b * b - (cx * cx + cy * cy - r * r)
            if disc >= 0:
                best = max(best, b + math.sqrt(disc))
        if dy < 0:
            best = min(best, base / dy)
        pts.append((best * dx, best * dy))
    return pts


@asset("cloud")
def a_cloud(c):
    puff(c, "cloud", cloud_pts(), 0.5, mat("cloudm", P["cream"], rough=0.5),
         rot=(math.radians(90), 0, 0), round_=0.5)
    for o in arrow(c, "sync", (0, 0, 1), 0.62, 0.06, M("wine")):
        o.location = Vector(o.location) + Vector((0, -0.3, -0.28))


@asset("shield")
def a_shield(c):
    puff(c, "shield", shield_pts(), 0.4, M("wine"), rot=(math.radians(90), 0, 0))
    puff(c, "inner", [(x * 0.72, y * 0.72 + 0.03) for x, y in shield_pts()], 0.1,
         M("cream"), loc=(0, -0.2, 0), rot=(math.radians(90), 0, 0))
    stroke(c, "check", [(-0.3, -0.29, 0.02), (-0.08, -0.29, -0.2), (0.34, -0.29, 0.3)],
           0.07, material=M("wine"))


@asset("bell")
def a_bell(c):
    prof = [(0.0, 1.05), (0.12, 1.02), (0.3, 0.9), (0.48, 0.6), (0.56, 0.25),
            (0.62, 0.05), (0.82, -0.12), (0.84, -0.2), (0.0, -0.2)]
    lathe(c, "bell", prof, material=M("wine"))
    sphere(c, "clapper", 0.16, loc=(0, 0, -0.3), material=M("cream"))
    torus(c, "loop", 0.12, 0.035, loc=(0, 0, 1.12), rot=(math.radians(90), 0, 0),
          material=M("wineD"))
    sphere(c, "badge", 0.22, loc=(0.55, -0.2, 0.75), material=M("ledR"))


@asset("ai-network")
def a_ai(c):
    import random
    random.seed(4)
    nodes = [Vector((0, 0, 0))]
    for i in range(8):
        a = 2 * math.pi * i / 8
        r = 0.9 if i % 2 == 0 else 0.62
        nodes.append(Vector((r * math.cos(a), r * math.sin(a) * 0.55, 0.42 * math.sin(a * 2))))
    for n in nodes[1:]:
        stroke(c, "e", [tuple(nodes[0]), tuple(n)], 0.025, material=M("rose"))
    for i in range(1, 9):
        a, b = nodes[i], nodes[1 + (i % 8)]
        stroke(c, "r", [tuple(a), tuple(b)], 0.02, material=M("rose"))
    sphere(c, "core", 0.3, material=M("wine"))
    for i, n in enumerate(nodes[1:]):
        sphere(c, "n%d" % i, 0.13 if i % 2 else 0.17, loc=tuple(n),
               material=M("wineM") if i % 3 == 0 else M("cream"))


@asset("bluetooth")
def a_bt(c):
    rbox(c, "tile", (1.4, 0.3, 1.4), material=M("wine"), r=0.3, seg=8)
    pts = [(-0.28, -0.2, -0.3), (0.26, -0.2, 0.22), (0.0, -0.2, 0.46), (0.0, -0.2, -0.46),
           (0.26, -0.2, -0.22), (-0.28, -0.2, 0.3)]
    stroke(c, "rune", pts, 0.055, material=M("white"))


@asset("battery", az=34, el=22)
def a_batt(c):
    rbox(c, "shell", (1.8, 0.8, 0.9), material=M("white"), r=0.16, seg=8)
    rbox(c, "cap", (0.14, 0.4, 0.36), loc=(0.98, 0, 0), material=M("steel"), r=0.05)
    for i in range(4):
        rbox(c, "cell%d" % i, (0.32, 0.82, 0.64), loc=(-0.6 + 0.4 * i, 0, 0),
             material=M("wine") if i < 3 else M("rose"), r=0.06)
    puff(c, "bolt", [(0.05, 0.3), (-0.12, -0.02), (0.02, -0.02), (-0.05, -0.3),
                     (0.14, 0.04), (0.0, 0.04)], 0.06, M("cream"),
         loc=(0.2, -0.43, 0), rot=(math.radians(90), 0, 0), round_=0.3)


@asset("wifi-iot")
def a_wifi(c):
    for i, R in enumerate((0.35, 0.68, 1.0)):
        arc_tube(c, "arc%d" % i, R, 0.08, math.radians(45), math.radians(135),
                 rot=(math.radians(90), 0, 0), material=M("wine") if i != 1 else M("wineM"))
    sphere(c, "dot", 0.12, loc=(0, 0, 0.05), material=M("wineD"))
    cyl(c, "base", 0.6, 0.1, loc=(0, 0, -0.1), material=M("white"), r=0.04)


# ---------------- metrics ----------------
@asset("bar-chart", az=32, el=22)
def a_bars(c):
    rbox(c, "base", (2.1, 0.8, 0.12), material=M("white"), r=0.06)
    for i, h in enumerate((0.55, 0.95, 0.7, 1.35)):
        rbox(c, "b%d" % i, (0.34, 0.34, h), loc=(-0.72 + 0.48 * i, 0, 0.06 + h / 2),
             material=M("wine") if i == 3 else (M("rose") if i % 2 == 0 else M("wineM")),
             r=0.07)
    pts = [(-0.72 + 0.48 * i, -0.3, 0.06 + h + 0.18) for i, h in enumerate((0.55, 0.95, 0.7, 1.35))]
    stroke(c, "trend", pts, 0.03, material=M("wineD"))
    for p in pts:
        sphere(c, "pt", 0.06, loc=p, material=M("cream"))


@asset("gauge", el=30)
def a_gauge(c):
    cyl(c, "dial", 1.05, 0.2, material=M("white"), r=0.08)
    arc_tube(c, "track", 0.78, 0.07, math.radians(-30), math.radians(210),
             loc=(0, 0, 0.14), material=M("cream"))
    arc_tube(c, "value", 0.78, 0.08, math.radians(40), math.radians(210),
             loc=(0, 0, 0.16), material=M("wine"))
    needle = puff(c, "needle", [(0, 0.66), (0.06, 0), (-0.06, 0)], 0.05, M("wineD"),
                  loc=(0, 0, 0.2), round_=0.3)
    needle.rotation_euler = (0, 0, math.radians(-40))
    cyl(c, "hub", 0.11, 0.12, loc=(0, 0, 0.2), material=M("wineD"), r=0.03)


@asset("stopwatch")
def a_stopwatch(c):
    cyl(c, "body", 0.95, 0.4, rot=(math.radians(90), 0, 0), material=M("wine"), r=0.12)
    cyl(c, "face", 0.78, 0.05, loc=(0, -0.2, 0), rot=(math.radians(90), 0, 0),
        material=M("white"))
    cyl(c, "crown", 0.13, 0.22, loc=(0, 0, 1.04), material=M("wineD"), r=0.03)
    rbox(c, "btn", (0.36, 0.2, 0.14), loc=(0, 0, 1.18), material=M("steel"), r=0.05)
    rbox(c, "side", (0.18, 0.18, 0.2), loc=(0.72, 0, 0.72), rot=(0, math.radians(-45), 0),
         material=M("wineD"), r=0.04)
    arc_tube(c, "elapsed", 0.6, 0.05, math.radians(90), math.radians(-150),
             loc=(0, -0.24, 0), rot=(math.radians(90), 0, 0), material=M("rose"))
    stroke(c, "hand", [(0, -0.26, 0), (0.36, -0.26, 0.36)], 0.035, material=M("wine"))
    sphere(c, "pin", 0.07, loc=(0, -0.26, 0), material=M("wineD"))


def flame_pts(n=40):
    """Rounded base, two bezier flanks meeting at a slightly leaning tip."""
    def qb(p0, p1, p2, k):
        return [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0],
                 (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1])
                for t in (i / k for i in range(k))]
    tip = (0.1, 1.05)
    pts = qb((0.62, -0.28), (0.6, 0.45), tip, n)               # right flank, going up
    pts += qb(tip, (-0.22, 0.58), (-0.62, -0.28), n)          # left flank, going down
    for i in range(n):                                          # round base
        a = math.pi + math.pi * i / n
        pts.append((0.62 * math.cos(a), -0.28 + 0.62 * math.sin(a)))
    return pts


@asset("flame")
def a_flame(c):
    outer = flame_pts()
    puff(c, "outer", outer, 0.5, M("wine"), rot=(math.radians(90), 0, 0))
    inner = [(x * 0.5, y * 0.5 - 0.36) for x, y in outer]
    puff(c, "inner", inner, 0.2, M("cream"), loc=(0, -0.24, 0), rot=(math.radians(90), 0, 0))


def foot_pts(n=90):
    """Sole outline: narrow heel, wide ball, arch cut in on the inner side."""
    pts = []
    for i in range(n):
        t = 2 * math.pi * i / n
        y = 0.62 * math.sin(t)
        u = (y + 0.62) / 1.24                      # 0 heel .. 1 ball
        w = 0.2 + 0.13 * u - 0.02 * u * u
        x = w * math.cos(t)
        if x < 0:                                  # inner edge: the arch
            x *= 1 - 0.38 * math.exp(-((u - 0.45) / 0.18) ** 2)
        pts.append((x, y))
    return pts


@asset("footsteps", el=48)
def a_steps(c):
    def foot(ox, oy, flip, m, ang):
        a = math.radians(ang)

        def place(x, y):
            x *= flip
            return (ox + x * math.cos(a) - y * math.sin(a), oy + x * math.sin(a) + y * math.cos(a))
        puff(c, "sole", [(x * flip, y) for x, y in foot_pts()], 0.14, m,
             loc=(ox, oy, 0), rot=(0, 0, a))
        for k, (tx, ty, tr) in enumerate([(0.2, 0.78, 0.1), (0.07, 0.84, 0.075),
                                           (-0.04, 0.83, 0.066), (-0.13, 0.78, 0.058),
                                           (-0.21, 0.7, 0.05)]):
            x, y = place(tx, ty)
            puff(c, "toe%d" % k, circle_pts(tr, 32), 0.12, m, loc=(x, y, 0))
    foot(-0.36, -0.42, -1, M("wine"), 8)
    foot(0.36, 0.42, 1, M("rose"), -8)


@asset("moon")
def a_moon(c):
    moon = puff(c, "moon", circle_pts(0.9, 96), 0.4, M("wine"), rot=(math.radians(90), 0, 0))
    cutter = cyl(c, "cut", 0.78, 1.0, loc=(0.42, 0, 0.3), rot=(math.radians(90), 0, 0),
                 material=M("white"))
    b = moon.modifiers.new("cut", "BOOLEAN")
    b.object = cutter
    b.operation = "DIFFERENCE"
    b.solver = "EXACT"
    moon.modifiers.move(len(moon.modifiers) - 1, 0)
    cutter.hide_render = True
    cutter.hide_viewport = True
    for (x, z, r) in ((0.62, 0.62, 0.1), (0.9, 0.12, 0.07), (0.55, -0.35, 0.06)):
        puff(c, "star", [(r * (1 if i % 2 == 0 else 0.42) * math.cos(math.pi * i / 5 + math.pi / 2),
                           r * (1 if i % 2 == 0 else 0.42) * math.sin(math.pi * i / 5 + math.pi / 2))
                          for i in range(10)], 0.05, M("rose"), loc=(x, 0, z),
             rot=(math.radians(90), 0, 0), round_=0.35)


# ---------------- results / business ----------------
@asset("medal")
def a_medal(c):
    for s, m in ((1, M("wine")), (-1, M("wineD"))):
        rbox(c, "ribbon", (0.34, 0.06, 1.1), loc=(0.2 * s, 0.05, 0.75),
             rot=(0, math.radians(-20 * s), 0), material=m, r=0.02)
    cyl(c, "disc", 0.62, 0.16, loc=(0, 0, 0), rot=(math.radians(90), 0, 0),
        material=M("gold"), r=0.05)
    cyl(c, "inner", 0.46, 0.05, loc=(0, -0.09, 0), rot=(math.radians(90), 0, 0),
        material=M("cream"))
    text(c, "A", "A", 0.55, loc=(0, -0.12, 0), rot=(math.radians(90), 0, 0),
         material=M("wine"), extrude=0.03)


@asset("target-tiers", el=28)
def a_tiers(c):
    for i, (r, h, m) in enumerate(((1.0, 0.22, "rose"), (0.68, 0.22, "wineM"), (0.38, 0.22, "wine"))):
        cyl(c, "tier%d" % i, r, h, loc=(0, 0, 0.11 + i * 0.22), material=M(m), r=0.05)
    cyl(c, "flagpole", 0.025, 0.7, loc=(0, 0, 0.98), material=M("steel"))
    puff(c, "flag", [(0, 0), (0.36, -0.09), (0, -0.18)], 0.03, M("wineD"),
         loc=(0.0, 0, 1.3), rot=(math.radians(90), 0, 0), round_=0.3)


@asset("coins", el=26)
def a_coins(c):
    for i in range(5):
        cyl(c, "c%d" % i, 0.52, 0.14, loc=(0.03 * math.sin(i * 1.7), 0.02 * i, 0.07 + 0.145 * i),
            material=M("gold"), r=0.035)
    for i in range(3):
        cyl(c, "d%d" % i, 0.52, 0.14, loc=(1.05, 0.25, 0.07 + 0.145 * i), material=M("gold"), r=0.035)
    up = cyl(c, "up", 0.52, 0.14, loc=(0.35, -0.75, 0.52), rot=(math.radians(90), 0, math.radians(20)),
             material=M("gold"), r=0.035)
    text(c, "rp", "Rp", 0.34, loc=(0.32, -0.83, 0.52), rot=(math.radians(90), 0, math.radians(20)),
         material=M("wine"), extrude=0.02)


@asset("calendar")
def a_cal(c):
    rbox(c, "page", (1.5, 0.22, 1.5), material=M("white"), r=0.12)
    rbox(c, "head", (1.5, 0.24, 0.42), loc=(0, 0, 0.56), material=M("wine"), r=0.12)
    for x in (-0.4, 0.4):
        cyl(c, "ring", 0.06, 0.42, loc=(x, 0, 0.82), material=M("steel"), r=0.02)
    for i in range(12):
        col_, row = i % 4, i // 4
        m = M("wine") if i == 6 else (M("rose") if i in (2, 9) else M("cream"))
        rbox(c, "d%d" % i, (0.22, 0.05, 0.2), loc=(-0.48 + 0.32 * col_, -0.12, 0.18 - 0.3 * row),
             material=m, r=0.04, seg=3)


@asset("lightbulb")
def a_bulb(c):
    prof = [(0.0, 1.35), (0.3, 1.3), (0.55, 1.12), (0.66, 0.85), (0.6, 0.55),
            (0.42, 0.3), (0.34, 0.1), (0.34, 0.0)]
    lathe(c, "glass", prof, material=M("glass"))
    for i in range(3):
        cyl(c, "thread%d" % i, 0.36, 0.1, loc=(0, 0, -0.07 - 0.12 * i), material=M("wine"), r=0.03)
    cyl(c, "tip", 0.2, 0.12, loc=(0, 0, -0.43), material=M("wineD"), r=0.04)
    stroke(c, "fil", [(-0.16, 0, 0.1), (-0.12, 0, 0.62), (-0.04, 0, 0.72), (0.04, 0, 0.62),
                      (0.12, 0, 0.72), (0.16, 0, 0.1)], 0.02, material=M("glowW"))
    sphere(c, "glow", 0.22, loc=(0, 0, 0.72), material=mat("warm", srgb("#ffd9b0"),
           emit=srgb("#ffc98a"), strength=4.0))


@asset("clipboard")
def a_clip(c):
    rbox(c, "board", (1.4, 0.12, 1.85), material=M("wine"), r=0.1)
    rbox(c, "paper", (1.18, 0.04, 1.55), loc=(0, -0.07, -0.06), material=M("white"), r=0.04)
    rbox(c, "clip", (0.6, 0.18, 0.26), loc=(0, -0.06, 0.9), material=M("steel"), r=0.06)
    for i in range(4):
        y = 0.45 - 0.33 * i
        rbox(c, "box%d" % i, (0.16, 0.03, 0.16), loc=(-0.36, -0.1, y),
             material=M("cream"), r=0.03, seg=2)
        rbox(c, "line%d" % i, (0.5, 0.02, 0.06), loc=(0.14, -0.1, y),
             material=M("rose"), r=0.02, seg=2)
        if i < 3:
            stroke(c, "tick%d" % i, [(-0.43, -0.13, y), (-0.37, -0.13, y - 0.06),
                                     (-0.26, -0.13, y + 0.08)], 0.022, material=M("wine"))


@asset("magnifier")
def a_mag(c):
    torus(c, "rim", 0.62, 0.1, rot=(math.radians(90), 0, 0), material=M("wine"))
    cyl(c, "lens", 0.6, 0.06, rot=(math.radians(90), 0, 0), material=M("glass"))
    h = cyl(c, "handle", 0.11, 0.9, loc=(0.78, 0, -0.78), rot=(0, math.radians(45), 0),
            material=M("wineD"), r=0.05)
    rbox(c, "doc", (0.6, 0.04, 0.72), loc=(-0.12, 0.25, 0.08), material=M("white"), r=0.04)
    for i in range(4):
        rbox(c, "ln%d" % i, (0.4 - 0.08 * (i % 2), 0.02, 0.05), loc=(-0.14, 0.22, 0.28 - 0.15 * i),
             material=M("rose"), r=0.02, seg=2)


@asset("warning")
def a_warn(c):
    tri = [(0, 0.95), (-1.0, -0.8), (1.0, -0.8)]
    puff(c, "tri", tri, 0.36, M("wine"), rot=(math.radians(90), 0, 0), round_=0.32)
    rbox(c, "bar", (0.16, 0.1, 0.6), loc=(0, -0.2, 0.08), material=M("cream"), r=0.07)
    sphere(c, "dot", 0.1, loc=(0, -0.2, -0.45), material=M("cream"))


@asset("spring-tendon", el=18)
def a_spring(c):
    pts = []
    turns, n = 6, 300
    for i in range(n + 1):
        t = i / n
        a = 2 * math.pi * turns * t
        pts.append((0.42 * math.cos(a), 0.42 * math.sin(a), -0.9 + 1.8 * t))
    stroke(c, "coil", pts, 0.07, material=M("wine"))
    cyl(c, "capB", 0.55, 0.14, loc=(0, 0, -1.0), material=M("white"), r=0.05)
    cyl(c, "capT", 0.55, 0.14, loc=(0, 0, 1.0), material=M("white"), r=0.05)


@asset("chain-link", el=30)
def a_link(c):
    torus(c, "l1", 0.55, 0.12, loc=(-0.42, 0, 0), scale=(1.35, 0.8, 1), material=M("wine"))
    torus(c, "l2", 0.55, 0.12, loc=(0.42, 0, 0), scale=(1.35, 0.8, 1),
          rot=(math.radians(90), 0, 0), material=M("cream"))


@asset("map-pin")
def a_pin(c):
    pts = teardrop_pts(sharp=1.4)                 # point at y=-1, round end at y=+1
    puff(c, "pin", pts, 0.45, M("wine"), rot=(math.radians(90), 0, 0), loc=(0, 0, 0.2))
    cyl(c, "hole", 0.27, 0.5, loc=(0, 0, 0.42), rot=(math.radians(90), 0, 0), material=M("white"))
    cyl(c, "spot", 0.55, 0.04, loc=(0, 0, -0.88), material=M("rose"), r=0.02)


@asset("globe", el=22)
def a_globe(c):
    sphere(c, "earth", 0.9, material=M("cream"))
    for i, lat in enumerate((-50, -25, 0, 25, 50)):
        r = 0.905 * math.cos(math.radians(lat))
        torus(c, "lat%d" % i, r, 0.018, loc=(0, 0, 0.905 * math.sin(math.radians(lat))),
              material=M("rose"))
    for i in range(6):
        torus(c, "lon%d" % i, 0.905, 0.018, rot=(math.radians(90), 0, math.radians(30 * i)),
              material=M("rose"))
    torus(c, "orbit", 1.22, 0.035, rot=(math.radians(72), math.radians(18), 0), material=M("wine"))
    sphere(c, "sat", 0.1, loc=(1.16, -0.2, 0.35), material=M("wine"))
    for (x, y, z) in ((0.3, -0.8, 0.3), (-0.45, -0.72, -0.1), (0.62, -0.5, -0.35)):
        sphere(c, "event", 0.07, loc=(x, y, z), material=M("wine"))


@asset("school", az=32, el=22)
def a_school(c):
    rbox(c, "body", (2.0, 0.9, 0.95), material=M("white"), r=0.06)
    rbox(c, "wing", (0.8, 1.0, 1.45), loc=(0, 0, 0.25), material=M("cream"), r=0.06)
    puff(c, "roof", [(-0.55, 0), (0.55, 0), (0, 0.42)], 1.06, M("wine"),
         loc=(0, 0, 0.97), rot=(math.radians(90), 0, 0), round_=0.12)
    for side in (-1, 1):
        rbox(c, "roofw", (0.64, 0.98, 0.09), loc=(side * 0.72, 0, 0.52), material=M("wine"), r=0.03)
        for k in range(2):
            rbox(c, "win", (0.2, 0.04, 0.24), loc=(side * (0.55 + 0.3 * k), -0.47, 0.05),
                 material=M("wineD"), r=0.03, seg=3)
    rbox(c, "door", (0.3, 0.04, 0.44), loc=(0, -0.52, -0.25), material=M("wine"), r=0.05)
    cyl(c, "clock", 0.13, 0.04, loc=(0, -0.52, 0.55), rot=(math.radians(90), 0, 0),
        material=M("white"), r=0.01)
    cyl(c, "pole", 0.02, 0.6, loc=(0.25, 0, 1.55), material=M("steel"))
    puff(c, "flag", [(0, 0), (0.3, -0.07), (0, -0.14)], 0.03, M("wine"),
         loc=(0.25, 0, 1.82), rot=(math.radians(90), 0, 0), round_=0.3)


@asset("gear", el=30)
def a_gear(c):
    pts = []
    teeth, n = 10, 200
    for i in range(n):
        a = 2 * math.pi * i / n
        k = (a * teeth / (2 * math.pi)) % 1.0
        r = 0.95 if 0.18 < k < 0.62 else 0.74
        pts.append((r * math.cos(a), r * math.sin(a)))
    puff(c, "gear", pts, 0.34, M("wine"), round_=0.25)
    cyl(c, "hub", 0.36, 0.4, material=M("cream"), r=0.06)
    cyl(c, "axle", 0.14, 0.46, material=M("wineD"), r=0.04)


@asset("user", el=16)
def a_user(c):
    sphere(c, "head", 0.42, loc=(0, 0, 0.72), material=M("cream"))
    lathe(c, "body", [(0.0, 0.26), (0.28, 0.24), (0.55, 0.12), (0.72, -0.15),
                       (0.78, -0.5), (0.0, -0.5)], material=M("wine"))
    rbox(c, "badge", (0.34, 0.05, 0.2), loc=(0.3, -0.62, -0.14), material=M("white"), r=0.04, seg=3)


# ---------------- decorative ----------------
@asset("dots-wave", kind="deco", az=20, el=32, res=(1600, 900), lens=50, shadow=False)
def a_dots(c):
    """The deck's dotted-wave motif, as real geometry."""
    bm = bmesh.new()
    NX, NY = 120, 34
    for i in range(NX):
        for j in range(NY):
            u, v = i / (NX - 1), j / (NY - 1)
            x = (u - 0.5) * 6.4
            y = (v - 0.5) * 2.2
            z = 0.45 * math.sin(u * 7.0 + v * 2.2) * math.cos(v * 3.1) + 0.25 * math.sin(u * 13 - v * 4)
            bm.verts.new((x, y, z))
    host = mesh_obj("host", bm, c, M("rose"))
    dot = sphere(c, "dot", 0.026, material=mat("dots", srgb("#b88c8c"), rough=0.5))
    dot.parent = host
    host.instance_type = "VERTS"
    host.hide_render = False


def capsule_profile(r, length, n=16):
    pts = []
    for i in range(n + 1):                         # top hemisphere
        a = math.pi / 2 - math.pi / 2 * i / n
        pts.append((r * math.cos(a), length / 2 + r * math.sin(a)))
    for i in range(n + 1):                         # bottom hemisphere
        a = -math.pi / 2 * i / n
        pts.append((r * math.cos(a), -length / 2 + r * math.sin(a)))
    pts[0] = (0.0, pts[0][1])
    pts[-1] = (0.0, pts[-1][1])
    return pts


@asset("pills", kind="deco", az=30, el=20, res=(1200, 1200), shadow=False)
def a_pills(c):
    specs = [((-0.6, 0, 0.4), (40, 0, 20), 0.28, 0.9, "wine"),
             ((0.75, 0.3, 0.95), (-20, 30, 70), 0.22, 0.7, "cream"),
             ((0.25, -0.4, -0.55), (70, 10, -30), 0.2, 0.6, "white"),
             ((-0.95, 0.5, -0.65), (10, 60, 10), 0.16, 0.45, "rose")]
    for i, (loc, rot, r, length, m) in enumerate(specs):
        o = lathe(c, "pill%d" % i, capsule_profile(r, length), material=M(m), loc=loc)
        o.rotation_euler = [math.radians(a) for a in rot]
    sphere(c, "ball", 0.18, loc=(1.05, -0.2, -0.2), material=M("wineM"))
    torus(c, "ring", 0.45, 0.07, loc=(-0.1, 0.4, 1.3), rot=(math.radians(60), math.radians(20), 0),
          material=M("wine"))


@asset("ring-glossy", kind="deco", el=30)
def a_ring(c):
    torus(c, "ring", 0.8, 0.26, rot=(math.radians(70), 0, math.radians(20)), material=M("wine"))


# ---------------- the device itself ----------------
NB = None


def load_model():
    global NB
    if NB is None:
        spec = importlib.util.spec_from_file_location(
            "novaband_model", os.path.join(SCRIPT_DIR, "novaband_model.py"))
        NB = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(NB)
    return NB


# Exploded view: how far each shell part travels from its assembled
# position, plus the internals the shell hides (shared with the reel).
EXPLODE_LIFT = {"SensorPod": -0.014, "ModuleCase": 0.034, "OpticalWindow": 0.050,
                "LedGreenA": 0.050, "LedGreenB": 0.050, "LedIR": 0.050,
                "Photodetector": 0.050, "StatusLed": 0.034}
EXPLODE_PARTS = [
    # name,  full size (m),              xy offset,        z above TOP_Z, material, bevel
    ("PCB",   (0.030, 0.022, 0.0012), (0.0, 0.0),        0.0030, "wineD", 0.0015),
    ("ESP32", (0.012, 0.009, 0.0018), (-0.006, 0.002),   0.0045, "steel", 0.0008),
    ("IMU",   (0.004, 0.004, 0.0010), (0.009, -0.004),   0.0041, "ink",   0.0004),
    ("LiPo",  (0.026, 0.019, 0.0045), (0.0, 0.0),        0.0200,
     lambda: mat("lipo", srgb("#d9d4d6"), rough=0.35, metal=0.6), 0.0018),
]


def build_device(c, exploded=False, arm=False):
    """Rebuild the band from novaband_model.py and restyle it to the deck's wine."""
    nb = load_model()
    root, parts = nb.build_into(c) if hasattr(nb, "build_into") else _build_device_compat(nb, c)
    look = {
        "NB_Strap": (srgb("#4f1019"), 0.8, 0.0, 0.0),
        "NB_Case": (srgb("#6b1622"), 0.3, 0.2, 0.7),
        "NB_CaseDark": (srgb("#2a0a10"), 0.45, 0.1, 0.0),
        "NB_Glass": (srgb("#0d0a0c"), 0.05, 0.1, 1.0),
    }
    for m in bpy.data.materials:
        if m.name in look and m.use_nodes:
            col, rough, metal, coat = look[m.name]
            b = m.node_tree.nodes.get("Principled BSDF")
            set_input(b, "Base Color", col)
            set_input(b, "Roughness", rough)
            set_input(b, "Metallic", metal)
            set_input(b, ["Coat Weight", "Clearcoat"], coat)
            if m.name == "NB_Strap":
                # the strap is fabric: sheen, not shine
                set_input(b, ["Sheen Weight", "Sheen"], 0.6)
    if exploded:
        # Pull the module stack apart along +Z and slide in the parts the
        # outer shell hides: the PCB with the ESP32 and the Li-Po cell.
        top = nb.TOP_Z
        for o in parts:
            base = o.name.split(".")[0]
            if base in EXPLODE_LIFT:
                o.location.z += EXPLODE_LIFT[base]
            elif base in ("Strap", "StrapRib", "Keeper", "Buckle"):
                # the strap would dwarf the stack; the exploded view is about the module
                o.hide_render = True
        for name, size, xy, z, material, r in EXPLODE_PARTS:
            rbox(c, name, size, loc=(xy[0], xy[1], top + z), material=M(material) if isinstance(material, str)
                 else material(), r=r, seg=3)
    if arm:
        # a clay mannequin arm through the band: clean, anonymous, readable
        clay = mat("clay", srgb("#efe9e4"), rough=0.6)
        cyl(c, "arm", nb.BAND_R - nb.BAND_T - 0.0005, 0.24, rot=(math.radians(90), 0, 0),
            material=clay, verts=96)
        sphere(c, "shoulder", nb.BAND_R * 1.05, loc=(0, 0.12, 0), material=clay)
        sphere(c, "elbow", nb.BAND_R * 0.92, loc=(0, -0.12, 0), material=clay)
    return root


def _build_device_compat(nb, c):
    root, parts = nb.build()
    for o in list(parts) + [root]:
        link(o, c)
    return root, parts


@asset("device-hero", kind="device", az=34, el=40, res=(1600, 1600), lens=70)
def a_dev_hero(c):
    build_device(c).rotation_euler = (math.radians(72), 0, math.radians(34))


@asset("device-front", kind="device", az=0, el=62, res=(1400, 1400), lens=85)
def a_dev_front(c):
    build_device(c)


@asset("device-side", kind="device", az=90, el=8, res=(1400, 1400), lens=85)
def a_dev_side(c):
    build_device(c)


@asset("device-exploded", kind="device", az=32, el=26, res=(1400, 1600), lens=70)
def a_dev_exploded(c):
    build_device(c, exploded=True)


@asset("device-on-arm", kind="device", az=52, el=20, res=(1600, 1200), lens=70)
def a_dev_arm(c):
    build_device(c, arm=True)


# ============================================================
# Framing + rendering
# ============================================================
def world_bbox(objs):
    dg = bpy.context.evaluated_depsgraph_get()
    lo = Vector((1e9, 1e9, 1e9))
    hi = Vector((-1e9, -1e9, -1e9))
    for o in objs:
        if o.hide_render or o.type not in {"MESH", "CURVE", "FONT", "META", "SURFACE"}:
            continue
        ev = o.evaluated_get(dg)
        for corner in ev.bound_box:
            w = ev.matrix_world @ Vector(corner)
            lo = Vector((min(lo.x, w.x), min(lo.y, w.y), min(lo.z, w.z)))
            hi = Vector((max(hi.x, w.x), max(hi.y, w.y), max(hi.z, w.z)))
        if o.instance_type == "VERTS" and o.type == "MESH":
            for v in o.data.vertices:
                w = o.matrix_world @ v.co
                lo = Vector((min(lo.x, w.x), min(lo.y, w.y), min(lo.z, w.z)))
                hi = Vector((max(hi.x, w.x), max(hi.y, w.y), max(hi.z, w.z)))
    return lo, hi


def normalise(col):
    """Parent everything to one empty, scale to a unit sphere, rest it on z=0."""
    objs = [o for o in col.all_objects]
    bpy.context.view_layer.update()
    lo, hi = world_bbox(objs)
    centre = (lo + hi) / 2
    radius = max((hi - lo).length / 2, 1e-6)
    pivot = bpy.data.objects.new("pivot", None)
    col.objects.link(pivot)
    for o in objs:
        if o.parent is None:
            o.parent = pivot
    pivot.location = -centre
    bpy.context.view_layer.update()
    s = 1.0 / radius
    holder = bpy.data.objects.new("holder", None)
    col.objects.link(holder)
    pivot.parent = holder
    holder.scale = (s, s, s)
    bpy.context.view_layer.update()
    lo, hi = world_bbox(objs)
    holder.location.z -= lo.z
    bpy.context.view_layer.update()
    lo, hi = world_bbox(objs)
    return (lo + hi) / 2, max((hi - lo).length / 2, 1e-6)


def studio(centre, radius, spec):
    sc = bpy.context.scene
    col = bpy.data.collections.new("studio")
    sc.collection.children.link(col)

    target = bpy.data.objects.new("target", None)
    target.location = centre
    col.objects.link(target)

    def area(name, az, el, dist, size, power, color=(1, 1, 1), shadow=True):
        d = bpy.data.lights.new(name, "AREA")
        d.energy = power
        d.size = size
        d.color = color
        try:
            d.cycles.cast_shadow = shadow
        except AttributeError:
            pass
        o = bpy.data.objects.new(name, d)
        a, e = math.radians(az), math.radians(el)
        o.location = centre + Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e),
                                      math.sin(e))) * dist
        col.objects.link(o)
        t = o.constraints.new("TRACK_TO")
        t.target = target
        t.track_axis = "TRACK_NEGATIVE_Z"
        t.up_axis = "UP_Y"
        return o

    # key above-left, soft fill front-right, warm rim behind — same for every asset
    area("key", -30, 68, 4.5, 1.8, 240, (1.0, 0.97, 0.95))
    area("fill", 55, 20, 5.0, 4.0, 70, (0.95, 0.97, 1.0), shadow=False)
    area("rim", 160, 35, 4.5, 2.5, 150, (1.0, 0.86, 0.86), shadow=False)

    if spec["shadow"]:
        bm = bmesh.new()
        bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=12)
        me = bpy.data.meshes.new("catcher")
        bm.to_mesh(me)
        bm.free()
        floor = bpy.data.objects.new("catcher", me)
        col.objects.link(floor)
        floor.is_shadow_catcher = True

    cam_d = bpy.data.cameras.new("cam")
    cam_d.lens = spec["lens"]
    cam = bpy.data.objects.new("cam", cam_d)
    col.objects.link(cam)
    fov = 2 * math.atan(18.0 / spec["lens"])
    dist = radius / math.sin(fov / 2) * 1.02
    a, e = math.radians(spec["az"]), math.radians(spec["el"])
    cam.location = centre + Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e),
                                    math.sin(e))) * dist
    t = cam.constraints.new("TRACK_TO")
    t.target = target
    t.track_axis = "TRACK_NEGATIVE_Z"
    t.up_axis = "UP_Y"
    sc.camera = cam


def render_asset(name, spec):
    sc = reset()
    MATS.clear()
    col = bpy.data.collections.new(name)
    sc.collection.children.link(col)
    spec["fn"](col)
    centre, radius = normalise(col)
    studio(centre, radius, spec)
    res = spec["res"] or (ICON_RES, ICON_RES)
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.filepath = os.path.join(OUT, name + ".png")
    bpy.ops.render.render(write_still=True)


def main():
    if "--list" in ARGS:
        for k, v in ASSETS.items():
            print("%-18s %s" % (k, v["kind"]))
        return
    names = [n for n in ASSETS if not ONLY or n in ONLY]
    ok, failed = [], []
    for i, n in enumerate(names):
        print("\n[asset %d/%d] %s" % (i + 1, len(names), n), flush=True)
        try:
            render_asset(n, ASSETS[n])
            ok.append(n)
        except Exception as e:
            import traceback
            traceback.print_exc()
            failed.append((n, str(e)))
    print("\nASSETS DONE: %d ok, %d failed" % (len(ok), len(failed)))
    for n, e in failed:
        print("  FAILED %s: %s" % (n, e))


if __name__ == "__main__":
    main()
