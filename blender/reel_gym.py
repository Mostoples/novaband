# ============================================================
# Nova-Band showreel — a real gym, rendered with Cycles (Blender CLI)
#
#   blender -b -P blender/reel_gym.py -- --shot establish [--test 50] [--samples 64] [--res 1920x1080]
#   blender -b -P blender/reel_gym.py -- --shot all
#
# Environment and props are Sketchfab models (CC-BY, see
# build/sketchfab/credits.json), fetched with tools/sketchfab.py:
#   training-gym (the room), runner (scanned athlete), treadmill,
#   dumbbell-rack, kettlebell, bottle, sports-bag, shoes, phone.
# The Nova-Band pieces are ours: the printed prototype pod with the
# firmware UI on its screen (blender/pod_model.py) and the concept band
# (blender/novaband_hero.py).
#
# Frames -> build/reel2/<shot>/f_####.png, cut by tools/make-showreel2.py
# ============================================================
import bmesh
import bpy
import importlib.util
import math
import os
import sys
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
SF = os.path.join(PROJECT, "build", "sketchfab")
OUT = os.path.join(PROJECT, "build", "reel2")
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
arg = lambda k, d=None: ARGS[ARGS.index(k) + 1] if k in ARGS else d
SHOT = arg("--shot", "establish")
TEST = arg("--test")
SAMPLES = int(arg("--samples", 64))
RES = tuple(int(v) for v in arg("--res", "1920x1080").split("x"))
FPS = 25
sys.argv = sys.argv[:1]


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, file))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


A = load("nb_assets", "novaband_assets.py")
POD = load("pod_model", "pod_model.py")
HERO = load("nb_hero", "novaband_hero.py")
srgb = A.srgb

# arm of the scanned runner, in the runner's own frame (measured: build/runner_arm2.py)
ARM_C = Vector((0.216, 0.073, 0.475))
ARM_AX = Vector((0.238, 0.800, -0.551)).normalized()
ARM_R = 0.058
RUNNER_AT = Vector((3.05, -0.55, 0.0))          # treadmill belt centre on the floor
BENCH_AT = Vector((2.05, 2.35, 0.0))


# ------------------------------------------------------------------ helpers
def import_gltf(name, col):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=os.path.join(SF, name, "scene.gltf"))
    new = [o for o in bpy.data.objects if o not in before]
    for o in new:
        for c in list(o.users_collection):
            c.objects.unlink(o)
        col.objects.link(o)
    root = bpy.data.objects.new(name, None)
    col.objects.link(root)
    for o in new:
        if o.parent is None:
            o.parent = root
    return root, new


def bounds(objs):
    bpy.context.view_layer.update()
    lo = Vector((1e9,) * 3)
    hi = Vector((-1e9,) * 3)
    for o in objs:
        if o.type != "MESH":
            continue
        for c in o.bound_box:
            w = o.matrix_world @ Vector(c)
            lo = Vector(map(min, lo, w))
            hi = Vector(map(max, hi, w))
    return lo, hi


def place(root, objs, height=None, at=Vector(), rot_z=0.0, scale=None):
    """Scale to a real height (or factor), rest on the floor at `at`."""
    lo, hi = bounds(objs)
    k = scale if scale else (height / max(hi.z - lo.z, 1e-6) if height else 1.0)
    root.scale = (k, k, k)
    root.rotation_euler = (0, 0, rot_z)
    bpy.context.view_layer.update()
    lo, hi = bounds(objs)
    c = (lo + hi) / 2
    root.location += Vector((at.x - c.x, at.y - c.y, at.z - lo.z))
    bpy.context.view_layer.update()
    return bounds(objs)


def settle(root, objs, at):
    """Move (keeping rotation and scale) so the object rests on `at`."""
    lo, hi = bounds(objs)
    c = (lo + hi) / 2
    root.location += Vector((at.x - c.x, at.y - c.y, at.z - lo.z))
    bpy.context.view_layer.update()


