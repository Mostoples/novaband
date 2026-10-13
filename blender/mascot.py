# ============================================================
# Nova-Band mascot "Nova" — a plush cheetah in the team suit
# (Blender CLI, Cycles, no .blend: everything is built from code)
#
#   blender -b -P blender/mascot.py -- --shot hero                 # one shot
#   python blender/mascot.py --shot all --samples 96               # every shot, one Blender each
#   python blender/mascot.py --shot front,hero --scale 0.5 --samples 24   # quick preview
#
# Shots: hero (thumbs-up), run, front, side, back, side2 (turnaround),
#        expr-smirk, expr-wink, expr-fierce, expr-happy, armband, all
# Output: build/mascot/<shot>.png (transparent, with a shadow catcher)
#
# How it is built
#   rig     a tree of empties (root > hips > spine > neck > head, shoulders >
#           elbows > wrists, hips > knees > ankles). Every body part is a mesh
#           modelled in rest-pose world space and parented to its joint, so a
#           pose is just a set of joint rotations (forward kinematics).
#   plush   Principled sheen + micro-bump fuzz; cheetah spots are a distorted
#           Voronoi in object space, so they stick to the parts when posed.
#   trims   white suit piping, cuffs and shoe stripes are written per vertex
#           into a "trim" colour attribute as a signed distance field and
#           thresholded in the shader -> crisp edges at any subdivision.
#   face    eyes with rotating eyelids (open / stern / wink), mouth curves
#           projected onto the muzzle, tear marks, whisker dots.
#
# Axes: the mascot faces -Y, +X is its LEFT side, Z up, metres.
# ============================================================
import math
import os
import sys

SHOT_NAMES = ["hero", "run", "front", "side", "back", "side2",
              "expr-smirk", "expr-wink", "expr-fierce", "expr-happy", "armband"]

try:
    import bpy
