# ============================================================
# Nova-Band prototype pod: the FreeCAD case (hardware/casing/out/*.stl)
# around a LILYGO T-Display-S3 Touch, with the firmware UI playing on
# its screen (frames from the PC simulator, build/sim/png).
#
#   import: spec_from_file_location("pod", "blender/pod_model.py")
#   pod.build(col, screen="build/sim/png", start=1, strap=True) -> root empty
#
# Units: metres. Pod frame: X along the case (USB-C at -X), Z up (screen).
# ============================================================
import bmesh
import bpy
import math
import os
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
CASE = os.path.join(PROJECT, "hardware", "casing", "out")
MM = 0.001


def srgb(h):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c) + (1.0,)


def _bsdf(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    return m, m.node_tree, m.node_tree.nodes["Principled BSDF"]


def _set(b, names, v):
    for n in ([names] if isinstance(names, str) else names):
        if n in b.inputs:
            b.inputs[n].default_value = v
            return


def mat_petg(name, hexcol):
    """3D-printed PETG: satin, with 0.2 mm layer lines as a bump along Z."""
    m, nt, b = _bsdf(name)
    _set(b, "Base Color", srgb(hexcol))
    _set(b, "Roughness", 0.32)
    _set(b, ["Coat Weight", "Clearcoat"], 0.25)
    _set(b, ["Specular IOR Level", "Specular"], 0.5)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs[0])
    comb = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(sep.outputs["Z"], comb.inputs["X"])
    wave = nt.nodes.new("ShaderNodeTexWave")
    wave.bands_direction = "X"
    wave.inputs["Scale"].default_value = (2 * math.pi / 20.0) / (0.2 * MM)   # 0.2 mm period
    wave.inputs["Distortion"].default_value = 0.4
    nt.links.new(comb.outputs[0], wave.inputs["Vector"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.18
    bump.inputs["Distance"].default_value = 0.00004
    nt.links.new(wave.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m


def mat_simple(name, hexcol, rough=0.4, metal=0.0, coat=0.0):
    m, nt, b = _bsdf(name)
    _set(b, "Base Color", srgb(hexcol))
    _set(b, "Roughness", rough)
    _set(b, "Metallic", metal)
    _set(b, ["Coat Weight", "Clearcoat"], coat)
    return m


def mat_screen(folder, start, count, strength=2.2):
    """Emissive LCD playing a PNG sequence, under a glossy glass coat."""
    m = bpy.data.materials.new("PodScreen")
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    files = sorted(f for f in os.listdir(folder) if f.endswith(".png"))
    img = bpy.data.images.load(os.path.join(folder, files[0]))
    img.source = "SEQUENCE"
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.interpolation = "Linear"
    tex.image_user.frame_duration = count
    tex.image_user.frame_start = start
    tex.image_user.frame_offset = 0
    tex.image_user.use_auto_refresh = True
    tex.image_user.use_cyclic = True
    emit = nt.nodes.new("ShaderNodeEmission")
    emit.inputs["Strength"].default_value = strength
    nt.links.new(tex.outputs["Color"], emit.inputs["Color"])
    glass = nt.nodes.new("ShaderNodeBsdfGlossy")
    glass.inputs["Roughness"].default_value = 0.04
    glass.inputs["Color"].default_value = (0.9, 0.9, 0.9, 1)
    lw = nt.nodes.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.12
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(lw.outputs["Fresnel"], mix.inputs["Fac"])
    nt.links.new(emit.outputs[0], mix.inputs[1])
    nt.links.new(glass.outputs[0], mix.inputs[2])
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(mix.outputs[0], out.inputs[0])
    return m


def _import_stl(path, name, col, material):
    before = set(bpy.data.objects)
    bpy.ops.import_mesh.stl(filepath=path)
    o = [x for x in bpy.data.objects if x not in before][0]
    for c in list(o.users_collection):
        c.objects.unlink(o)
    col.objects.link(o)
    o.name = name
    o.scale = (MM, MM, MM)
    o.data.materials.clear()
    o.data.materials.append(material)
    for p in o.data.polygons:
        p.use_smooth = True
    if hasattr(o.data, "use_auto_smooth"):
        o.data.use_auto_smooth = True
        o.data.auto_smooth_angle = math.radians(35)
    return o


def _rbox(col, name, sx, sy, sz, loc, r, material, seg=4):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * sx, v.co.y * sy, v.co.z * sz))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    col.objects.link(o)
    o.location = loc
    if r > 0:
        bv = o.modifiers.new("bevel", "BEVEL")
        bv.width, bv.segments, bv.limit_method = r, seg, "ANGLE"
    for p in me.polygons:
        p.use_smooth = True
    me.materials.append(material)
    return o


def _plane(col, name, sx, sy, loc, material):
    me = bpy.data.meshes.new(name)
    hx, hy = sx / 2, sy / 2
    me.from_pydata([(-hx, -hy, 0), (hx, -hy, 0), (hx, hy, 0), (-hx, hy, 0)], [], [(0, 1, 2, 3)])
    me.uv_layers.new(name="UVMap")
    for i, uv in enumerate(((0, 0), (1, 0), (1, 1), (0, 1))):
        me.uv_layers[0].data[i].uv = uv
    o = bpy.data.objects.new(name, me)
    col.objects.link(o)
    o.location = loc
    me.materials.append(material)
    return o


def params():
    import importlib.util
    spec = importlib.util.spec_from_file_location("case_params", os.path.join(PROJECT, "hardware", "casing", "case_params.py"))
    P = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(P)
    return P


def build(col, screen=None, start=1, count=None, strap=True, exploded=0.0, case_color="#6b1a26"):
    """exploded: 0..1 lifts the lid, caps and board apart (for breakdown shots)."""
    P = params()
    root = bpy.data.objects.new("Pod", None)
    col.objects.link(root)
    petg = mat_petg("PETG", case_color)
    parts = []
    lift = lambda k: exploded * k * MM
    bot = _import_stl(os.path.join(CASE, "case_bottom.stl"), "CaseBottom", col, petg)
    top = _import_stl(os.path.join(CASE, "case_top.stl"), "CaseTop", col, petg)
    top.location.z = lift(34)
    parts += [bot, top]
    capm = mat_simple("CapGrey", "#d9d4d6", rough=0.45)
    for sy in (-1, 1):
        cap = _import_stl(os.path.join(CASE, "button_cap.stl"), "Cap", col, capm)
        cap.location = (P.BTN_X * MM, sy * P.BTN_Y * MM, (P.PCB_TOP + 1.8) * MM + lift(26))
        parts.append(cap)
    # board: black PCB, touch glass, the LCD, USB-C
    pcb = _rbox(col, "PCB", P.BOARD_L * MM, P.BOARD_W * MM, P.BOARD_T * MM,
                (0, 0, (P.PCB_Z + P.BOARD_T / 2) * MM + lift(14)), 0.4 * MM, mat_simple("PCB", "#0d0d0f", 0.5))
    glass_h = P.GLASS_ABOVE - 1.2
    glass = _rbox(col, "Glass", (P.GLASS_X1 - P.GLASS_X0) * MM, P.GLASS_W * MM, glass_h * MM,
                  (((P.GLASS_X0 + P.GLASS_X1) / 2) * MM, 0, (P.GLASS_TOP - glass_h / 2) * MM + lift(20)),
                  P.GLASS_R * MM, mat_simple("GlassBlack", "#030304", 0.05, coat=1.0), seg=6)
    parts += [pcb, glass]
    usb = _rbox(col, "USB", 7.4 * MM, 8.9 * MM, 3.2 * MM,
                ((-P.BOARD_L / 2 + 3.0) * MM, 0, (P.PCB_TOP + 1.6) * MM + lift(14)), 1.2 * MM,
                mat_simple("Steel", "#c9c9cc", 0.25, metal=1.0))
    parts.append(usb)
    if screen:
        n = count or len([f for f in os.listdir(screen) if f.endswith(".png")])
        scr = _plane(col, "Screen", P.ACTIVE_L * MM, P.ACTIVE_W * MM,
                     (P.ACTIVE_CX * MM, 0, P.GLASS_TOP * MM + 0.02 * MM + lift(20)), mat_screen(screen, start, n))
        parts.append(scr)
    if strap:
        parts.append(_strap(col, P))
    for o in parts:
        o.parent = root
    return root


def _strap(col, P):
    """A 38 mm woven strap through the tunnel, curving down both sides."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("nb_hero", os.path.join(HERE, "novaband_hero.py"))
    H = importlib.util.module_from_spec(spec)
    import sys
    argv = sys.argv
    sys.argv = argv[:1]
    spec.loader.exec_module(H)
    sys.argv = argv
    fab = H.fabric("PodStrap", "#1c0409", "#431019", period=0.0009, bump=0.6)
    zc = (P.TUNNEL_Z0 + P.TUNNEL_H / 2) * MM
    pts = []
    for i in range(41):                      # along Y, bending down past the case sides
        y = -0.045 + 0.09 * i / 40
        z = zc - max(0.0, abs(y) - 0.017) ** 2 * 9.0
        pts.append(Vector((0, y, z)))
    fr = []
    for i, p in enumerate(pts):
        a, b = pts[max(i - 1, 0)], pts[min(i + 1, len(pts) - 1)]
        t = (b - a).normalized()
        nrm = Vector((0, -t.z, t.y))
        fr.append((p, t, nrm))
    hw, ht = 19 * MM, 0.8 * MM
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    ring = [(-hw, -ht), (hw, -ht), (hw, ht), (-hw, ht)]
    rings = []
    for p, t, nrm in fr:
        side = Vector((1, 0, 0))
        rings.append([bm.verts.new(p + side * x + nrm * z) for x, z in ring])
    s = 0.0
    for i in range(len(rings) - 1):
        seg = (fr[i + 1][0] - fr[i][0]).length
        for j in range(4):
            f = bm.faces.new((rings[i][j], rings[i][(j + 1) % 4], rings[i + 1][(j + 1) % 4], rings[i + 1][j]))
            for loop, (u, v) in zip(f.loops, ((s, j * 0.02), (s, (j + 1) * 0.02), (s + seg, (j + 1) * 0.02), (s + seg, j * 0.02))):
                loop[uvl].uv = (u, v)
        s += seg
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new("Strap")
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new("Strap", me)
    col.objects.link(o)
    o.modifiers.new("sub", "SUBSURF").levels = 1
    me.materials.append(fab)
    return o