def mat(name, hexcol, rough=0.5, metal=0.0, coat=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    A.set_input(b, "Base Color", srgb(hexcol))
    A.set_input(b, "Roughness", rough)
    A.set_input(b, "Metallic", metal)
    A.set_input(b, ["Coat Weight", "Clearcoat"], coat)
    return m


def box(col, name, size, loc, material, bevel=0.0):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    col.objects.link(o)
    o.location = loc
    me.materials.append(material)
    if bevel:
        b = o.modifiers.new("b", "BEVEL")
        b.width, b.segments = bevel, 3
    return o


def emissive_image(path, strength=1.0):
    m = bpy.data.materials.new("img_" + os.path.basename(path))
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    t = nt.nodes.new("ShaderNodeTexImage")
    t.image = bpy.data.images.load(path)
    e = nt.nodes.new("ShaderNodeEmission")
    e.inputs["Strength"].default_value = strength
    nt.links.new(t.outputs["Color"], e.inputs["Color"])
    o = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(e.outputs[0], o.inputs[0])
    return m


# ------------------------------------------------------------------ the gym
def build_gym(sc):
    col = bpy.data.collections.new("gym")
    sc.collection.children.link(col)
    root, objs = import_gltf("training-gym", col)
    for o in objs:
        # the window panes are opaque planes in the source file: remove them so
        # the sun can reach the floor; a stray helper sphere goes too
        if o.name.startswith(("Object_8", "Object_15", "Icosphere")):
            o.hide_render = True
    return col


def lighting(sc, haze=0.0):
    w = sc.world
    nt = w.node_tree
    bg = nt.nodes["Background"]
    sky = nt.nodes.new("ShaderNodeTexSky")
    sky.sky_type = "NISHITA"
    sky.sun_elevation = math.radians(24)
    sky.sun_rotation = math.radians(185)
    sky.altitude = 200
    sky.air_density, sky.dust_density = 1.2, 2.5
    nt.links.new(sky.outputs[0], bg.inputs[0])
    bg.inputs[1].default_value = 0.35
    # the sun rakes in through the big left-wall windows toward the training floor
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    sun.data.energy = 5.5
    sun.data.angle = math.radians(1.2)
    sun.data.color = (1.0, 0.9, 0.78)
    d = Vector((math.cos(math.radians(24)), 0.30, -math.sin(math.radians(24)))).normalized()
    sun.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    sc.collection.objects.link(sun)
    # practical ceiling fixtures (warm) + a soft cool bounce
    for i, (x, y) in enumerate(((-4, -3), (-4, 3), (0, -3), (0, 3), (3.5, -3), (3.5, 3))):
        L = bpy.data.objects.new("fix%d" % i, bpy.data.lights.new("fix%d" % i, "AREA"))
        L.data.energy, L.data.size, L.data.size_y, L.data.shape = 380, 2.2, 0.35, "RECTANGLE"
        L.data.color = (1.0, 0.86, 0.7)
        L.location = (x, y, 5.6)
        sc.collection.objects.link(L)
    fill = bpy.data.objects.new("fill", bpy.data.lights.new("fill", "AREA"))
    fill.data.energy, fill.data.size, fill.data.color = 900, 6, (0.8, 0.88, 1.0)
    fill.location = (6.0, 0.5, 3.0)
    fill.rotation_euler = (Vector((0, 0, 1)) - fill.location).to_track_quat("-Z", "Y").to_euler()
    fill.visible_glossy = False
    sc.collection.objects.link(fill)
    if haze > 0:                                 # light shafts through the windows
        bpy.ops.mesh.primitive_cube_add(size=1, location=(-0.5, -0.4, 4.2))
        v = bpy.context.active_object
        v.scale = (14.4, 15.4, 8.4)
        vm = bpy.data.materials.new("haze")
        vm.use_nodes = True
        nt2 = vm.node_tree
        nt2.nodes.remove(nt2.nodes["Principled BSDF"])
        pv = nt2.nodes.new("ShaderNodeVolumePrincipled")
        pv.inputs["Density"].default_value = haze
        pv.inputs["Anisotropy"].default_value = 0.55
        pv.inputs["Color"].default_value = (1.0, 0.95, 0.9, 1)
        nt2.links.new(pv.outputs[0], nt2.nodes["Material Output"].inputs["Volume"])
        v.data.materials.append(vm)
        v.visible_shadow = False
    return sun


# ------------------------------------------------------------------ runner on a treadmill, pod on the arm
def build_runner(sc, screen_start=200):
    col = bpy.data.collections.new("runner")
    sc.collection.children.link(col)
    tr, tobjs = import_gltf("treadmill", col)
    place(tr, tobjs, scale=0.001, at=RUNNER_AT)
    # console must face the runner (runner faces -Y): put the tall end at -Y
    lo, hi = bounds(tobjs)
    tops = []
    for o in tobjs:
        if o.type == "MESH":
            mw = o.matrix_world
            tops += [(mw @ v.co) for v in o.data.vertices if (mw @ v.co).z > lo.z + 0.8 * (hi.z - lo.z)]
    if tops and sum(p.y for p in tops) / len(tops) > (lo.y + hi.y) / 2:
        tr.rotation_euler.z += math.pi
        place(tr, tobjs, scale=0.001, at=RUNNER_AT, rot_z=math.pi)
    lo, hi = bounds(tobjs)
    belt = lo.z + 0.21                       # deck height of the model (measured visually)

    rn, robjs = import_gltf("runner", col)
    rn.location = Vector((RUNNER_AT.x, RUNNER_AT.y + 0.15, belt + 0.95))
    bpy.context.view_layer.update()

    # the pod strapped to the left upper arm, screen facing out and a little forward
    M = rn.matrix_world
    c = M @ ARM_C
    ax = (M.to_3x3() @ ARM_AX).normalized()
    out = Vector((1.0, -0.35, 0.0))
    out = (out - ax * out.dot(ax)).normalized()
    pcol = bpy.data.collections.new("pod")
    sc.collection.children.link(pcol)
    pod = POD.build(pcol, case_color="#4e101b", screen=os.path.join(PROJECT, "build", "sim", "png"), start=screen_start, strap=False)
    y = out.cross(ax)                      # right-handed: X = along the arm, Z = out of the screen
    R = Matrix((ax, y, out)).transposed().to_4x4()
    pod.matrix_world = Matrix.Translation(c + out * (ARM_R + 0.0035)) @ R
    band = arm_strap(pcol, c, ax, out, ARM_R + 0.0022)
    return col, rn, pod, c, ax, out


def arm_strap(col, c, ax, out, r):
    """A woven 38 mm band around the upper arm (under the pod's tunnel)."""
    fab = HERO.fabric("ArmStrap", "#1c0409", "#431019", period=0.0009, bump=0.6)
    y = ax.cross(out)
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    N, hw, t = 72, 0.019, 0.0016
    rings = []
    for i in range(N):
        a = 2 * math.pi * i / N
        d = out * math.cos(a) + y * math.sin(a)
        rr = r * (1.0 + 0.08 * math.cos(2 * a))           # arms are not round
        rings.append([bm.verts.new(c + d * (rr + dz) + ax * dx) for dx, dz in ((-hw, 0), (hw, 0), (hw, t), (-hw, t))])
    for i in range(N):
        a, b = rings[i], rings[(i + 1) % N]
        for j in range(4):
            f = bm.faces.new((a[j], a[(j + 1) % 4], b[(j + 1) % 4], b[j]))
            for loop, uv in zip(f.loops, ((i * .005, j * .02), (i * .005, (j + 1) * .02), ((i + 1) * .005, (j + 1) * .02), ((i + 1) * .005, j * .02))):
                loop[uvl].uv = uv
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new("ArmStrap")
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    o = bpy.data.objects.new("ArmStrap", me)
    col.objects.link(o)
    me.materials.append(fab)
    return o


# ------------------------------------------------------------------ bench with props
def build_bench(sc):
    col = bpy.data.collections.new("bench")
    sc.collection.children.link(col)
    wood = mat("oak", "#8a6242", rough=0.55, coat=0.2)
    steel = mat("steel_black", "#1b1b1d", rough=0.35, metal=0.9)
    top_z = 0.45
    box(col, "BenchTop", (1.5, 0.36, 0.05), BENCH_AT + Vector((0, 0, top_z - 0.025)), wood, bevel=0.006)
    for sx in (-0.62, 0.62):
        box(col, "Leg", (0.05, 0.32, top_z - 0.05), BENCH_AT + Vector((sx, 0, (top_z - 0.05) / 2)), steel, bevel=0.004)
    props = {}
    for name, h, off, rz in (("bottle", 0.25, (-0.45, 0.02, top_z), 0.3),
                             ("kettlebell", 0.28, (0.95, -0.35, 0.0), 0.8),
                             ("sports-bag", None, (-1.25, -0.15, 0.0), -0.4),
                             ("shoes", None, (0.35, -0.55, 0.0), 1.9),
                             ("dumbbell-rack", None, (2.25, 0.55, 0.0), -1.57)):
        r, objs = import_gltf(name, col)
        place(r, objs, height=h, at=BENCH_AT + Vector(off), rot_z=rz)
        props[name] = (r, objs)
    # phone lying on the bench, screen up, running the web app
    r, objs = import_gltf("phone", col)
    lo, hi = bounds(objs)                          # upright model: screen faces +Y
    screen_png = os.path.join(PROJECT, "build", "reel2", "app_phone.png")
    if os.path.exists(screen_png):
        w, h = (hi.x - lo.x) * 0.905, (hi.z - lo.z) * 0.955
        cx, cz = (lo.x + hi.x) / 2, (lo.z + hi.z) / 2
        me = bpy.data.meshes.new("PhoneScreen")
        yv = hi.y + 0.0002
        me.from_pydata([(cx - w / 2, yv, cz - h / 2), (cx + w / 2, yv, cz - h / 2),
                        (cx + w / 2, yv, cz + h / 2), (cx - w / 2, yv, cz + h / 2)], [], [(0, 1, 2, 3)])
        uv = me.uv_layers.new(name="UVMap")
        for i, c in enumerate(((0, 0), (1, 0), (1, 1), (0, 1))):
            uv.data[i].uv = c
        ps = bpy.data.objects.new("PhoneScreen", me)
        col.objects.link(ps)
        me.materials.append(emissive_image(screen_png, 1.3))
        ps.parent = r
        objs.append(ps)
    # lie it flat, screen up (+Y -> +Z), top of the screen pointing away from the camera
    r.rotation_euler = (math.radians(90), 0, math.radians(200))
    settle(r, objs, BENCH_AT + Vector((0.14, 0.03, top_z)))
    props["phone"] = (r, objs)
    return col, props, top_z


# ------------------------------------------------------------------ camera
def camera(sc, lens=35, fstop=None):
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    sc.collection.objects.link(cam)
    cam.data.lens = lens
    cam.data.sensor_width = 36
    cam.data.clip_start = 0.01
    if fstop:
        cam.data.dof.use_dof = True
        cam.data.dof.aperture_fstop = fstop
        cam.data.dof.aperture_blades = 9
    sc.camera = cam
    return cam


def keyframe_path(cam, n, pos_fn, look_fn, focus_fn=None, up=None):
    for f in range(1, n + 1):
        t = (f - 1) / max(n - 1, 1)
        e = t * t * (3 - 2 * t)
        cam.location = pos_fn(t, e)
        tgt = look_fn(t, e)
        if up is None:
            cam.rotation_euler = (tgt - cam.location).to_track_quat("-Z", "Y").to_euler()
        else:                                      # roll the frame so `up` reads as up
            fwd = (tgt - cam.location).normalized()
            y = (up - fwd * up.dot(fwd)).normalized()
            z = -fwd
            x = y.cross(z)
            cam.rotation_euler = Matrix((x, y, z)).transposed().to_euler()
        cam.keyframe_insert("location", frame=f)
        cam.keyframe_insert("rotation_euler", frame=f)
        if focus_fn:
            cam.data.dof.focus_distance = focus_fn(t, e, tgt)
            cam.data.dof.keyframe_insert("focus_distance", frame=f)


# ------------------------------------------------------------------ shots
def shot_establish(sc):
    lighting(sc, haze=0.004)
    _, rn, pod, c, ax, out = build_runner(sc, screen_start=180)
    build_bench(sc)
    cam = camera(sc, 28, fstop=4.0)
    n = 110
    # from behind the row of heavy bags, gliding toward the runner (he faces us)
    keyframe_path(cam, n,
                  lambda t, e: Vector((4.35 - 0.55 * e, -6.1 + 2.3 * e, 1.55 - 0.15 * e)),
                  lambda t, e: Vector((2.9 - 0.1 * e, -0.2, 1.25)),
                  lambda t, e, tgt: (Vector((RUNNER_AT.x, RUNNER_AT.y, 1.3)) - cam.location).length)
    return n


def shot_orbit(sc):
    lighting(sc, haze=0.002)
    _, rn, pod, c, ax, out = build_runner(sc, screen_start=240)
    build_bench(sc)
    cam = camera(sc, 45, fstop=2.2)
    n = 125
    centre = Vector((RUNNER_AT.x, RUNNER_AT.y + 0.15, 1.42))
    def pos(t, e):
        a = math.radians(52 + 62 * e)                 # left side: where the pod is
        return centre + Vector((math.sin(a) * 2.0, -math.cos(a) * 2.0, 0.12 - 0.08 * e))
    keyframe_path(cam, n, pos, lambda t, e: centre + Vector((0.08, 0, -0.02)),
                  lambda t, e, tgt: (c - cam.location).length)
    return n


def shot_arm(sc):
    lighting(sc)
    _, rn, pod, c, ax, out = build_runner(sc, screen_start=520)
    build_bench(sc)
    cam = camera(sc, 90, fstop=2.4)
    n = 100
    p = c + out * (ARM_R + 0.012)
    side = ax.cross(out)
    keyframe_path(cam, n,
                  lambda t, e: p + out * (0.78 - 0.24 * e) + side * (0.10 - 0.06 * e) + Vector((0, 0, 0.10)),
                  lambda t, e: p,
                  lambda t, e, tgt: (tgt - cam.location).length * (1.0 + 1.6 * (1 - min(t / .4, 1)) ** 2),
                  up=-side)
    return n


def shot_bench(sc):
    lighting(sc)
    col, props, top_z = build_bench(sc)
    pcol = bpy.data.collections.new("pod2")
    sc.collection.children.link(pcol)
    pod = POD.build(pcol, case_color="#4e101b", screen=os.path.join(PROJECT, "build", "sim", "png"), start=100, strap=True)
    pod.location = BENCH_AT + Vector((-0.12, 0.03, top_z + 0.0005))
    pod.rotation_euler = (0, 0, math.radians(-12))
    # Bluetooth: rings of light rippling from the pod toward the phone
    phone_at = BENCH_AT + Vector((0.12, 0.02, top_z + 0.02))
    ring_m = bpy.data.materials.new("blewave")
    ring_m.use_nodes = True
    nt = ring_m.node_tree
    for nd in list(nt.nodes):
        nt.nodes.remove(nd)
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs[0].default_value = srgb("#ff6b7a")
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    o = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(mix.outputs[0], o.inputs[0])
    n = 100
    for k in range(3):
        bpy.ops.mesh.primitive_torus_add(major_radius=1, minor_radius=0.012, location=pod.location + Vector((0, 0, 0.018)))
        ring = bpy.context.active_object
        ring.data.materials.append(ring_m if k == 0 else ring_m.copy())
        m = ring.data.materials[0]
        for f in range(1, n + 1):
            ph = ((f - 1) / 40.0 + k / 3.0) % 1.0
            s = 0.02 + 0.22 * ph
            ring.scale = (s, s, s)
            ring.keyframe_insert("scale", frame=f)
            fac = m.node_tree.nodes["Mix Shader"].inputs["Fac"]
            fac.default_value = 0.9 * (1 - ph) ** 1.5
            fac.keyframe_insert("default_value", frame=f)
            em2 = m.node_tree.nodes["Emission"].inputs["Strength"]
            em2.default_value = 6.0
    cam = camera(sc, 50, fstop=2.4)
    look = BENCH_AT + Vector((0.0, 0.02, top_z + 0.02))
    keyframe_path(cam, n,
                  lambda t, e: look + Vector((-0.75 + 0.5 * e, -0.62, 0.30 - 0.05 * e)),
                  lambda t, e: look + Vector((-0.05 + 0.1 * e, 0, 0)),
                  lambda t, e, tgt: (tgt - cam.location).length)
    return n


def shot_exploded(sc):
    lighting(sc)
    build_bench(sc)
    pcol = bpy.data.collections.new("podx")
    sc.collection.children.link(pcol)
    n = 100
    at = BENCH_AT + Vector((-0.2, -0.05, 0.72))
    # rebuild per frame is heavy; instead animate the parts' Z offsets directly
    pod = POD.build(pcol, case_color="#4e101b", screen=os.path.join(PROJECT, "build", "sim", "png"), start=40, strap=False)
    pod.location = at
    parts = [o for o in pcol.objects if o.parent == pod]
    lift = {"CaseTop": 34, "Cap": 26, "Glass": 20, "Screen": 20, "PCB": 14, "USB": 14}
    base = {o.name: o.location.z for o in parts}
    for f in range(1, n + 1):
        t = (f - 1) / (n - 1)
        x = min(max((t - 0.12) / 0.45, 0), 1)
        x = x * x * (3 - 2 * x)
        for o in parts:
            k = next((v for key, v in lift.items() if o.name.startswith(key)), 0)
            o.location.z = base[o.name] + x * k * 0.001 * 1.6
            o.keyframe_insert("location", index=2, frame=f)
        pod.rotation_euler = (math.radians(12), 0, math.radians(-30 + 55 * t))
        pod.keyframe_insert("rotation_euler", frame=f)
    cam = camera(sc, 70, fstop=2.8)
    keyframe_path(cam, n,
                  lambda t, e: at + Vector((0.05, -0.36 + 0.06 * e, 0.16)),
                  lambda t, e: at + Vector((0, 0, 0.015)),
                  lambda t, e, tgt: (tgt - cam.location).length)
    return n


def shot_hero(sc):
    lighting(sc)
    sc.view_settings.exposure = -0.7            # keep the wine from washing out to pink
    build_bench(sc)
    hcol = bpy.data.collections.new("hero")
    sc.collection.children.link(hcol)
    root = HERO.build(hcol)
    HERO.orient(root, 0)
    holder = bpy.data.objects.new("holder", None)
    hcol.objects.link(holder)
    root.parent = holder
    at = BENCH_AT + Vector((0.48, 0.02, 0.45 + 0.046))
    holder.location = at
    n = 100
    for f in range(1, n + 1):
        holder.rotation_euler = (0, 0, math.radians(-40 + 70 * (f - 1) / (n - 1)))
        holder.keyframe_insert("rotation_euler", frame=f)
    cam = camera(sc, 85, fstop=2.2)
    look = at + Vector((0, 0, 0.004))
    keyframe_path(cam, n,
                  lambda t, e: look + Vector((0.10 - 0.06 * e, -0.74 + 0.10 * e, 0.16 - 0.03 * e)),
                  lambda t, e: look,
                  lambda t, e, tgt: (tgt - cam.location).length)
    return n


SHOTS = {"establish": shot_establish, "orbit": shot_orbit, "arm": shot_arm,
         "bench": shot_bench, "exploded": shot_exploded, "hero": shot_hero}


def render(name):
    sc = A.reset()
    A.MATS.clear()
    sc.render.film_transparent = False
    sc.cycles.samples = SAMPLES
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = 0.02
    sc.cycles.max_bounces = 6
    sc.cycles.volume_bounces = 1
    sc.cycles.volume_step_rate = 4.0
    sc.render.use_persistent_data = True
    sc.render.fps = FPS
    sc.view_settings.view_transform = "AgX" if "AgX" in [i.identifier for i in bpy.types.ColorManagedViewSettings.bl_rna.properties["view_transform"].enum_items] else "Filmic"
    sc.view_settings.look = "AgX - Medium High Contrast" if sc.view_settings.view_transform == "AgX" else "Medium High Contrast"
    sc.render.resolution_x, sc.render.resolution_y = RES
    build_gym(sc)
    n = SHOTS[name](sc)
    d = os.path.join(OUT, name)
    os.makedirs(d, exist_ok=True)
    sc.render.filepath = os.path.join(d, "f_")
    sc.render.image_settings.color_mode = "RGB"
    if TEST:
        sc.frame_set(int(TEST))
        sc.render.filepath = os.path.join(OUT, "test_%s.png" % name)
        bpy.ops.render.render(write_still=True)
    else:
        # --start / --end resume an interrupted shot (or redo a few frames)
        sc.frame_start, sc.frame_end = int(arg("--start", 1)), int(arg("--end", n))
        bpy.ops.render.render(animation=True)
    print("REEL DONE", name, n)


if __name__ == "__main__":                       # importable by blender/usecases.py
    for s in (SHOTS if SHOT == "all" else SHOT.split(",")):
        render(s)