except ImportError:
    # Plain Python: act as a driver and render every shot in its own Blender
    # process (Blender 4.0 crashes when one session builds many scenes, and
    # also when Blender spawns Blender).
    #   python blender/mascot.py --shot all --samples 96
    import subprocess
    blender = os.environ.get("BLENDER", r"C:\Program Files\Blender Foundation\Blender 4.0\blender.exe")
    argv = sys.argv[1:]
    shot = argv[argv.index("--shot") + 1] if "--shot" in argv else "all"
    rest = [a for i, a in enumerate(argv) if a != "--shot" and (i == 0 or argv[i - 1] != "--shot")]
    names = SHOT_NAMES if shot == "all" else shot.split(",")
    failed = []
    out_dir = argv[argv.index("--out") + 1] if "--out" in argv else os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "build", "mascot")
    import time
    for n in names:
        t0 = time.time()
        subprocess.run([blender, "-b", "-P", os.path.abspath(__file__), "--", "--shot", n] + rest,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        png = os.path.join(out_dir, n + ".png")
        ok = os.path.exists(png) and os.path.getmtime(png) >= t0
        print(("ok    %-12s %5.1fs" % (n, time.time() - t0)) if ok else "FAIL  " + n, flush=True)
        if not ok:
            failed.append(n)
    sys.exit(1 if failed else 0)

import bmesh
import importlib.util
from mathutils import Vector, Matrix, Euler

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(SCRIPT_DIR)
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def arg(name, default=None):
    return ARGS[ARGS.index(name) + 1] if name in ARGS else default


SHOT = arg("--shot", "hero")
SAMPLES = int(arg("--samples", 128))
SCALE = float(arg("--scale", 1.0))
OUT = arg("--out", os.path.join(PROJECT, "build", "mascot"))
os.makedirs(OUT, exist_ok=True)

spec = importlib.util.spec_from_file_location("nb_assets", os.path.join(SCRIPT_DIR, "novaband_assets.py"))
A = importlib.util.module_from_spec(spec)
spec.loader.exec_module(A)
srgb = A.srgb
si = A.set_input
rad = math.radians

FONT_DIRS = [os.path.join(PROJECT, "build", "fonts"), r"C:\Windows\Fonts"]

HEX = dict(
    fur="#5e131b",      # brand wine #7b2021, pre-darkened so the lit plush reads as the deck colour
    spot="#2a060b",     # cheetah spots
    suit="#561018",     # the jersey / pants, a touch deeper than the fur
    trim="#f2ebe6",     # white piping
    cream="#ecd3ba",    # face mask, inner ears
    ink="#17100f",
    iris="#3b2317",
    sole="#efe9e4",
    band="#151112",
    module="#7b2021",
    mouth="#3a0b10",
    tongue="#c25a63",
)

COLL = None
EMP = {}
MAT = {}


# ================================================================ materials
def node_mat(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    return m, nt, nt.nodes["Principled BSDF"]


def put(nt, sock, v):
    if isinstance(v, bpy.types.NodeSocket):
        nt.links.new(v, sock)
    else:
        sock.default_value = v


def mixc(nt, fac, c1, c2):
    n = nt.nodes.new("ShaderNodeMixRGB")
    put(nt, n.inputs["Fac"], fac)
    put(nt, n.inputs["Color1"], c1)
    put(nt, n.inputs["Color2"], c2)
    return n.outputs["Color"]


def math_node(nt, op, a, b=None, c=None):
    n = nt.nodes.new("ShaderNodeMath")
    n.operation = op
    put(nt, n.inputs[0], a)
    if b is not None:
        put(nt, n.inputs[1], b)
    if c is not None:
        put(nt, n.inputs[2], c)
    return n.outputs[0]


def map_range(nt, v, a, b, lo=0.0, hi=1.0):
    n = nt.nodes.new("ShaderNodeMapRange")
    put(nt, n.inputs["Value"], v)
    n.inputs["From Min"].default_value = a
    n.inputs["From Max"].default_value = b
    n.inputs["To Min"].default_value = lo
    n.inputs["To Max"].default_value = hi
    n.clamp = True
    return n.outputs["Result"]


def trim_mask(nt):
    """Crisp 0/1 mask from the per-vertex signed-distance attribute 'trim'."""
    a = nt.nodes.new("ShaderNodeVertexColor")
    a.layer_name = "trim"
    return map_range(nt, a.outputs["Color"], 0.47, 0.53)


def plush(name, base, spot=None, spot_scale=12.0, spot_size=0.30, trim=None,
          sheen=0.9, rough=0.88, fuzz=0.35, fuzz_scale=420.0):
    m, nt, b = node_mat(name)
    co = nt.nodes.new("ShaderNodeTexCoord").outputs["Object"]
    cur = srgb(base)
    if spot:
        # distort the coordinates a little so the spots are irregular blobs
        nz = nt.nodes.new("ShaderNodeTexNoise")
        nz.inputs["Scale"].default_value = 7.0
        nz.inputs["Detail"].default_value = 3.0
        put(nt, nz.inputs["Vector"], co)
        off = nt.nodes.new("ShaderNodeVectorMath")
        off.operation = "MULTIPLY_ADD"
        put(nt, off.inputs[0], nz.outputs["Color"])
        off.inputs[1].default_value = (0.03, 0.03, 0.03)
        put(nt, off.inputs[2], co)
        vor = nt.nodes.new("ShaderNodeTexVoronoi")
        vor.feature = "F1"
        vor.inputs["Scale"].default_value = spot_scale
        vor.inputs["Randomness"].default_value = 1.0
        nt.links.new(off.outputs[0], vor.inputs["Vector"])
        radius = math_node(nt, "MULTIPLY_ADD", vor.outputs["Color"], 0.16, spot_size - 0.06)
        diff = math_node(nt, "SUBTRACT", radius, vor.outputs["Distance"])
        cur = mixc(nt, map_range(nt, diff, -0.03, 0.03), cur, srgb(spot))
    if trim:
        cur = mixc(nt, trim_mask(nt), cur, srgb(trim))
    put(nt, b.inputs["Base Color"], cur)
    si(b, "Roughness", rough)
    si(b, ["Specular IOR Level", "Specular"], 0.25)
    si(b, ["Sheen Weight", "Sheen"], sheen)
    si(b, "Sheen Roughness", 0.4)
    try:
        b.inputs["Sheen Tint"].default_value = (1.0, 0.8, 0.8, 1.0)
    except (KeyError, TypeError, ValueError):
        pass
    # plush pile: a fine high-detail noise as bump
    fz = nt.nodes.new("ShaderNodeTexNoise")
    fz.inputs["Scale"].default_value = fuzz_scale
    fz.inputs["Detail"].default_value = 12.0
    fz.inputs["Roughness"].default_value = 0.65
    put(nt, fz.inputs["Vector"], co)
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = fuzz
    bump.inputs["Distance"].default_value = 0.004
    nt.links.new(fz.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m


def glossy(name, base, rough=0.25, coat=0.0, spec=0.5):
    m, nt, b = node_mat(name)
    si(b, "Base Color", srgb(base))
    si(b, "Roughness", rough)
    si(b, ["Specular IOR Level", "Specular"], spec)
    si(b, ["Coat Weight", "Clearcoat"], coat)
    si(b, ["Coat Roughness", "Clearcoat Roughness"], 0.05)
    return m


def emissive(name, base, strength):
    m, nt, b = node_mat(name)
    si(b, "Base Color", srgb(base))
    si(b, ["Emission Color", "Emission"], srgb(base))
    si(b, "Emission Strength", strength)
    return m


def materials():
    MAT.clear()
    MAT["fur"] = plush("M_Fur", HEX["fur"], spot=HEX["spot"], trim=HEX["trim"], spot_scale=17.0, spot_size=0.27, sheen=0.55)
    MAT["lid"] = plush("M_Lid", HEX["fur"], trim=HEX["ink"], fuzz=0.2, sheen=0.55)
    MAT["suit"] = plush("M_Suit", HEX["suit"], trim=HEX["trim"], sheen=0.3, rough=0.62, fuzz=0.12,
                        fuzz_scale=900.0)
    MAT["cream"] = plush("M_Cream", HEX["cream"], sheen=0.8, fuzz=0.3)
    MAT["ink"] = glossy("M_Ink", HEX["ink"], rough=0.3, coat=0.4)
    MAT["eye"] = glossy("M_EyeWhite", "#f7f3ef", rough=0.18, coat=0.6)
    MAT["iris"] = glossy("M_Iris", HEX["iris"], rough=0.2, coat=0.8)
    MAT["pupil"] = glossy("M_Pupil", "#050303", rough=0.15, coat=0.8)
    MAT["hilite"] = emissive("M_Hilite", "#ffffff", 3.0)
    MAT["sole"] = glossy("M_Sole", HEX["sole"], rough=0.6, spec=0.3)
    MAT["band"] = glossy("M_Band", HEX["band"], rough=0.55, spec=0.35)
    MAT["module"] = glossy("M_Module", HEX["module"], rough=0.28, coat=0.6)
    MAT["led"] = emissive("M_Led", "#fff4f2", 6.0)
    MAT["logo"] = glossy("M_Logo", HEX["trim"], rough=0.5, spec=0.3)
    MAT["mouth"] = glossy("M_Mouth", HEX["mouth"], rough=0.4)
    MAT["tongue"] = glossy("M_Tongue", HEX["tongue"], rough=0.35)


# ================================================================ geometry
def clamp01(v):
    return 0.0 if v < 0.0 else 1.0 if v > 1.0 else v


def band(d, w):
    """Signed-distance stripe value: 0.5 on the edge, >0.5 inside a stripe of half-width w."""
    return clamp01(0.5 + (w - abs(d)) / (2.0 * w))


def angdiff(a, b):
    return (a - b + math.pi) % (2 * math.pi) - math.pi


def finish(name, bm, mat, trims=None, sub=2, smooth=True, joint=None, solidify=0.0):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    if trims is not None:
        ca = me.color_attributes.new("trim", "FLOAT_COLOR", "POINT")
        for i, v in enumerate(trims):
            ca.data[i].color = (v, v, v, 1.0)
    me.materials.append(mat)
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    COLL.objects.link(ob)
    if solidify:
        md = ob.modifiers.new("solid", "SOLIDIFY")
        md.thickness = solidify
        md.offset = 1.0
    if sub:
        md = ob.modifiers.new("sub", "SUBSURF")
        md.levels = 1
        md.render_levels = sub
    if joint:
        attach(ob, joint)
    return ob


def ellip(name, c, r, mat, rot=(0, 0, 0), M=None, seg=40, rings=24, taper=0.0, cut=None,
          trim_fn=None, sub=2, joint=None, solidify=0.0):
    """Ellipsoid (unit UV sphere scaled by r). taper>0 narrows the top, <0 the bottom.
    cut: drop vertices whose unit z is below this (shells such as eyelids)."""
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=1.0)
    if cut is not None:
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z < cut - 1e-6], context="VERTS")
    if M is None:
        M = Matrix.Translation(Vector(c)) @ Euler([rad(a) for a in rot]).to_matrix().to_4x4()
    trims = [] if trim_fn else None
    for v in bm.verts:
        x, y, z = v.co
        if taper:
            k = 1.0 - abs(taper) * max(z if taper > 0 else -z, 0.0)
            x, y = x * k, y * k
        unit = Vector((x, y, z))
        v.co = M @ Vector((x * r[0], y * r[1], z * r[2]))
        if trims is not None:
            trims.append(trim_fn(unit, v.co))
    return finish(name, bm, mat, trims, sub=sub, joint=joint, solidify=solidify)


