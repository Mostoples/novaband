# ============================================================
# "Detailed" Nova: extra realism layered on blender/mascot.py.
#
#   import mascot_detail as D
#   D.materials(M)        after M.materials()   (richer iris, whisker material)
#   D.apply(M, screen=..) after the mascot is built, before posing/keys
#
# - plush fur: particle hair (short, clumped, with children) on every
#   fur-material part; it takes the spot pattern from the same material
# - whiskers: thin curved strands from the muzzle
# - eyes: iris with a radial gradient, dark limbal ring and fibre noise
# - Nova-Band module: a live screen (firmware simulator frames, emissive)
#   replaces the printed "N", exactly like the real T-Display prototype
# ============================================================
import math
import os

import bpy
from mathutils import Matrix, Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def materials(M):
    M.MAT["iris"] = iris_mat()
    M.MAT["whisker"] = M.glossy("M_Whisker", "#f4ece6", rough=0.35, spec=0.4)
    M.MAT["screen_glass"] = M.glossy("M_ScreenGlass", "#050304", rough=0.05, coat=1.0, spec=0.6)


def iris_mat():
    m = bpy.data.materials.new("M_IrisDetail")
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    gen = nt.nodes.new("ShaderNodeTexCoord").outputs["Generated"]
    sub = nt.nodes.new("ShaderNodeVectorMath")
    sub.operation = "SUBTRACT"
    nt.links.new(gen, sub.inputs[0])
    sub.inputs[1].default_value = (0.5, 0.5, 0.5)
    mul = nt.nodes.new("ShaderNodeVectorMath")
    mul.operation = "MULTIPLY"
    nt.links.new(sub.outputs[0], mul.inputs[0])
    mul.inputs[1].default_value = (1.0, 0.0, 1.0)
    ln = nt.nodes.new("ShaderNodeVectorMath")
    ln.operation = "LENGTH"
    nt.links.new(mul.outputs[0], ln.inputs[0])
    # fibre noise stretched radially: noise on the direction, not the distance
    nrm = nt.nodes.new("ShaderNodeVectorMath")
    nrm.operation = "NORMALIZE"
    nt.links.new(mul.outputs[0], nrm.inputs[0])
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 18.0
    nz.inputs["Detail"].default_value = 6.0
    nt.links.new(nrm.outputs[0], nz.inputs["Vector"])
    add = nt.nodes.new("ShaderNodeMath")
    add.operation = "MULTIPLY_ADD"
    nt.links.new(nz.outputs["Fac"], add.inputs[0])
    add.inputs[1].default_value = 0.08
    nt.links.new(ln.outputs["Value"], add.inputs[2])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    cr = ramp.color_ramp
    cr.elements[0].position, cr.elements[0].color = 0.10, (0.36, 0.17, 0.05, 1)
    cr.elements[1].position, cr.elements[1].color = 0.50, (0.02, 0.01, 0.005, 1)
    for pos, col in ((0.26, (0.20, 0.09, 0.03, 1)), (0.40, (0.07, 0.035, 0.015, 1))):
        e = cr.elements.new(pos)
        e.color = col
    nt.links.new(add.outputs[0], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.25
    for k in ("Coat Weight", "Clearcoat"):
        if k in b.inputs:
            b.inputs[k].default_value = 1.0
    for k in ("Coat Roughness", "Clearcoat Roughness"):
        if k in b.inputs:
            b.inputs[k].default_value = 0.02
    return m


# ---------------------------------------------------------------- fur
FUR_SKIP = ("Lid.", "EarIn.")


def add_fur(ob, density=26000, length=0.0075, children=10):
    me = ob.data
    area = sum(p.area for p in me.polygons)
    mod = ob.modifiers.new("fur", "PARTICLE_SYSTEM")
    st = mod.particle_system.settings
    st.type = "HAIR"
    st.use_advanced_hair = False        # simple mode: hair_length is the real length
    st.count = max(200, int(area * density))
    st.hair_length = length
    st.emit_from = "FACE"
    st.use_emit_random = True
    st.distribution = "JIT"
    st.length_random = 0.3
    st.child_type = "INTERPOLATED"
    st.rendered_child_count = children
    st.child_percent = 1
    st.child_length = 0.85
    st.child_length_threshold = 0.4
    st.clump_factor = 0.25
    st.clump_shape = -0.2
    st.roughness_1 = 0.0012
    st.roughness_1_size = 0.6
    st.roughness_endpoint = 0.0016
    st.render_step = 3
    st.display_step = 2
    st.root_radius = 1.0
    st.tip_radius = 0.0
    st.radius_scale = 0.00055
    st.use_close_tip = True
    st.material = 1
    # no fur on the white piping / cuffs: density follows 1 - trim (the per-vertex trim mask)
    ca = me.color_attributes.get("trim")
    if ca is not None:
        vg = ob.vertex_groups.new(name="fur_density")
        for i, c in enumerate(ca.data):
            w = 1.0 - min(max((c.color[0] - 0.25) / 0.3, 0.0), 1.0)
            if w > 0:
                vg.add([i], w, "REPLACE")
        mod.particle_system.vertex_group_density = vg.name
    return st


def fur_all(M, scale=1.0):
    n = 0
    for ob in list(M.COLL.objects):
        if ob.type != "MESH" or not ob.material_slots:
            continue
        mat = ob.material_slots[0].material
        if not mat or mat.name.split(".")[0] not in ("M_Fur",) or ob.name.startswith(FUR_SKIP):
            continue
        st = add_fur(ob, density=26000 * scale)
        n += st.count * (1 + st.rendered_child_count)
    return n


# ---------------------------------------------------------------- whiskers
def whiskers(M):
    for sx in (1, -1):
        for k, (z, dz, spread) in enumerate(((1.604, 0.012, 0.0), (1.596, 0.0, 0.0), (1.589, -0.014, 0.0))):
            root = M.on_face(0.058 * sx, z, 0.0)
            pts = []
            for i in range(7):
                u = i / 6
                pts.append(root + Vector((sx * 0.13 * u, -0.025 * u + 0.012 * u * u, (dz - 0.01 * u) * u)))
            M.curve_line("Whisker.%d.%d" % (sx, k), pts, M.MAT["whisker"], r=0.0009, joint="head")


# ---------------------------------------------------------------- band screen
def band_screen(M, image_path, sequence=False, frames=1, start=1):
    S, E = Vector(M.J["shoulder.L"]), Vector(M.J["elbow.L"])
    axis = (E - S).normalized()
    P = S.lerp(E, 0.52)
    o = (Vector((1, -0.8, 0)) - axis * Vector((1, -0.8, 0)).dot(axis)).normalized()
    zt, yt = o, -axis
    xt = yt.cross(zt)
    Mrot = Matrix((xt, yt, zt)).transposed().to_4x4()
    C = P + o * 0.097
    for n in ("BandN", "BandLed"):
        ob = bpy.data.objects.get(n)
        if ob:
            ob.hide_render = ob.hide_viewport = True
    # glass panel + the screen just above it
    M.rbox("BandGlass", Matrix.Translation(C + o * 0.0079) @ Mrot, (0.033, 0.049, 0.0012), M.MAT["screen_glass"],
           bevel=0.0012, joint="shoulder.L")
    w, h = 0.0255, 0.046                       # 170 x 320, the long side runs along the arm
    me = bpy.data.meshes.new("BandScreen")
    vs = [Mrot @ Vector((x, y, 0)) + C + o * 0.0088 for x, y in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2),
                                                                  (-w / 2, h / 2))]
    me.from_pydata([tuple(v) for v in vs], [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new(name="UVMap")
    # image is landscape (320 wide): rotate 90 degrees so its width follows the arm
    for loop, (u, v) in zip(uv.data, ((1, 1), (1, 0), (0, 0), (0, 1))):
        loop.uv = (u, v)
    ob = bpy.data.objects.new("BandScreen", me)
    M.COLL.objects.link(ob)
    mat = bpy.data.materials.new("M_BandScreen")
    mat.use_nodes = True
    nt = mat.node_tree
    for nd in list(nt.nodes):
        if nd.type == "BSDF_PRINCIPLED":
            nt.nodes.remove(nd)
    out = nt.nodes["Material Output"]
    tex = nt.nodes.new("ShaderNodeTexImage")
    img = bpy.data.images.load(image_path)
    if sequence:
        img.source = "SEQUENCE"
        tex.image_user.frame_duration = frames
        tex.image_user.frame_start = start
        tex.image_user.use_cyclic = True
        tex.image_user.use_auto_refresh = True
    tex.image = img
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = 2.2
    nt.links.new(tex.outputs["Color"], em.inputs["Color"])
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    me.materials.append(mat)
    M.attach(ob, "shoulder.L")
    return ob


def apply(M, screen=None, fur=1.0, sequence=False, frames=1):
    whiskers(M)
    if screen:
        band_screen(M, screen, sequence=sequence, frames=frames)
    n = fur_all(M, fur) if fur else 0
    for ob in M.COLL.objects:                  # a touch more geometry where it shows
        for md in ob.modifiers:
            if md.type == "SUBSURF" and ob.name.split(".")[0] in ("Head", "Mask", "Muzzle", "Torso"):
                md.render_levels = 3
    return n
