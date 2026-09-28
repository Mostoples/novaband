# ============================================================
# Nova-Band — detailed product model (Blender CLI, Cycles)
#
#   blender -b -P blender/novaband_hero.py -- --shot hero
#   blender -b -P blender/novaband_hero.py -- --shot front --samples 256
#   blender -b -P blender/novaband_hero.py -- --shot spin   --frames 90
#   blender -b -P blender/novaband_hero.py -- --shot arm | exploded
#
# A product-grade rebuild of the band, modelled after the ISIF product
# images rather than approximated from primitives:
#
#   module  a rounded pill, curved to the arm, with a raised perimeter
#           frame, a groove, and a softly domed face; an inset stadium
#           window of black glass with the PPG stack (green LED, green
#           sensor, red/IR diode) and a pill-shaped status light
#   strap   a woven twill band swept along an arm-shaped path with real
#           UVs (procedural weave, sheen, stitched edges), doubled back
#           through a rectangular buckle and held by a fabric keeper
#
# Everything is built in "band space": the arm runs along Y, the strap
# loop lies in XZ, the module sits on top (+Z) with its long axis on X.
# Units are metres, true scale.
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
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def arg(name, default=None):
    return ARGS[ARGS.index(name) + 1] if name in ARGS else default


SHOT = arg("--shot", "hero")
SAMPLES = int(arg("--samples", 160))
FRAMES = int(arg("--frames", 90))
FRAME_CAP = int(arg("--frame-cap", 0))
RES = int(arg("--res", 1400))
OUT = arg("--out", os.path.join(PROJECT, "build", "hero"))
os.makedirs(OUT, exist_ok=True)
TAU = 2 * math.pi

spec = importlib.util.spec_from_file_location("nb_assets", os.path.join(SCRIPT_DIR, "novaband_assets.py"))
A = importlib.util.module_from_spec(spec)
spec.loader.exec_module(A)
srgb = A.srgb

# ---------------------------------------------------------------- dimensions
# The module is modelled with its long axis on X and then turned 90 deg, so on
# the band its long axis runs ACROSS the strap (along the arm), as in the photos.
MOD_HL, MOD_HW, MOD_R = 0.0360, 0.0205, 0.0125     # module half-length, half-width, corner radius
BEND_R = 0.060                                       # radius the module is curved to (across its width)
STRAP_HW, STRAP_HT = 0.0440, 0.00140                 # a wide arm band: wider than the module is long
TOP_Z = 0.038                                        # strap centre-line height under the module