def catmull(P, n_per=8):
    P = [Vector(p) for p in P]
    ext = [P[0] * 2 - P[1]] + P + [P[-1] * 2 - P[-2]]
    out = []
    for i in range(1, len(ext) - 2):
        p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
        for k in range(n_per):
            t = k / n_per
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    out.append(P[-1])
    return out


def resample_radii(R, n_out):
    out = []
    for i in range(n_out):
        f = i / (n_out - 1) * (len(R) - 1)
        a = int(min(math.floor(f), len(R) - 2))
        t = f - a
        out.append(R[a] + (R[a + 1] - R[a]) * t)
    return out


def tube(name, pts, radii, mat, n=40, ref=(0, -1, 0), trim_fn=None, sub=2, cap=1.0,
         smooth_path=False, steps=10, joint=None):
    """Swept tube with hemispherical caps. radii: one per point (scalar).
    trim_fn(t, theta, pos): t = 0..1 along the body, theta = angle from `ref`
    around the tangent (positive towards T x ref)."""
    if smooth_path:
        P = catmull(pts, steps)
        R = resample_radii(list(radii), len(P))
    else:
        P, R = [], []
        for i in range(len(pts) - 1):
            a, b = Vector(pts[i]), Vector(pts[i + 1])
            for k in range(steps):
                t = k / steps
                P.append(a.lerp(b, t))
                R.append(radii[i] + (radii[i + 1] - radii[i]) * t)
        P.append(Vector(pts[-1]))
        R.append(radii[-1])
    N = len(P)
    T = [(P[min(i + 1, N - 1)] - P[max(i - 1, 0)]).normalized() for i in range(N)]
    refv = Vector(ref)
    nrm = refv - T[0] * refv.dot(T[0])
    if nrm.length < 1e-6:
        nrm = T[0].orthogonal()
    nrm.normalize()
    frames = []
    for i in range(N):
        if i:
            nrm = T[i - 1].rotation_difference(T[i]) @ nrm
            nrm = (nrm - T[i] * nrm.dot(T[i])).normalized()
        frames.append((T[i], nrm, T[i].cross(nrm)))
    L = [0.0]
    for i in range(1, N):
        L.append(L[-1] + (P[i] - P[i - 1]).length)
    tt = [l / L[-1] for l in L]

    rings = []          # (centre, frame index, radius, t)
    m = 6
    d0, d1 = R[0] * cap, R[-1] * cap
    for k in range(m - 1, 0, -1):
        a = k / m * math.pi / 2
        rings.append((P[0] - T[0] * d0 * math.sin(a), 0, R[0] * math.cos(a), 0.0))
    for i in range(N):
        rings.append((P[i], i, R[i], tt[i]))
    for k in range(1, m):
        a = k / m * math.pi / 2
        rings.append((P[-1] + T[-1] * d1 * math.sin(a), N - 1, R[-1] * math.cos(a), 1.0))

    bm = bmesh.new()
    trims = [] if trim_fn else None
    pole0 = bm.verts.new(P[0] - T[0] * d0)
    if trims is not None:
        trims.append(trim_fn(0.0, 0.0, pole0.co))
    ring_verts = []
    for c, fi, r, t in rings:
        Tn, Nn, Bn = frames[fi]
        row = []
        for j in range(n):
            th = 2 * math.pi * j / n
            p = c + (Nn * math.cos(th) + Bn * math.sin(th)) * r
            row.append(bm.verts.new(p))
            if trims is not None:
                trims.append(trim_fn(t, angdiff(th, 0.0), p))
        ring_verts.append(row)
    pole1 = bm.verts.new(P[-1] + T[-1] * d1)
    if trims is not None:
        trims.append(trim_fn(1.0, 0.0, pole1.co))
    for j in range(n):
        bm.faces.new((pole0, ring_verts[0][(j + 1) % n], ring_verts[0][j]))
    for a, b in zip(ring_verts[:-1], ring_verts[1:]):
        for j in range(n):
            bm.faces.new((a[j], a[(j + 1) % n], b[(j + 1) % n], b[j]))
    last = ring_verts[-1]
    for j in range(n):
        bm.faces.new((pole1, last[j], last[(j + 1) % n]))
    bm.normal_update()
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return finish(name, bm, mat, trims, sub=sub, joint=joint)