# ================================================================ materials
def node_mat(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    return m, nt, b


def plastic(name, hexcol, rough=0.32, coat=0.55, coat_rough=0.12):
    m, nt, b = node_mat(name)
    A.set_input(b, "Base Color", srgb(hexcol))
    A.set_input(b, "Roughness", rough)
    A.set_input(b, ["Coat Weight", "Clearcoat"], coat)
    A.set_input(b, ["Coat Roughness", "Clearcoat Roughness"], coat_rough)
    A.set_input(b, ["Specular IOR Level", "Specular"], 0.5)
    # a whisper of large-scale noise so broad surfaces are not CG-perfect
    tex = nt.nodes.new("ShaderNodeTexNoise")
    tex.inputs["Scale"].default_value = 180.0
    tex.inputs["Detail"].default_value = 3.0
    ramp = nt.nodes.new("ShaderNodeMapRange")
    ramp.inputs["To Min"].default_value = rough - 0.04
    ramp.inputs["To Max"].default_value = rough + 0.05
    nt.links.new(tex.outputs["Fac"], ramp.inputs["Value"])
    nt.links.new(ramp.outputs["Result"], b.inputs["Roughness"])
    return m


def glass_black():
    m, nt, b = node_mat("NB_Glass")
    A.set_input(b, "Base Color", srgb("#020102"))
    A.set_input(b, "Roughness", 0.05)
    A.set_input(b, ["Coat Weight", "Clearcoat"], 0.6)
    A.set_input(b, ["Coat Roughness", "Clearcoat Roughness"], 0.02)
    A.set_input(b, ["Specular IOR Level", "Specular"], 0.35)
    return m


def emissive(name, col, strength, base=None):
    m, nt, b = node_mat(name)
    A.set_input(b, "Base Color", base or col)
    A.set_input(b, "Roughness", 0.2)
    A.set_input(b, ["Emission Color", "Emission"], col)
    A.set_input(b, "Emission Strength", strength)
    return m


def fabric(name, dark, light, period=0.00085, bump=0.45):
    """
    Woven twill from the strap's own UVs (u = metres along the strap,
    v = metres across it): diagonal ribs + a finer cross rib + fibre noise,
    driving colour, roughness and a bump; sheen gives the soft textile rim.
    """
    m, nt, b = node_mat(name)
    N, L = nt.nodes, nt.links
    uv = N.new("ShaderNodeTexCoord")
    sep = N.new("ShaderNodeSeparateXYZ")
    L.new(uv.outputs["UV"], sep.inputs["Vector"])
    k = 1.0 / period

    def lin(a, fa, bb, fb):
        n = N.new("ShaderNodeMath"); n.operation = "MULTIPLY_ADD"
        n2 = N.new("ShaderNodeMath"); n2.operation = "MULTIPLY"
        L.new(bb, n2.inputs[0]); n2.inputs[1].default_value = fb
        L.new(a, n.inputs[0]); n.inputs[1].default_value = fa
        L.new(n2.outputs[0], n.inputs[2])
        return n.outputs[0]

    diag = lin(sep.outputs["X"], k, sep.outputs["Y"], k)          # twill direction
    cross = lin(sep.outputs["X"], k * 1.9, sep.outputs["Y"], 0.0)  # fine cross rib

    def wave(inp, distortion):
        comb = N.new("ShaderNodeCombineXYZ")
        L.new(inp, comb.inputs["X"])
        w = N.new("ShaderNodeTexWave")
        w.wave_type = "BANDS"
        w.bands_direction = "X"
        w.inputs["Scale"].default_value = TAU / 20.0     # Blender bands: sin(20*scale*x) -> period 1
        w.inputs["Distortion"].default_value = distortion
        w.inputs["Detail"].default_value = 1.5
        L.new(comb.outputs["Vector"], w.inputs["Vector"])
        return w.outputs["Fac"]

    w1, w2 = wave(diag, 1.2), wave(cross, 0.6)
    noise = N.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 900.0
    noise.inputs["Detail"].default_value = 8.0
    L.new(uv.outputs["Object"], noise.inputs["Vector"])
    mix1 = N.new("ShaderNodeMath"); mix1.operation = "MULTIPLY_ADD"
    L.new(w1, mix1.inputs[0]); mix1.inputs[1].default_value = 0.62
    mul2 = N.new("ShaderNodeMath"); mul2.operation = "MULTIPLY"
    L.new(w2, mul2.inputs[0]); mul2.inputs[1].default_value = 0.23
    L.new(mul2.outputs[0], mix1.inputs[2])
    mix2 = N.new("ShaderNodeMath"); mix2.operation = "MULTIPLY_ADD"
    L.new(noise.outputs["Fac"], mix2.inputs[0]); mix2.inputs[1].default_value = 0.3
    L.new(mix1.outputs[0], mix2.inputs[2])
    h = mix2.outputs[0]

    ramp = N.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.25
    ramp.color_ramp.elements[0].color = srgb(dark)
    ramp.color_ramp.elements[1].position = 0.95
    ramp.color_ramp.elements[1].color = srgb(light)
    L.new(h, ramp.inputs["Fac"])
    L.new(ramp.outputs["Color"], b.inputs["Base Color"])
    bmp = N.new("ShaderNodeBump")
    bmp.inputs["Strength"].default_value = bump
    bmp.inputs["Distance"].default_value = 0.00022
    L.new(h, bmp.inputs["Height"])
    L.new(bmp.outputs["Normal"], b.inputs["Normal"])
    A.set_input(b, "Roughness", 0.88)
    A.set_input(b, ["Sheen Weight", "Sheen"], 0.35)
    A.set_input(b, ["Sheen Roughness"], 0.45)
    A.set_input(b, ["Sheen Tint"], srgb("#d98c9a") if "Sheen Tint" in b.inputs and
                b.inputs["Sheen Tint"].type == "RGBA" else 0.5)
    A.set_input(b, ["Specular IOR Level", "Specular"], 0.25)
    return m


MAT = {}


def mats():
    MAT.update(
        body=plastic("NB_Body", "#3f0b15", rough=0.36, coat=0.45),
        frame=plastic("NB_Frame", "#440c18", rough=0.3, coat=0.5, coat_rough=0.1),
        face=plastic("NB_Face", "#4a0e19", rough=0.4, coat=0.45, coat_rough=0.16),
        bezel=plastic("NB_Bezel", "#140b0e", rough=0.3, coat=0.3),
        glass=glass_black(),
        led=emissive("NB_LedGreen", (0.05, 1.0, 0.12, 1), 2.4, base=srgb("#0b3a14")),
        ledsq=emissive("NB_LedSq", (0.12, 1.0, 0.04, 1), 1.4, base=srgb("#12400c")),
        ir=emissive("NB_LedIR", (1.0, 0.12, 0.1, 1), 2.2, base=srgb("#3a0a0a")),
        lens=plastic("NB_Lens", "#171013", rough=0.25, coat=0.4, coat_rough=0.08),
        status=emissive("NB_Status", (0.9, 0.9, 0.95, 1), 0.12, base=srgb("#b9b4ba")),
        strap=fabric("NB_Strap", "#170306", "#471020", period=0.0011, bump=0.7),
        keeper=fabric("NB_Keeper", "#170306", "#380a13", period=0.0007, bump=0.6),
        stitch=plastic("NB_Stitch", "#5c1622", rough=0.75, coat=0.0),
        buckle=plastic("NB_Buckle", "#3d0a14", rough=0.28, coat=0.8, coat_rough=0.1),
    )
    b = MAT["buckle"].node_tree.nodes["Principled BSDF"]
    A.set_input(b, "Metallic", 0.55)


# ================================================================ geometry kit
def new_obj(name, bm, col, mat, smooth=True):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
        if hasattr(me, "use_auto_smooth"):
            me.use_auto_smooth = True
            me.auto_smooth_angle = math.radians(42)
    o = bpy.data.objects.new(name, me)
    col.objects.link(o)
    me.materials.append(mat)
    return o


# -- rounded rectangle outlines with a FIXED point layout, so offsets correspond
SEG = dict(sx=26, sy=12, arc=18)


def rrect(hl, hw, r, cx=0.0, cy=0.0):
    pts = []
    corners = [(hl - r, hw - r, 0), (-(hl - r), hw - r, 90), (-(hl - r), -(hw - r), 180), ((hl - r), -(hw - r), 270)]
    straights = [((hl - r, hw), (-(hl - r), hw), SEG["sx"]), ((-hl, hw - r), (-hl, -(hw - r)), SEG["sy"]),
                 ((-(hl - r), -hw), (hl - r, -hw), SEG["sx"]), ((hl, -(hw - r)), (hl, hw - r), SEG["sy"])]
    for k in range(4):
        cxk, cyk, a0 = corners[k]
        for i in range(SEG["arc"]):
            a = math.radians(a0 + 90 * i / SEG["arc"])
            pts.append((cx + cxk + r * math.cos(a), cy + cyk + r * math.sin(a)))
        (x0, y0), (x1, y1), n = straights[k]
        for i in range(n):
            t = i / n
            pts.append((cx + x0 + (x1 - x0) * t, cy + y0 + (y1 - y0) * t))
    return pts


def outline(inset):
    return rrect(MOD_HL - inset, MOD_HW - inset, max(MOD_R - inset, 0.0005))


def sweep_outline(bm, profile, z_of=None):
    """Profile = [(inset, z)] swept around the module outline -> list of rings."""
    rings = []
    for inset, z in profile:
        ring = [bm.verts.new((x, y, z)) for x, y in outline(inset)]
        rings.append(ring)
    for r0, r1 in zip(rings, rings[1:]):
        n = len(r0)
        for i in range(n):
            bm.faces.new((r0[i], r0[(i + 1) % n], r1[(i + 1) % n], r1[i]))
    return rings


def cap(bm, ring, zfun, rings=14, down=False):
    """Fill a ring with concentric scaled rings to a centre vertex (so it bends cleanly)."""
    pts = [v.co.copy() for v in ring]
    cx = sum(p.x for p in pts) / len(pts)
    cy = sum(p.y for p in pts) / len(pts)
    prev = ring
    for k in range(1, rings):
        s = 1 - k / rings
        cur = [bm.verts.new((cx + (p.x - cx) * s, cy + (p.y - cy) * s, zfun(s))) for p in pts]
        n = len(cur)
        for i in range(n):
            f = (prev[i], prev[(i + 1) % n], cur[(i + 1) % n], cur[i])
            bm.faces.new(f[::-1] if down else f)
        prev = cur
    c = bm.verts.new((cx, cy, zfun(0.0)))
    n = len(prev)
    for i in range(n):
        f = (prev[i], prev[(i + 1) % n], c)
        bm.faces.new(f[::-1] if down else f)


FACE_EDGE_Z, DOME = 0.0091, 0.0013


def dome_z(x, y):
    """Height of the domed face at (x, y): a superellipse-norm pillow."""
    hl, hw = MOD_HL - 0.0036, MOD_HW - 0.0036
    s = min(((abs(x) / hl) ** 4 + (abs(y) / hw) ** 4) ** 0.25, 1.0)
    return FACE_EDGE_Z + DOME * (1 - s * s) ** 0.85


def bend(obj):
    """Wrap a flat module part (X along its length) onto the arm curvature."""
    for v in obj.data.vertices:
        y, x, z = v.co              # module X (long axis) -> band Y (across the strap)
        x = -x
        th = x / BEND_R
        rr = BEND_R + z
        v.co = Vector((rr * math.sin(th), y, rr * math.cos(th) - BEND_R))
    obj.data.update()


# ================================================================ module
def build_module(col):
    parts = []

    # (a) lower body: rounded bottom edge, straight wall
    bm = bmesh.new()
    prof = [(0.0024, 0.0), (0.0013, 0.00035), (0.0005, 0.0011), (0.0001, 0.0021), (0.0, 0.0035), (0.0, 0.0074)]
    rings = sweep_outline(bm, prof)
    cap(bm, rings[0], lambda s: 0.0, down=True)
    cap(bm, rings[-1], lambda s: 0.0074)
    parts.append(new_obj("ModuleBody", bm, col, MAT["body"]))

    # (b) perimeter frame: outer wall, rounded crown, inner wall into the groove
    bm = bmesh.new()
    prof = [(0.0, 0.0072), (0.0, 0.0083), (0.00018, 0.00885), (0.0006, 0.00912), (0.0011, 0.0092),
            (0.00155, 0.0090), (0.0018, 0.0086), (0.0019, 0.0078), (0.0019, 0.0074)]
    sweep_outline(bm, prof)
    parts.append(new_obj("ModuleFrame", bm, col, MAT["frame"]))

    # (c) domed face, sitting inside the frame with a visible groove
    bm = bmesh.new()
    prof = [(0.0025, 0.0074), (0.0025, 0.0083), (0.0027, 0.0087), (0.0031, 0.00898), (0.0036, FACE_EDGE_Z)]
    rings = sweep_outline(bm, prof)
    top = rings[-1]
    for v in top:
        v.co.z = dome_z(v.co.x, v.co.y)
    pts = [v.co.copy() for v in top]
    prev = top
    for k in range(1, 18):
        s = 1 - k / 18
        cur = []
        for p in pts:
            x, y = p.x * s, p.y * s
            cur.append(bm.verts.new((x, y, dome_z(x, y))))
        n = len(cur)
        for i in range(n):
            bm.faces.new((prev[i], prev[(i + 1) % n], cur[(i + 1) % n], cur[i]))
        prev = cur
    c = bm.verts.new((0, 0, dome_z(0, 0)))
    for i in range(len(prev)):
        bm.faces.new((prev[i], prev[(i + 1) % len(prev)], c))
    parts.append(new_obj("ModuleFace", bm, col, MAT["face"]))

    # (d) window: bezel ring + black glass, following the dome
    WX, WHL, WHW, WR = 0.0045, 0.0150, 0.0102, 0.0094

    def win_ring(bm, hl, hw, r, dz):
        ring = []
        for x, y in rrect(hl, hw, r, cx=WX):
            ring.append(bm.verts.new((x, y, dome_z(x, y) + dz)))
        return ring

    bm = bmesh.new()
    rs = [win_ring(bm, WHL + 0.0009, WHW + 0.0009, WR + 0.0009, -0.0002),
          win_ring(bm, WHL + 0.0008, WHW + 0.0008, WR + 0.0008, 0.00025),
          win_ring(bm, WHL + 0.0003, WHW + 0.0003, WR + 0.0003, 0.00042),
          win_ring(bm, WHL, WHW, WR, 0.0003)]
    for r0, r1 in zip(rs, rs[1:]):
        n = len(r0)
        for i in range(n):
            bm.faces.new((r0[i], r0[(i + 1) % n], r1[(i + 1) % n], r1[i]))
    parts.append(new_obj("WindowBezel", bm, col, MAT["bezel"]))

    bm = bmesh.new()
    rim = win_ring(bm, WHL, WHW, WR, 0.0003)
    edge = win_ring(bm, WHL - 0.0005, WHW - 0.0005, WR - 0.0005, 0.00062)
    n = len(rim)
    for i in range(n):
        bm.faces.new((rim[i], rim[(i + 1) % n], edge[(i + 1) % n], edge[i]))
    base_z = lambda x, y: dome_z(x, y) + 0.00068
    pts = [v.co.copy() for v in edge]
    prev = edge
    for k in range(1, 10):
        s = 1 - k / 10
        cur = []
        for p in pts:
            x, y = WX + (p.x - WX) * s, p.y * s
            cur.append(bm.verts.new((x, y, base_z(x, y) + 0.0001 * (1 - s))))
        for i in range(n):
            bm.faces.new((prev[i], prev[(i + 1) % n], cur[(i + 1) % n], cur[i]))
        prev = cur
    cc = bm.verts.new((WX, 0, base_z(WX, 0) + 0.0001))
    for i in range(n):
        bm.faces.new((prev[i], prev[(i + 1) % n], cc))
    parts.append(new_obj("WindowGlass", bm, col, MAT["glass"]))

    # (e) the PPG stack under the glass, from the far end: LED, sensor, IR
    def disc(name, x, r, mat, square=False, lift=0.00073):
        bm = bmesh.new()
        z0 = dome_z(x, 0) + lift
        if square:
            ring = [bm.verts.new((px, py, z0)) for px, py in rrect(r, r, r * 0.35, cx=x)]
        else:
            ring = [bm.verts.new((x + r * math.cos(TAU * i / 32), r * math.sin(TAU * i / 32), z0)) for i in range(32)]
        c = bm.verts.new((x, 0, z0 + 0.00004))
        for i in range(len(ring)):
            bm.faces.new((ring[i], ring[(i + 1) % len(ring)], c))
        parts.append(new_obj(name, bm, col, mat))

    for name, x, r in (("LensA", WX + 0.0080, 0.0021), ("LensB", WX + 0.0012, 0.0025), ("LensC", WX - 0.0056, 0.0021)):
        disc(name, x, r, MAT["lens"], lift=0.00084)
    disc("LedGreenA", WX + 0.0080, 0.0011, MAT["led"], lift=0.00087)
    disc("LedGreenB", WX + 0.0012, 0.0015, MAT["ledsq"], square=True, lift=0.00087)
    disc("LedIR", WX - 0.0056, 0.0010, MAT["ir"], lift=0.00087)

    # (f) status light: a small frosted pill near the near end
    bm = bmesh.new()
    SX = -(MOD_HL - 0.0078)
    ring = [bm.verts.new((x, y, dome_z(x, y) + 0.00005)) for x, y in rrect(0.0014, 0.0034, 0.00135, cx=SX)]
    ring2 = [bm.verts.new((x, y, dome_z(x, y) + 0.0003)) for x, y in rrect(0.0012, 0.0032, 0.00115, cx=SX)]
    n = len(ring)
    for i in range(n):
        bm.faces.new((ring[i], ring[(i + 1) % n], ring2[(i + 1) % n], ring2[i]))
    c = bm.verts.new((SX, 0, dome_z(SX, 0) + 0.00036))
    for i in range(n):
        bm.faces.new((ring2[i], ring2[(i + 1) % n], c))
    # the status pill runs across the module (along Y)
    parts.append(new_obj("StatusLed", bm, col, MAT["status"]))

    for p in parts:
        bend(p)
        p.location.z = TOP_Z + STRAP_HT
    return parts


# ================================================================ strap
def catmull(pts, n_per=60):
    out = []
    m = len(pts)
    for i in range(m):
        p0, p1, p2, p3 = (Vector(pts[(i + k - 1) % m]) for k in range(4))
        for j in range(n_per):
            t = j / n_per
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 +
                              (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    return out


def resample(pts, n):
    L = [0.0]
    for a, b in zip(pts, pts[1:] + pts[:1]):
        L.append(L[-1] + (b - a).length)
    total = L[-1]
    out, j = [], 0
    for i in range(n):
        s = total * i / n
        while L[j + 1] < s:
            j += 1
        a, b = pts[j], pts[(j + 1) % len(pts)]
        t = (s - L[j]) / max(L[j + 1] - L[j], 1e-12)
        out.append(a.lerp(b, t))
    return out, total


def strap_path():
    """Arm-shaped loop in XZ: a shallow arc under the module, rounder below."""
    top = [(x, TOP_Z - BEND_R + math.sqrt(BEND_R ** 2 - x * x)) for x in (0.024, 0.012, 0.0, -0.012, -0.024)]
    right = [(0.0475, 0.0), (0.0415, TOP_Z - 0.016)]
    bottom = [(-0.0475, 0.0), (-0.042, -0.0215), (-0.025, -0.036), (0.0, -0.040), (0.025, -0.036), (0.042, -0.0215)]
    ctrl = [right[0], right[1]] + top + [(-0.0415, TOP_Z - 0.016)] + bottom
    pts = [Vector((x, 0.0, z)) for x, z in ctrl]
    dense = catmull(pts, 80)
    path, total = resample(dense, 720)
    return path, total


def frames_of(path, closed=True):
    n = len(path)
    fr = []
    for i in range(n):
        a = path[(i - 1) % n] if closed or i > 0 else path[i]
        b = path[(i + 1) % n] if closed or i < n - 1 else path[i]
        t = (b - a).normalized()
        nout = Vector((t.z, 0.0, -t.x))
        fr.append((path[i], t, nout))
    return fr


def band_profile(hw, ht, r, n=44):
    """Rounded-rectangle cross-section in (outward, across) coordinates, closed."""
    pts = []
    for k, (cx, cy, a0) in enumerate([(ht - r, hw - r, 0), (-(ht - r), hw - r, 90),
                                      (-(ht - r), -(hw - r), 180), (ht - r, -(hw - r), 270)]):
        for i in range(n // 4):
            a = math.radians(a0 + 90 * i / (n // 4 - 1))
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def sweep(name, fr, profile, col, mat, closed=True, offset=0.0, caps=False, uv_s0=0.0):
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    rings, s_acc, s = [], [], uv_s0
    for i, (p, t, nout) in enumerate(fr):
        if i:
            s += (fr[i][0] - fr[i - 1][0]).length
        s_acc.append(s)
        ring = [bm.verts.new(p + nout * (pn + offset) + Vector((0, py, 0))) for pn, py in profile]
        rings.append(ring)
    # across-coordinate for v: profile arc length
    vv = [0.0]
    for a, b in zip(profile, profile[1:] + profile[:1]):
        vv.append(vv[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    m = len(profile)
    pairs = list(zip(range(len(rings)), list(range(1, len(rings))) + ([0] if closed else [])))
    for i0, i1 in pairs[: len(rings) if closed else len(rings) - 1]:
        r0, r1 = rings[i0], rings[i1]
        u0, u1 = s_acc[i0], s_acc[i1] if i1 else s_acc[i0] + (fr[i0][0] - fr[i1][0]).length
        for j in range(m):
            f = bm.faces.new((r0[j], r0[(j + 1) % m], r1[(j + 1) % m], r1[j]))
            for loop, (u, v) in zip(f.loops, ((u0, vv[j]), (u0, vv[j + 1]), (u1, vv[j + 1]), (u1, vv[j]))):
                loop[uvl].uv = (u, v)
    if caps and not closed:
        for ring, rev in ((rings[0], True), (rings[-1], False)):
            c = bm.verts.new(sum((v.co for v in ring), Vector()) / len(ring))
            for j in range(m):
                f = (ring[j], ring[(j + 1) % m], c)
                bm.faces.new(f[::-1] if rev else f)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return new_obj(name, bm, col, mat)


def stitches(name, fr, col, lines, step=0.0021, length=0.0012, rad=0.00026, closed=True):
    """Stitch dashes along the band: tiny ellipsoids, one mesh."""
    bm = bmesh.new()
    s, nxt = 0.0, 0.0
    for i in range(len(fr) - (0 if closed else 1)):
        p, t, nout = fr[i]
        q = fr[(i + 1) % len(fr)][0]
        seg = (q - p).length
        while nxt <= s + seg:
            f = (nxt - s) / max(seg, 1e-9)
            c0 = p.lerp(q, f)
            for pn, py in lines:
                ctr = c0 + nout * pn + Vector((0, py, 0))
                mat = Matrix((t * (length / 2), Vector((0, rad, 0)), nout * rad * 0.8)).transposed()
                geom = bmesh.ops.create_uvsphere(bm, u_segments=8, v_segments=5, radius=1.0)
                for v in geom["verts"]:
                    v.co = ctr + mat @ v.co
            nxt += step
        s += seg
    return new_obj(name, bm, col, MAT["stitch"])


def build_strap(col):
    parts = []
    path, total = strap_path()
    fr = frames_of(path)
    prof = band_profile(STRAP_HW, STRAP_HT, STRAP_HT * 0.92)
    parts.append(sweep("Strap", fr, prof, col, MAT["strap"]))
    ln = STRAP_HW - 0.0017
    parts.append(stitches("StrapStitch", fr, col,
                          [(STRAP_HT + 0.00008, ln), (STRAP_HT + 0.00008, -ln),
                           (-STRAP_HT - 0.00008, ln), (-STRAP_HT - 0.00008, -ln)]))

    # the adjusting end: on the side of the loop, next to the module, the strap
    # runs through a rectangular buckle, doubles back over itself and is held
    # down by a wide stitched fabric keeper (as in the product photos)
    n = len(fr)
    span = lambda a, b: [fr[i % n] for i in range(int(n * a), int(n * b))]
    i1 = int(n * 0.005)                            # buckle, on the far edge of the keeper
    flap = span(0.005, 0.150)
    off = 2 * STRAP_HT + 0.0002
    fprof = band_profile(STRAP_HW - 0.0004, STRAP_HT, STRAP_HT * 0.92)
    parts.append(sweep("Flap", flap, fprof, col, MAT["strap"], closed=False, offset=off, caps=True))
    parts.append(stitches("FlapStitch", flap, col, [(off + STRAP_HT + 0.00008, ln - 0.0003),
                                                   (off + STRAP_HT + 0.00008, -ln + 0.0003)], closed=False))

    # buckle: a rounded-rectangle ring around both layers, in the band's cross-section plane
    p, t, nout = fr[i1]
    ring_path = []
    bw, bt = STRAP_HW + 0.0026, 2 * STRAP_HT + 0.0026
    for x, y in rrect(bt, bw, 0.0022):
        ring_path.append(p + nout * (x + STRAP_HT) + Vector((0, y, 0)))
    rfr = []
    m = len(ring_path)
    for i in range(m):
        tt = (ring_path[(i + 1) % m] - ring_path[i - 1]).normalized()
        side = t.cross(tt).normalized()
        rfr.append((ring_path[i], tt, side))
    bm = bmesh.new()
    rings = []
    for q, tt, side in rfr:
        up = t
        rings.append([bm.verts.new(q + side * 0.0013 * math.cos(TAU * k / 16) + up * 0.0017 * math.sin(TAU * k / 16))
                      for k in range(16)])
    for a, b in zip(rings, rings[1:] + rings[:1]):
        for k in range(16):
            bm.faces.new((a[k], a[(k + 1) % 16], b[(k + 1) % 16], b[k]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    parts.append(new_obj("Buckle", bm, col, MAT["buckle"]))

    # keeper: a wide padded sleeve wrapping strap + flap, stitched all round
    kt = (off + 2 * STRAP_HT + 0.0016) / 2
    kprof = band_profile(STRAP_HW + 0.0010, kt, 0.0012)
    kfr = [(q + nout * (off / 2), tt, nout) for q, tt, nout in span(0.030, 0.125)]
    parts.append(sweep("Keeper", kfr, kprof, col, MAT["keeper"], closed=False, caps=True))
    kin = STRAP_HW - 0.0012
    parts.append(stitches("KeeperStitch", kfr[3:-3], col, [(kt + 0.0001, kin), (kt + 0.0001, -kin)],
                          step=0.0019, closed=False))
    # stitched cross seams at both ends of the keeper
    for e in (kfr[4], kfr[-5]):
        p, t, nout = e
        seam = [(p + Vector((0, y, 0)), Vector((0, 1, 0)), nout) for y in
                [(-kin + 2 * kin * i / 120) for i in range(121)]]
        parts.append(stitches("KeeperSeam", seam, col, [(kt + 0.0001, 0.0)], step=0.0019, closed=False))
    return parts


# ================================================================ scene
def build(col, arm=False, exploded=False):
    mats()
    root = bpy.data.objects.new("NovaBand", None)
    col.objects.link(root)
    mod = build_module(col)
    strap = build_strap(col)
    for o in mod + strap:
        o.parent = root
    if exploded:
        W = 0.058                      # window + sensor stack on top
        lift = {"ModuleFrame": 0.033, "ModuleFace": 0.042, "StatusLed": 0.042, "WindowBezel": W,
                "WindowGlass": W, "LensA": W, "LensB": W, "LensC": W, "LedGreenA": W, "LedGreenB": W, "LedIR": W}
        for o in mod:
            o.location.z += lift.get(o.name.split(".")[0], 0.0)
        for o in strap:
            o.hide_render = True
        inner = [("PCB", (0.034, 0.062, 0.0012), 0.0075 + 0.0060, "#2c5d3a"),
                 ("LiPo", (0.027, 0.048, 0.0040), 0.0075 + 0.0180, "#cfc9cc")]
        for name, size, z, hexcol in inner:
            ob = A.rbox(col, name, size, loc=(0, 0, TOP_Z + STRAP_HT + z), r=0.0012,
                        material=plastic("NB_" + name, hexcol, rough=0.35, coat=0.3))
            ob.parent = root
        chip = A.rbox(col, "ESP32", (0.012, 0.016, 0.0020), loc=(0.005, -0.012, TOP_Z + STRAP_HT + 0.0075 + 0.0076),
                      r=0.0006, material=plastic("NB_Chip", "#c9c4c7", rough=0.25, coat=0.2))
        chip.parent = root
    if arm:
        clay = A.mat("clay", srgb("#cdbfba"), rough=0.75)
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=96, radius1=0.92, radius2=1.06, depth=0.24)
        o = new_obj("Arm", bm, col, clay)
        o.rotation_euler = (math.radians(90), 0, 0)
        o.scale = (0.0458, 0.0378, 1.0)          # oval to fill the loop
        o.location = (0, 0, -0.0012)
        o.parent = root
    return root


def orient(root, yaw):
    """Band space -> world: arm upright, module facing the camera, then a yaw."""
    # band X -> world X, band Y (arm axis) -> world Z, band Z (module normal) -> world -Y
    M = Matrix(((1, 0, 0), (0, 0, -1), (0, 1, 0))).to_4x4()
    root.matrix_world = Matrix.Rotation(math.radians(yaw), 4, "Z") @ M


def studio(centre, radius, az, el, lens, res, dof=True):
    sc = bpy.context.scene
    world = sc.world
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.92, 0.9, 0.91, 1)
    bg.inputs[1].default_value = 0.35
    col = bpy.data.collections.new("studio")
    sc.collection.children.link(col)
    target = bpy.data.objects.new("target", None)
    target.location = centre
    col.objects.link(target)

    def area(name, pos, size, power, color=(1, 1, 1), shadow=True, shape="RECTANGLE", sy=None):
        d = bpy.data.lights.new(name, "AREA")
        d.energy, d.size, d.color = power, size, color
        d.shape = shape
        if sy:
            d.size_y = sy
        try:
            d.cycles.cast_shadow = shadow
        except AttributeError:
            pass
        o = bpy.data.objects.new(name, d)
        o.location = centre + Vector(pos) * radius
        col.objects.link(o)
        c = o.constraints.new("TRACK_TO")
        c.target, c.track_axis, c.up_axis = target, "TRACK_NEGATIVE_Z", "UP_Y"
        return o

    # big soft key (front-left-top), strip rim (back-right), low fill, top reflector
    area("key", (-2.6, -3.2, 3.0), 3.0, 330, (1.0, 0.97, 0.95), shape="RECTANGLE", sy=2.2)
    area("rim", (3.2, 2.2, 1.6), 0.6, 260, (1.0, 0.88, 0.9), shadow=False, shape="RECTANGLE", sy=3.0)
    area("fill", (3.0, -2.6, 0.4), 3.0, 70, (0.95, 0.97, 1.0), shadow=False)
    area("top", (0.2, -0.6, 4.2), 2.5, 120, (1, 1, 1), shadow=False)

    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=12 * radius)
    me = bpy.data.meshes.new("catcher")
    bm.to_mesh(me)
    bm.free()
    floor = bpy.data.objects.new("catcher", me)
    col.objects.link(floor)
    floor.is_shadow_catcher = True

    cam_d = bpy.data.cameras.new("cam")
    cam_d.lens = lens
    cam = bpy.data.objects.new("cam", cam_d)
    col.objects.link(cam)
    fov = 2 * math.atan(18.0 / lens)
    dist = radius / math.sin(fov / 2) * 1.02
    a, e = math.radians(az), math.radians(el)
    cam.location = centre + Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e))) * dist
    c = cam.constraints.new("TRACK_TO")
    c.target, c.track_axis, c.up_axis = target, "TRACK_NEGATIVE_Z", "UP_Y"
    if dof:
        cam_d.dof.use_dof = True
        cam_d.dof.focus_object = target
        cam_d.dof.aperture_fstop = 5.6 * radius       # scene is normalised: keep a gentle falloff
    sc.camera = cam
    sc.render.resolution_x, sc.render.resolution_y = res


def setup_render(samples):
    sc = bpy.context.scene
    sc.cycles.samples = samples
    sc.cycles.use_adaptive_sampling = True
    sc.render.use_persistent_data = True
    # Standard (set by reset) keeps the brand wine exact; AgX drifts it brown
    vs = sc.view_settings
    vs.exposure = -0.1


SHOTS = {
    # name: (yaw, cam az, cam el, lens, res, kind)
    "hero":     (-32, -6, 12, 85, (RES, RES)),
    "front":    (-24, 0, 8, 85, (RES, RES)),
    "back":     (200, -8, 14, 85, (RES, RES)),
    "spin":     (0, -6, 16, 70, (720, 720)),
    "arm":      (40, -6, 16, 60, (1600, 1200)),
    "exploded": (0, 24, 30, 70, (1400, 1600)),
}


def main():
    sc = A.reset()
    A.MATS.clear()
    col = bpy.data.collections.new("band")
    sc.collection.children.link(col)
    yaw, az, el, lens, res = SHOTS[SHOT]
    root = build(col, arm=SHOT == "arm", exploded=SHOT == "exploded")
    if SHOT == "exploded":
        # lay the module flat, window up, so the stack reads vertically
        root.matrix_world = Matrix.Rotation(math.radians(-18), 4, "Z")
    else:
        orient(root, yaw)
    centre, radius = A.normalise(col)
    setup_render(SAMPLES)
    studio(centre, radius, az, el, lens, res, dof=SHOT not in ("spin", "exploded"))
    if SHOT == "spin":
        h = bpy.data.objects["holder"]
        for f in range(1, FRAMES + 2):
            h.rotation_euler[2] = TAU * (f - 1) / FRAMES
            h.keyframe_insert("rotation_euler", index=2, frame=f)
        for fc in h.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"
        led = bpy.data.materials["NB_LedGreen"].node_tree.nodes["Principled BSDF"].inputs["Emission Strength"]
        for f in range(1, FRAMES + 2):
            p = ((f - 1) / FRAMES * 3) % 1.0
            led.default_value = 6 + 16 * (math.exp(-40 * p * p) + 0.45 * math.exp(-60 * (p - 0.22) ** 2))
            led.keyframe_insert("default_value", frame=f)
        sc.frame_start, sc.frame_end = 1, min(FRAMES, FRAME_CAP) if FRAME_CAP else FRAMES
        d = arg("--spin-dir", os.path.join(OUT, "spin"))
        os.makedirs(d, exist_ok=True)
        for f in os.listdir(d):
            os.remove(os.path.join(d, f))
        sc.render.filepath = os.path.join(d, "f_")
        bpy.ops.render.render(animation=True)
    else:
        sc.render.filepath = os.path.join(OUT, SHOT + ".png")
        bpy.ops.render.render(write_still=True)
    print("HERO DONE", SHOT)


if __name__ == "__main__":
    main()