def loft_y(name, rows, mat, n=36, expo=2.6, trim_fn=None, joint=None, sub=2):
    """Shoe-like loft along -Y: rows of (y, cx, cz, rx, rz) superellipse sections in XZ."""
    bm = bmesh.new()
    trims = [] if trim_fn else None

    def add(p, nrm_hint):
        v = bm.verts.new(p)
        if trims is not None:
            trims.append(trim_fn(p, nrm_hint))
        return v

    y0, cx0, cz0, _, _ = rows[0]
    y1, cx1, cz1, _, _ = rows[-1]
    pole0 = add(Vector((cx0, y0 + 0.012, cz0)), (0, 0))
    ring_verts = []
    for y, cx, cz, rx, rz in rows:
        row = []
        for j in range(n):
            th = 2 * math.pi * j / n
            c, s = math.cos(th), math.sin(th)
            x = rx * math.copysign(abs(c) ** (2 / expo), c)
            z = rz * math.copysign(abs(s) ** (2 / expo), s)
            row.append(add(Vector((cx + x, y, cz + z)), (c, s)))
        ring_verts.append(row)
    pole1 = add(Vector((cx1, y1 - 0.012, cz1)), (0, 0))
    for j in range(n):
        bm.faces.new((pole0, ring_verts[0][j], ring_verts[0][(j + 1) % n]))
    for a, b in zip(ring_verts[:-1], ring_verts[1:]):
        for j in range(n):
            bm.faces.new((a[j], b[j], b[(j + 1) % n], a[(j + 1) % n]))
    last = ring_verts[-1]
    for j in range(n):
        bm.faces.new((pole1, last[(j + 1) % n], last[j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return finish(name, bm, mat, trims, sub=sub, joint=joint)


def ring_band(name, centre, axis, R, half_t, half_h, mat, nu=64, nv=20, joint=None):
    """A flat rubber band around `axis`: rounded-rectangle profile swept on a circle."""
    axis = Vector(axis).normalized()
    u = axis.orthogonal().normalized()
    w = axis.cross(u)
    bm = bmesh.new()
    rows = []
    for i in range(nu):
        a = 2 * math.pi * i / nu
        radial = u * math.cos(a) + w * math.sin(a)
        row = []
        for j in range(nv):
            b = 2 * math.pi * j / nv
            c, s = math.cos(b), math.sin(b)
            pr = half_t * math.copysign(abs(c) ** 0.5, c)
            pz = half_h * math.copysign(abs(s) ** 0.5, s)
            row.append(bm.verts.new(Vector(centre) + radial * (R + pr) + axis * pz))
        rows.append(row)
    for i in range(nu):
        a, b = rows[i], rows[(i + 1) % nu]
        for j in range(nv):
            bm.faces.new((a[j], b[j], b[(j + 1) % nv], a[(j + 1) % nv]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return finish(name, bm, mat, sub=1, joint=joint)


def rbox(name, M, size, mat, bevel=0.005, joint=None):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = M @ Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
    ob = finish(name, bm, mat, sub=0, smooth=True, joint=None)
    md = ob.modifiers.new("bevel", "BEVEL")
    md.width = bevel
    md.segments = 5
    md.limit_method = "NONE"
    if joint:
        attach(ob, joint)
    return ob


def curve_line(name, pts, mat, r=0.0032, joint=None):
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = r
    cu.bevel_resolution = 4
    cu.use_fill_caps = True
    sp = cu.splines.new("POLY")
    sp.points.add(len(pts) - 1)
    for p, q in zip(sp.points, pts):
        p.co = (q[0], q[1], q[2], 1.0)
    cu.materials.append(mat)
    ob = bpy.data.objects.new(name, cu)
    COLL.objects.link(ob)
    if joint:
        attach(ob, joint)
    return ob


def find_font(*names):
    for d in FONT_DIRS:
        for n in names:
            p = os.path.join(d, n)
            if os.path.exists(p):
                return bpy.data.fonts.load(p)
    return None


def text_mesh(name, body, font, size, shear=0.0, extrude=0.0015):
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = body
    if font:
        cu.font = font
    cu.size = size
    cu.shear = shear
    cu.extrude = extrude
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    cu.resolution_u = 6
    tmp = bpy.data.objects.new(name + "_tmp", cu)
    COLL.objects.link(tmp)
    bpy.context.view_layer.update()
    me = bpy.data.meshes.new_from_object(tmp.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    bpy.data.objects.remove(tmp)
    return me


# ================================================================ rig
J = {"root": (0, 0, 0), "hips": (0, 0, 0.95), "spine": (0, 0, 1.0), "neck": (0, 0, 1.40),
     "head": (0, 0, 1.50)}
PARENT = {"hips": "root", "spine": "hips", "neck": "spine", "head": "neck"}
for s, sx in (("L", 1), ("R", -1)):
    J["shoulder." + s] = (0.235 * sx, 0.0, 1.33)
    J["elbow." + s] = (0.33 * sx, 0.015, 1.07)
    J["wrist." + s] = (0.385 * sx, 0.0, 0.84)
    J["hip." + s] = (0.11 * sx, 0.0, 0.92)
    J["knee." + s] = (0.125 * sx, -0.01, 0.52)
    J["ankle." + s] = (0.13 * sx, 0.0, 0.15)
    PARENT.update({"shoulder." + s: "spine", "elbow." + s: "shoulder." + s, "wrist." + s: "elbow." + s,
                   "hip." + s: "hips", "knee." + s: "hip." + s, "ankle." + s: "knee." + s})


def build_rig():
    EMP.clear()
    for name in ["root", "hips", "spine", "neck", "head",
                 "shoulder.L", "elbow.L", "wrist.L", "shoulder.R", "elbow.R", "wrist.R",
                 "hip.L", "knee.L", "ankle.L", "hip.R", "knee.R", "ankle.R"]:
        e = bpy.data.objects.new("J_" + name, None)
        e.empty_display_size = 0.05
        COLL.objects.link(e)
        e.rotation_mode = "XYZ"
        if name in PARENT:
            e.parent = EMP[PARENT[name]]
            e.location = Vector(J[name]) - Vector(J[PARENT[name]])
        else:
            e.location = J[name]
        EMP[name] = e


HEAD_DROP = 0.055   # the head is modelled high; seat it onto the collar


def attach(ob, joint):
    ob.parent = EMP[joint]
    off = V(0, 0, -HEAD_DROP) if joint == "head" else V(0, 0, 0)
    ob.matrix_parent_inverse = Matrix.Translation(-Vector(J[joint]) + off)


V = lambda *a: Vector(a)


# ================================================================ body
def torso_rows():
    # (z, rx, ry, y-centre)
    return [(0.90, 0.190, 0.135, 0.0), (1.00, 0.200, 0.140, 0.0), (1.10, 0.214, 0.150, -0.004),
            (1.22, 0.234, 0.160, -0.010), (1.31, 0.236, 0.155, -0.006), (1.37, 0.205, 0.132, 0.0),
            (1.42, 0.130, 0.095, 0.0)]


TORSO_E = 2.4


def torso_section(z):
    rows = torso_rows()
    for a, b in zip(rows[:-1], rows[1:]):
        if a[0] <= z <= b[0]:
            t = (z - a[0]) / (b[0] - a[0])
            return [a[i] + (b[i] - a[i]) * t for i in range(4)]
    return list(rows[0] if z < rows[0][0] else rows[-1])


def torso_front(x, z):
    _, rx, ry, yc = torso_section(z)
    k = max(1.0 - abs(x / rx) ** TORSO_E, 1e-4) ** (1.0 / TORSO_E)
    return yc - ry * k


def build_torso():
    rows = torso_rows()
    n = 160
    bm = bmesh.new()
    trims = []

    def piping(p):
        x, y, z = p
        if z >= 1.15:
            xc = 0.075 + (1.40 - z) / 0.25 * 0.10
        else:
            xc = 0.175 - (1.15 - z) * 0.05
        v = band(abs(x) - xc, 0.0085) if z < 1.39 else 0.0
        # hem line just above the pants
        v = max(v, band(z - 0.935, 0.008))
        return v

    def add(p):
        trims.append(piping(p))
        return bm.verts.new(p)

    z0, z1 = rows[0][0], rows[-1][0]
    pole0 = add(V(0, rows[0][3], z0 - 0.03))
    ring_verts = []
    for z, rx, ry, yc in rows:
        sub_rows = [(z, rx, ry, yc)]
        for zz, rrx, rry, yyc in sub_rows:
            row = []
            for j in range(n):
                th = 2 * math.pi * j / n
                c, s = math.cos(th), math.sin(th)
                x = rrx * math.copysign(abs(c) ** (2 / TORSO_E), c)
                y = yyc + rry * math.copysign(abs(s) ** (2 / TORSO_E), s)
                row.append(add(V(x, y, zz)))
            ring_verts.append(row)
    pole1 = add(V(0, 0, z1 + 0.03))
    for j in range(n):
        bm.faces.new((pole0, ring_verts[0][(j + 1) % n], ring_verts[0][j]))
    for a, b in zip(ring_verts[:-1], ring_verts[1:]):
        for j in range(n):
            bm.faces.new((a[j], a[(j + 1) % n], b[(j + 1) % n], b[j]))
    for j in range(n):
        bm.faces.new((pole1, ring_verts[-1][j], ring_verts[-1][(j + 1) % n]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    # more rings so the piping stays crisp: subdivide the long edges once
    bmesh.ops.subdivide_edges(bm, edges=[e for e in bm.edges if abs(e.verts[0].co.z - e.verts[1].co.z) > 0.04],
                              cuts=6, use_grid_fill=True)
    trims = [piping(v.co) for v in bm.verts]
    finish("Torso", bm, MAT["suit"], trims, joint="spine")


def build_chest_logo():
    bold = find_font("Poppins-ExtraBold.ttf", "Poppins-Bold.ttf", "segoeuib.ttf", "arialbd.ttf")
    semi = find_font("Poppins-SemiBold.ttf", "Poppins-Bold.ttf", "segoeuib.ttf", "arialbd.ttf")
    for name, body, font, size, shear, zc in (("LogoN", "N", bold, 0.085, 0.22, 1.262),
                                              ("LogoWord", "NovaBand", semi, 0.036, 0.0, 1.192)):
        me = text_mesh(name, body, font, size, shear)
        for v in me.vertices:
            lx, ly, lz = v.co
            x, z = lx, zc + ly
            v.co = V(x, torso_front(x, z) - 0.0012 - lz, z)
        me.materials.append(MAT["logo"])
        ob = bpy.data.objects.new(name, me)
        COLL.objects.link(ob)
        attach(ob, "spine")


def build_hips():
    ellip("Pelvis", (0, 0.005, 0.93), (0.205, 0.15, 0.13), MAT["suit"], joint="hips")
    ellip("Collar", (0, 0, 1.415), (0.118, 0.106, 0.085), MAT["suit"], joint="neck",
          trim_fn=lambda u, p: band(u.z - 0.66, 0.1))


def build_arm(s):
    sx = 1 if s == "L" else -1
    S, E, W = Vector(J["shoulder." + s]), Vector(J["elbow." + s]), Vector(J["wrist." + s])
    out = (sx, 0, 0)
    # theta = 0 is the outer side, +pi/2 the front (see tube frames)
    ellip("Shoulder." + s, S + V(0.005 * sx, 0, -0.005), (0.098, 0.095, 0.095), MAT["fur"],
          joint="shoulder." + s)
    r_up = 0.078

    def up_trim(t, th, p):
        v = band(t - 0.16, 0.035)                         # raglan band near the shoulder
        v = max(v, band(th * r_up, 0.009) if t > 0.16 else 0.0)  # outer piping down the sleeve
        return v

    tube("UpperArm." + s, [S + V(0, 0, 0.03), E], [0.084, 0.072], MAT["fur"], ref=out,
         trim_fn=up_trim, joint="shoulder." + s, steps=24, n=96)
    ellip("Elbow." + s, E, (0.072, 0.072, 0.072), MAT["fur"], joint="elbow." + s)

    def fo_trim(t, th, p):
        v = band(t - 0.9, 0.045)                          # white cuff
        v = max(v, band(th * 0.066, 0.008) if t < 0.9 else 0.0)
        return v

    tube("Forearm." + s, [E, W + (W - E).normalized() * 0.01], [0.07, 0.062], MAT["fur"], ref=out,
         trim_fn=fo_trim, joint="elbow." + s, steps=24, n=96)

    # the Nova-Band itself on the LEFT upper arm
    if s == "L":
        axis = (E - S).normalized()
        P = S.lerp(E, 0.52)
        ring_band("Armband", P, axis, 0.083, 0.0075, 0.024, MAT["band"], joint="shoulder.L")
        o = (V(1, -0.8, 0) - axis * V(1, -0.8, 0).dot(axis)).normalized()
        zt = o
        yt = -axis
        xt = yt.cross(zt)
        Mrot = Matrix((xt, yt, zt)).transposed().to_4x4()
        C = P + o * 0.097
        rbox("BandModule", Matrix.Translation(C) @ Mrot, (0.04, 0.054, 0.016), MAT["module"],
             bevel=0.0055, joint="shoulder.L")
        bold = find_font("Poppins-ExtraBold.ttf", "Poppins-Bold.ttf", "segoeuib.ttf", "arialbd.ttf")
        me = text_mesh("BandN", "N", bold, 0.026, 0.2, extrude=0.0008)
        Mt = Matrix.Translation(C + o * 0.0085) @ Mrot
        me.transform(Mt)
        me.materials.append(MAT["led"])
        ob = bpy.data.objects.new("BandN", me)
        COLL.objects.link(ob)
        attach(ob, "shoulder.L")
        # status LED under the logo
        ellip("BandLed", C + o * 0.0082 + axis * 0.019, (0.0035, 0.0035, 0.0035), MAT["led"],
              joint="shoulder.L", seg=12, rings=8, sub=0)


def build_hand(s, thumb_up=False):
    sx = 1 if s == "L" else -1
    E, W = Vector(J["elbow." + s]), Vector(J["wrist." + s])
    a = (W - E).normalized()               # distal
    f = V(0, -1, 0)                         # forward
    inn = V(-sx, 0, 0)                      # towards the body
    c = W + a * 0.06
    j = "wrist." + s
    ellip("Fist." + s, c, (0.074, 0.076, 0.084), MAT["fur"], joint=j, rot=(0, -8 * sx, 0))
    # curled fingers: a roll across the front of the fist
    tube("Fingers." + s, [c + f * 0.045 + inn * 0.035 + a * 0.02, c + f * 0.05 + a * 0.025,
                          c + f * 0.045 - inn * 0.035 + a * 0.02],
         [0.03, 0.032, 0.029], MAT["fur"], joint=j, steps=6, smooth_path=True, n=24)
    if thumb_up:
        pts = [c + inn * 0.03 + f * 0.012 + a * 0.02, c + inn * 0.032 + f * 0.012 + a * 0.08,
               c + inn * 0.026 + f * 0.012 + a * 0.12]
        rr = [0.026, 0.024, 0.022]
    else:
        pts = [c + inn * 0.045 + f * 0.02, c + inn * 0.03 + f * 0.065 + a * 0.02,
               c + inn * 0.012 + f * 0.07 + a * 0.035]
        rr = [0.024, 0.022, 0.02]
    tube("Thumb." + s, pts, rr, MAT["fur"], joint=j, steps=6, smooth_path=True, n=24)


def build_leg(s):
    sx = 1 if s == "L" else -1
    H, K, A_ = Vector(J["hip." + s]), Vector(J["knee." + s]), Vector(J["ankle." + s])
    # front = theta 0 (ref -Y); for this leg's outer side theta = -pi/2 * sx
    r_th = 0.11

    def th_trim(t, th, p):
        tc = (-1.15 * (1 - t) + 0.45 * t) * sx
        return band(angdiff(th, tc) * r_th, 0.011) if 0.08 < t < 0.97 else 0.0

    tube("Thigh." + s, [H + V(0, 0, 0.05), K], [0.128, 0.11], MAT["suit"], trim_fn=th_trim,
         joint="hip." + s, steps=32, n=112)
    ellip("Knee." + s, K, (0.108, 0.108, 0.108), MAT["suit"], joint="knee." + s)

    def sh_trim(t, th, p):
        return band(angdiff(th, -math.pi / 2 * sx) * 0.093, 0.009) if t < 0.9 else 0.0

    tube("Shin." + s, [K, K.lerp(A_, 0.7), A_ + V(0, 0, 0.035)], [0.104, 0.098, 0.104], MAT["suit"],
         trim_fn=sh_trim, joint="knee." + s, steps=24, n=112, cap=0.5)

    cx = A_.x
    rows = [(0.075, cx, 0.085, 0.048, 0.05), (0.06, cx, 0.095, 0.066, 0.064), (0.02, cx, 0.1, 0.075, 0.072),
            (-0.04, cx, 0.095, 0.079, 0.068), (-0.10, cx, 0.086, 0.081, 0.058), (-0.16, cx, 0.077, 0.079, 0.048),
            (-0.21, cx, 0.069, 0.069, 0.039), (-0.236, cx, 0.066, 0.046, 0.026)]

    def shoe_trim(p, cs):
        x, y, z = p
        side = abs(cs[0])                       # 1 on the sides of the shoe
        u = (-y) * 0.75 + z * 0.66
        best = 0.0
        for k in range(2):
            best = max(best, band(u - (0.075 + k * 0.042), 0.0085))
        mask = clamp01(0.5 + (side - 0.82) * 4.0)
        reg = clamp01(0.5 + (-y + 0.005) * 25.0) if True else 1.0
        v = min(best, mask, clamp01(0.5 + (0.17 + y) * 30.0), reg)
        # white collar at the shoe opening
        v = max(v, band(z - 0.142, 0.006) if y > -0.06 else 0.0)
        return v

    shoe = loft_y("Shoe." + s, rows, MAT["suit"], trim_fn=shoe_trim, joint="ankle." + s)
    srows = [(0.085, cx, 0.03, 0.052, 0.03), (0.06, cx, 0.028, 0.074, 0.03), (-0.04, cx, 0.026, 0.085, 0.028),
             (-0.16, cx, 0.026, 0.084, 0.027), (-0.215, cx, 0.03, 0.072, 0.028), (-0.246, cx, 0.036, 0.048, 0.024)]
    sole = loft_y("Sole." + s, srows, MAT["sole"], expo=3.2, joint="ankle." + s)
    # chunky mascot sneakers: scale up about the heel-floor point
    Ms = Matrix.Translation(V(cx, 0.03, 0)) @ Matrix.Scale(1.25, 4) @ Matrix.Translation(V(-cx, -0.03, 0))
    for ob in (shoe, sole):
        ob.data.transform(Ms)


def build_tail(pose):
    if pose == "run":
        pts = [(0, 0.13, 0.9), (0.0, 0.3, 0.84), (0.02, 0.48, 0.83), (0.04, 0.64, 0.88), (0.05, 0.76, 0.99),
               (0.04, 0.8, 1.1), (0.0, 0.76, 1.16)]
    else:
        pts = [(0, 0.13, 0.9), (-0.06, 0.3, 0.79), (-0.18, 0.4, 0.75), (-0.32, 0.41, 0.81), (-0.41, 0.35, 0.94),
               (-0.41, 0.26, 1.06), (-0.34, 0.21, 1.1)]
    tube("Tail", pts, [0.05, 0.056, 0.06, 0.062, 0.062, 0.06, 0.056], MAT["fur"], smooth_path=True, steps=10,
         joint="hips", n=32)


# ================================================================ head
HEAD_C, HEAD_R = V(0, -0.005, 1.685), (0.215, 0.195, 0.2)
MASK_C, MASK_R = V(0, -0.095, 1.615), (0.175, 0.12, 0.115)
MUZ_C, MUZ_R = V(0, -0.19, 1.598), (0.085, 0.06, 0.058)


def front_y(x, z, use=("head", "mask", "muz")):
    best = None
    for key, (c, r) in (("head", (HEAD_C, HEAD_R)), ("mask", (MASK_C, MASK_R)), ("muz", (MUZ_C, MUZ_R))):
        if key not in use:
            continue
        q = 1 - ((x - c.x) / r[0]) ** 2 - ((z - c.z) / r[2]) ** 2
        if q > 0:
            y = c.y - r[1] * math.sqrt(q)
            best = y if best is None else min(best, y)
    return best if best is not None else HEAD_C.y


def on_face(x, z, off=0.0015):
    return V(x, front_y(x, z) - off, z)


def face_curve(name, xz, mat=None, r=0.0032, n_per=10):
    pts2 = catmull([V(x, 0, z) for x, z in xz], n_per)
    curve_line(name, [on_face(p.x, p.z) for p in pts2], mat or MAT["ink"], r=r, joint="head")


EXPR = {
    # name: (lid L, lid R (deg, + closes), lid slant (deg, + = stern), mouth, look (x, z))
    "smirk":  (-14, -14, 16, "smirk", (0.004, -0.002)),
    "wink":   (-26, 80, 6, "smile", (0.0, 0.0)),
    "fierce": (-4, -4, 26, "flat", (0.0, -0.003)),
    "happy":  (-40, -40, -6, "open", (0.0, 0.002)),
}


def build_eye(s, lid_deg, slant, look):
    sx = 1 if s == "L" else -1
    c = V(0.08 * sx, -0.168, 1.708)
    r = (0.05, 0.03, 0.044)
    yaw = Matrix.Rotation(rad(15 * sx), 4, "Z")
    roll_eye = Matrix.Rotation(rad(-8 * sx), 4, "Y")
    Me = Matrix.Translation(c) @ yaw @ roll_eye
    lx, lz = look
    if lid_deg <= 60:
        build_eyeball(s, sx, r, Me, lx, lz)
    # eyelid: an upper hemisphere shell rotated down over the eye
    roll = Matrix.Rotation(rad(-slant * sx), 4, "Y")
    close = Matrix.Rotation(rad(lid_deg), 4, "X")
    Ml = Matrix.Translation(c) @ yaw @ roll @ close
    if lid_deg > 60:
        # closed: a flush fur cap over the whole eye (same shape as the eyeball,
        # a hair larger) so nothing pokes forward, plus a curved lash line
        lr = (r[0] * 1.06, r[1] * 1.12, r[2] * 1.06)
        ellip("Lid." + s, None, lr, MAT["lid"], M=Me, joint="head", seg=40, rings=24)
        pts = []
        for i in range(15):
            t = -1 + 2 * i / 14
            lx_ = t * lr[0] * 0.82
            lz_ = 0.004 - 0.013 * (1 - t * t) + 0.004 * t * sx   # a soft "u", outer corner a touch higher
            q = 1 - (lx_ / lr[0]) ** 2 - (lz_ / lr[2]) ** 2
            ly_ = -lr[1] * math.sqrt(max(q, 0.0)) - 0.0012
            pts.append(Me @ V(lx_, ly_, lz_))
        curve_line("WinkLash." + s, pts, MAT["ink"], r=0.0038, joint="head")
        return
    lr = (r[0] * 1.12, r[1] * 1.22, r[2] * 1.14)
    ellip("Lid." + s, None, lr, MAT["lid"], M=Ml, cut=-0.04, joint="head", seg=40, rings=24, solidify=0.003,
          trim_fn=lambda u, p: band(u.z + 0.04, 0.13))


def build_eyeball(s, sx, r, Me, lx, lz):
    ellip("EyeWhite." + s, None, r, MAT["eye"], M=Me, joint="head", seg=32, rings=20)
    Mi = Me @ Matrix.Translation(V(lx - 0.004 * sx, -r[1] * 0.74, lz - 0.003))
    ellip("Iris." + s, None, (0.028, 0.009, 0.031), MAT["iris"], M=Mi, joint="head", seg=32, rings=16)
    Mp = Me @ Matrix.Translation(V(lx - 0.004 * sx, -r[1] * 0.86, lz - 0.003))
    ellip("Pupil." + s, None, (0.017, 0.006, 0.019), MAT["pupil"], M=Mp, joint="head", seg=24, rings=12)
    Mh = Me @ Matrix.Translation(V(lx + 0.007 * sx, -r[1] * 1.03, lz + 0.01))
    ellip("Hilite." + s, None, (0.0065, 0.003, 0.0065), MAT["hilite"], M=Mh, joint="head", seg=12, rings=8,
          sub=1)


def build_head(expr):
    lidL, lidR, slant, mouth, look = EXPR[expr]
    ellip("Head", HEAD_C, HEAD_R, MAT["fur"], joint="head", seg=64, rings=40)
    ellip("Mask", MASK_C, MASK_R, MAT["cream"], joint="head", seg=56, rings=32)
    ellip("Muzzle", MUZ_C, MUZ_R, MAT["cream"], joint="head", seg=40, rings=24)
    ellip("Nose", (0, -0.24, 1.637), (0.03, 0.017, 0.018), MAT["ink"], joint="head", taper=-0.45, seg=32,
          rings=16)
    build_eye("L", lidL, slant, look)
    build_eye("R", lidR, slant, look)
    for s, sx in (("L", 1), ("R", -1)):
        # ears
        base = V(0.145 * sx, 0.02, 1.82)
        M = (Matrix.Translation(base) @ Matrix.Rotation(rad(24 * sx), 4, "Y")
             @ Matrix.Rotation(rad(12 * sx), 4, "Z"))
        ellip("Ear." + s, None, (0.075, 0.04, 0.1), MAT["fur"], M=M @ Matrix.Translation(V(0, 0, 0.05)),
              taper=0.42, joint="head", seg=32, rings=20)
        ellip("EarIn." + s, None, (0.05, 0.02, 0.07), MAT["cream"],
              M=M @ Matrix.Translation(V(0, -0.026, 0.05)), taper=0.45, joint="head", seg=32, rings=20)
        # cheetah tear marks: inner eye corner down to the muzzle
        face_curve("Tear." + s, [(0.05 * sx, 1.67), (0.057 * sx, 1.643), (0.066 * sx, 1.618)], r=0.0042)
        for dx, dz in ((0.034, 1.603), (0.054, 1.607), (0.046, 1.587), (0.064, 1.592)):
            ellip("Dot.%s.%.3f" % (s, dx + dz), on_face(dx * sx, dz, -0.001), (0.0045, 0.003, 0.0045),
                  MAT["ink"], joint="head", seg=12, rings=8, sub=1)
    # mouth
    face_curve("Philtrum", [(0, 1.62), (0, 1.605), (0, 1.592)], r=0.003, n_per=4)
    if mouth == "smirk":
        face_curve("MouthL", [(0, 1.592), (-0.022, 1.579), (-0.045, 1.583)])
        face_curve("MouthR", [(0, 1.592), (0.026, 1.578), (0.054, 1.593)])
    elif mouth == "smile":
        face_curve("MouthL", [(0, 1.592), (-0.026, 1.577), (-0.05, 1.588)])
        face_curve("MouthR", [(0, 1.592), (0.026, 1.577), (0.05, 1.588)])
    elif mouth == "flat":
        face_curve("MouthL", [(0, 1.591), (-0.026, 1.583), (-0.048, 1.578)])
        face_curve("MouthR", [(0, 1.591), (0.026, 1.583), (0.048, 1.578)])
    else:  # open
        face_curve("MouthL", [(0, 1.593), (-0.024, 1.583), (-0.042, 1.586)])
        face_curve("MouthR", [(0, 1.593), (0.024, 1.583), (0.042, 1.586)])
        y = front_y(0, 1.566)
        ellip("MouthOpen", (0, y + 0.006, 1.566), (0.036, 0.016, 0.022), MAT["mouth"], joint="head")
        ellip("Tongue", (0, front_y(0, 1.556) + 0.004, 1.556), (0.022, 0.01, 0.01), MAT["tongue"], joint="head")


# ================================================================ poses
POSES = {
    "stand": {"shoulder.L": (0, -7, 0), "shoulder.R": (0, 7, 0), "elbow.L": (-8, 0, 0), "elbow.R": (-8, 0, 0),
              "hip.L": (0, -3, 0), "hip.R": (0, 3, 0)},
    "thumbs": {"root": (0, 0, -12), "spine": (0, 0, 4), "head": (-3, 6, 4),
               "shoulder.R": (-22, 32, 10), "elbow.R": (-122, 0, 0), "wrist.R": (0, 0, 70),
               "shoulder.L": (4, -9, 0), "elbow.L": (-18, 0, 0),
               "hip.L": (0, -6, 0), "hip.R": (-4, 7, 0), "knee.R": (6, 0, 0)},
    "run": {"root": (14, 0, 0), "spine": (0, 0, 6), "neck": (-6, 0, 0), "head": (-2, 0, -4),
            "hip.L": (-72, 0, 0), "knee.L": (95, 0, 0), "ankle.L": (-12, 0, 0),
            "hip.R": (32, 0, 0), "knee.R": (82, 0, 0), "ankle.R": (28, 0, 0),
            "shoulder.L": (48, -10, 0), "elbow.L": (-86, 0, 0),
            "shoulder.R": (-58, 10, 0), "elbow.R": (-96, 0, 0)},
}
POSE_LIFT = {"run": 0.07}


def apply_pose(pose):
    for j, (x, y, z) in POSES[pose].items():
        EMP[j].rotation_euler = (rad(x), rad(y), rad(z))
    EMP["root"].location = (0, 0, POSE_LIFT.get(pose, 0.0))
    bpy.context.view_layer.update()


# ================================================================ studio
def studio(target, half_h, az, el, lens, res, dof=None):
    sc = bpy.context.scene
    bg = sc.world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.93, 0.91, 0.92, 1)
    bg.inputs[1].default_value = 0.3
    col = bpy.data.collections.new("studio")
    sc.collection.children.link(col)
    C = V(0, 0, 1.0)
    tgt_light = bpy.data.objects.new("light_target", None)
    tgt_light.location = C
    col.objects.link(tgt_light)

    def area(name, pos, size, power, color=(1, 1, 1), shadow=True, sy=None):
        d = bpy.data.lights.new(name, "AREA")
        d.energy, d.size, d.color = power, size, color
        d.shape = "RECTANGLE"
        d.size_y = sy or size
        try:
            d.cycles.cast_shadow = shadow
        except AttributeError:
            pass
        o = bpy.data.objects.new(name, d)
        o.location = C + V(*pos) * 1.15
        col.objects.link(o)
        c = o.constraints.new("TRACK_TO")
        c.target, c.track_axis, c.up_axis = tgt_light, "TRACK_NEGATIVE_Z", "UP_Y"

    area("key", (-2.6, -3.2, 3.0), 3.2, 300, (1.0, 0.97, 0.95), sy=2.4)
    area("rim", (3.2, 2.4, 1.8), 0.8, 260, (1.0, 0.9, 0.92), shadow=False, sy=3.2)
    area("rim2", (-3.0, 2.6, 1.2), 0.8, 150, (1.0, 0.93, 0.93), shadow=False, sy=3.0)
    area("fill", (3.0, -2.8, 0.6), 3.2, 80, (0.95, 0.97, 1.0), shadow=False)
    area("top", (0.2, -0.6, 4.2), 2.8, 90, shadow=False)

    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=14)
    me = bpy.data.meshes.new("catcher")
    bm.to_mesh(me)
    bm.free()
    floor = bpy.data.objects.new("catcher", me)
    col.objects.link(floor)
    floor.is_shadow_catcher = True

    target = Vector(target)
    t_obj = bpy.data.objects.new("cam_target", None)
    t_obj.location = target
    col.objects.link(t_obj)
    cd = bpy.data.cameras.new("cam")
    cd.lens = lens
    cd.sensor_fit = "VERTICAL"
    cd.sensor_height = 24.0
    cam = bpy.data.objects.new("cam", cd)
    col.objects.link(cam)
    vfov = 2 * math.atan(12.0 / lens)
    dist = half_h / math.tan(vfov / 2)
    a, e = rad(az), rad(el)
    cam.location = target + V(math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e)) * dist
    c = cam.constraints.new("TRACK_TO")
    c.target, c.track_axis, c.up_axis = t_obj, "TRACK_NEGATIVE_Z", "UP_Y"
    if dof:
        cd.dof.use_dof = True
        cd.dof.focus_object = t_obj
        cd.dof.aperture_fstop = dof
    sc.camera = cam
    sc.render.resolution_x = int(res[0] * SCALE)
    sc.render.resolution_y = int(res[1] * SCALE)
    sc.render.resolution_percentage = 100


# ================================================================ shots
SHOTS = {
    # name: (pose, expression, target, half height, az, el, lens, res)
    "hero":        ("thumbs", "smirk", (0, 0, 0.99), 1.07, -24, 5, 70, (1200, 1500)),
    "run":         ("run", "fierce", (0.0, -0.02, 1.02), 1.08, 58, 6, 60, (1500, 1200)),
    "front":       ("stand", "smirk", (0, 0, 0.99), 1.05, 0, 3, 85, (800, 1200)),
    "side":        ("stand", "smirk", (0, 0, 0.99), 1.05, 90, 3, 85, (800, 1200)),
    "back":        ("stand", "smirk", (0, 0, 0.99), 1.05, 180, 3, 85, (800, 1200)),
    "side2":       ("stand", "smirk", (0, 0, 0.99), 1.05, 270, 3, 85, (800, 1200)),
    "expr-smirk":  ("stand", "smirk", (0, -0.05, 1.66), 0.27, -8, 3, 85, (800, 720)),
    "expr-wink":   ("stand", "wink", (0, -0.05, 1.66), 0.27, -8, 3, 85, (800, 720)),
    "expr-fierce": ("stand", "fierce", (0, -0.05, 1.66), 0.27, -8, 3, 85, (800, 720)),
    "expr-happy":  ("stand", "happy", (0, -0.05, 1.66), 0.27, -8, 3, 85, (800, 720)),
    "armband":     ("stand", "smirk", None, 0.14, 52, 8, 85, (1000, 1000)),
}


def build(pose, expr):
    global COLL
    COLL = bpy.data.collections.new("mascot")
    bpy.context.scene.collection.children.link(COLL)
    materials()
    build_rig()
    build_torso()
    build_chest_logo()
    build_hips()
    for s in ("L", "R"):
        build_arm(s)
        build_hand(s, thumb_up=(pose == "thumbs" and s == "R"))
        build_leg(s)
    build_tail(pose)
    build_head(expr)
    apply_pose(pose)


def render_shot(name):
    pose, expr, target, half_h, az, el, lens, res = SHOTS[name]
    sc = A.reset()
    build(pose, expr)
    dof = None
    if target is None:   # armband close-up: aim at the band where the pose put it
        S, E = Vector(J["shoulder.L"]), Vector(J["elbow.L"])
        P = S.lerp(E, 0.52)
        target = EMP["shoulder.L"].matrix_world @ (P - S) + V(0.03, -0.02, 0)
        dof = 2.8
    studio(target, half_h, az, el, lens, res, dof=dof)
    sc.cycles.samples = SAMPLES
    sc.cycles.use_adaptive_sampling = True
    sc.render.filepath = os.path.join(OUT, name + ".png")
    bpy.ops.render.render(write_still=True)
    print("MASCOT DONE", name, sc.render.filepath)


def main():
    # one shot per Blender session; use the plain-Python driver for several
    # (python blender/mascot.py --shot all)
    names = SHOT_NAMES if SHOT == "all" else SHOT.split(",")
    if len(names) > 1:
        print("mascot.py: several shots -> run `python blender/mascot.py --shot %s`; rendering %s only"
              % (SHOT, names[0]))
    render_shot(names[0])


if __name__ == "__main__":
    main()
