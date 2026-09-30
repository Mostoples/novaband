# ============================================================
# Nova-Band use-case film — six scenes with real, moving people (Cycles, CLI)
#
#   blender -b -P blender/usecases.py -- --shot park_run [--test 60] [--samples 48]
#   blender -b -P blender/usecases.py -- --shot all
#
#   park_run   morning run in the park: live heart rate on the arm
#   treadmill  gym session: run metrics on the band's screen
#   pushups    strength work: the IMU follows every rep
#   coach      early warning: the coach's phone rings when HR crosses the limit
#   recovery   sitting after the run: the readiness score
#   walk       everyday activity: steps and resting heart rate
#
# People are rigged, motion-captured Sketchfab models (CC-BY, credits in
# build/sketchfab/credits.json); the gym and props come from blender/reel_gym.py,
# the park is built here from Sketchfab trees, bushes and grass. The pod on
# each arm is parented to the upper-arm bone (blender/characters.py) and its
# screen plays the firmware simulator's scenario frames (build/sim/<scenario>).
# ============================================================
import bpy
import importlib.util
import math
import os
import random
import sys
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
arg = lambda k, d=None: ARGS[ARGS.index(k) + 1] if k in ARGS else d
SHOT = arg("--shot", "park_run")
TEST = arg("--test")
CPU = "--cpu" in ARGS
SAMPLES = int(arg("--samples", 48))
RES = tuple(int(v) for v in arg("--res", "1920x1080").split("x"))
START, END = arg("--start"), arg("--end")
N = 125                                     # frames per scene (5 s at 25 fps)
OUT = os.path.join(PROJECT, "build", "usecases")
SIM = os.path.join(PROJECT, "build", "sim")
sys.argv = sys.argv[:1]


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, file))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


RG = load("reel_gym", "reel_gym.py")        # gym, lights, bench, camera helpers
A, POD = RG.A, RG.POD
CH = load("characters", "characters.py")
srgb = A.srgb
JOG_HEIGHT = 1.78


# ------------------------------------------------------------------ render settings (same look as the gym reel)
def setup():
    sc = A.reset()
    A.MATS.clear()
    sc.render.film_transparent = False
    sc.cycles.samples = SAMPLES
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = 0.02
    sc.cycles.max_bounces = 6
    sc.render.use_persistent_data = True
    sc.render.fps = 25
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Medium High Contrast"
    sc.render.resolution_x, sc.render.resolution_y = RES
    sc.render.image_settings.file_format = "JPEG"
    sc.render.image_settings.quality = 94
    # other GPU jobs share this 8 GB card: cap texture size so a scene fits
    sc.cycles.texture_limit_render = "2048"
    if CPU:                                                # the GPU is taken by other jobs
        sc.cycles.device = "CPU"
    return sc


def pod_on(ch, scenario):
    return ch.strap_pod(POD, screen_dir=os.path.join(SIM, scenario), start=1)


def walk_forward(ch, speed, axis=Vector((1, 0, 0)), frames=N):
    """In-place cycle -> move the root at the planted-foot speed so feet do not slide."""
    p0 = ch.root.location.copy()
    for f in (1, frames + 20):
        ch.root.location = p0 + axis * speed * (f - 1)
        ch.root.keyframe_insert("location", frame=f)
    for fc in ch.root.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"


def hips_travel(ch, action):
    """Horizontal distance the hips cover over one cycle (root motion if large)."""
    ch.use_action(action)
    key = next((k for k in ("hips", "pelvis", "hip") if k in ch.bones), None)
    if not key:
        return 0.0
    sc = bpy.context.scene
    f0, f1 = int(action.frame_range[0]) + 1, int(action.frame_range[1])
    sc.frame_set(f0)
    a = ch.bone_world(key)
    sc.frame_set(f1)
    b = ch.bone_world(key)
    return (b - a).xy.length


def remove(objs):
    for o in objs:
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.data.orphans_purge(do_recursive=True)              # free their meshes and textures too


# ------------------------------------------------------------------ the park (procedural ground + Sketchfab plants)
def grass_material():
    m = bpy.data.materials.new("lawn")
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    n1 = nt.nodes.new("ShaderNodeTexNoise"); n1.inputs["Scale"].default_value = 0.35; n1.inputs["Detail"].default_value = 6
    n2 = nt.nodes.new("ShaderNodeTexNoise"); n2.inputs["Scale"].default_value = 60; n2.inputs["Detail"].default_value = 8
    nt.links.new(tc.outputs["Object"], n1.inputs["Vector"])
    nt.links.new(tc.outputs["Object"], n2.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = srgb("#2f4a1f")
    ramp.color_ramp.elements[1].color = srgb("#7d8a3e")
    ramp.color_ramp.elements.new(0.55).color = srgb("#4f6d2a")
    mix = nt.nodes.new("ShaderNodeMath"); mix.operation = "MULTIPLY_ADD"
    nt.links.new(n1.outputs["Fac"], mix.inputs[0]); mix.inputs[1].default_value = 0.7
    nt.links.new(n2.outputs["Fac"], mix.inputs[2])
    mul = nt.nodes.new("ShaderNodeMath"); mul.operation = "MULTIPLY"; mul.inputs[1].default_value = 0.62
    nt.links.new(mix.outputs[0], mul.inputs[0])
    nt.links.new(mul.outputs[0], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    bump = nt.nodes.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.6; bump.inputs["Distance"].default_value = 0.02
    nt.links.new(n2.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    A.set_input(b, "Roughness", 0.92)
    return m


def asphalt_material():
    m = bpy.data.materials.new("path")
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    n = nt.nodes.new("ShaderNodeTexNoise"); n.inputs["Scale"].default_value = 180; n.inputs["Detail"].default_value = 10
    v = nt.nodes.new("ShaderNodeTexVoronoi"); v.inputs["Scale"].default_value = 90
    nt.links.new(tc.outputs["Object"], n.inputs["Vector"])
    nt.links.new(tc.outputs["Object"], v.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = srgb("#3a3a3c")
    ramp.color_ramp.elements[1].color = srgb("#76726f")
    nt.links.new(n.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    bump = nt.nodes.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.45; bump.inputs["Distance"].default_value = 0.004
    nt.links.new(v.outputs["Distance"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    A.set_input(b, "Roughness", 0.82)
    return m


def build_park(sc, seed=3):
    rnd = random.Random(seed)
    col = bpy.data.collections.new("park")
    sc.collection.children.link(col)
    # ground and a paved running path along X
    bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, 0))
    g = bpy.context.active_object
    g.data.materials.append(grass_material())
    RG.box(col, "Path", (140, 2.8, 0.04), Vector((0, 0, 0.02)), asphalt_material(), bevel=0.01)
    curb = RG.mat("curb", "#b9b3ab", rough=0.7)
    for s in (-1, 1):
        RG.box(col, "Curb", (140, 0.14, 0.08), Vector((0, s * 1.47, 0.04)), curb, bevel=0.01)

    # sources: the tree + grass clump (env-road), bushes and ground plants (env-vegetation)
    src = bpy.data.collections.new("park_src")
    sc.collection.children.link(src)
    _, road = RG.import_gltf("env-road", src)
    keep = {"Object_28", "Object_29", "Object_30", "mesh_3"}
    tree_parts = [o for o in road if o.type == "MESH" and o.name.split(".")[0] in keep - {"mesh_3"}]
    grass = next(o for o in road if o.type == "MESH" and o.name.startswith("mesh_3"))
    remove([o for o in road if o.type == "MESH" and o.name.split(".")[0] not in keep])
    tree_col = bpy.data.collections.new("TreeSrc")
    bpy.context.scene.collection.children.link(tree_col)
    for o in tree_parts:
        mw = o.matrix_world.copy()
        o.parent = None
        o.matrix_world = mw
        for c in list(o.users_collection):
            c.objects.unlink(o)
        tree_col.objects.link(o)
    # sources must be EXCLUDED from the view layer (not hidden): hidden collections
    # would hide their instances too
    bpy.context.view_layer.layer_collection.children[tree_col.name].exclude = True
    tree_col.instance_offset = (0.03, 0.01, 0.0)
    _, veg = RG.import_gltf("env-vegetation", src)
    bush_mats = ("europianspindle", "Atlas.056", "Atlas.065", "tundra", "fern")
    bushes = [o for o in veg if o.type == "MESH" and o.data.materials and o.data.materials[0]
              and o.data.materials[0].name.split(".")[0] in {m.split(".")[0] for m in bush_mats}
              and len(o.data.polygons) > 500]
    remove([o for o in veg if o.type == "MESH" and o not in bushes])
    bpy.context.view_layer.layer_collection.children[src.name].exclude = True

    def instance(obj, loc, rz, s):
        d = bpy.data.objects.new(obj.name + "_i", obj.data)
        col.objects.link(d)
        d.matrix_world = obj.matrix_world.copy()
        d.location = loc
        d.rotation_euler.z += rz
        d.scale = (d.scale.x * s, d.scale.y * s, d.scale.z * s)
        # drop to the ground: the source sits near z = 0 already
        return d

    def tree(loc, rz, s):
        e = bpy.data.objects.new("tree", None)
        e.instance_type = "COLLECTION"
        e.instance_collection = tree_col
        e.location = loc
        e.rotation_euler = (0, 0, rz)
        e.scale = (s, s, s)
        col.objects.link(e)

    for row, (y0, y1, smin, smax, step) in enumerate(((5.0, 7.5, 1.0, 1.35, 7.0), (11, 18, 1.2, 1.7, 6.0), (24, 40, 1.6, 2.2, 5.0))):
        for side in (-1, 1):
            x = -60 + rnd.uniform(0, step)
            while x < 60:
                tree(Vector((x, side * rnd.uniform(y0, y1), 0)), rnd.uniform(0, 6.28), rnd.uniform(smin, smax))
                x += step * rnd.uniform(0.75, 1.3)
    for i in range(220):                                   # grass clumps near the path
        x = rnd.uniform(-30, 30)
        y = rnd.choice((-1, 1)) * rnd.uniform(1.7, 9.0)
        instance(grass, Vector((x, y, 0)), rnd.uniform(0, 6.28), rnd.uniform(0.25, 0.5))
    for i in range(70):                                    # bushes along the verge
        b = rnd.choice(bushes)
        x = rnd.uniform(-30, 30)
        y = rnd.choice((-1, 1)) * rnd.uniform(2.3, 4.5)
        instance(b, Vector((x, y, 0)), rnd.uniform(0, 6.28), rnd.uniform(1.0, 1.8))
    return col


def morning_light(sc):
    nt = sc.world.node_tree
    bg = nt.nodes["Background"]
    sky = nt.nodes.new("ShaderNodeTexSky")
    sky.sky_type = "NISHITA"
    sky.sun_elevation = math.radians(30)
    sky.sun_rotation = math.radians(20)
    sky.air_density, sky.dust_density = 1.4, 3.0
    sky.sun_disc = False                                   # the sun lamp is the sun; no double light
    nt.links.new(sky.outputs[0], bg.inputs[0])
    bg.inputs[1].default_value = 0.16                      # Nishita is physically bright outdoors
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    sun.data.energy = 3.6
    sun.data.angle = math.radians(1.0)
    sun.data.color = (1.0, 0.86, 0.68)
    d = Vector((0.35, -0.70, -0.60)).normalized()          # warm morning key from the camera side
    sun.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    sc.collection.objects.link(sun)
    fill = bpy.data.objects.new("fill", bpy.data.lights.new("fill", "AREA"))
    fill.data.energy, fill.data.size, fill.data.color = 350, 8, (0.85, 0.9, 1.0)
    fill.location = (0, 9, 4)
    fill.rotation_euler = (Vector((0, 0, 1)) - fill.location).to_track_quat("-Z", "Y").to_euler()
    fill.visible_glossy = False
    sc.collection.objects.link(fill)


def people_col(sc, name):
    col = bpy.data.collections.new(name)
    sc.collection.children.link(col)
    return col


# ------------------------------------------------------------------ scenes
def shot_park_run(sc):
    build_park(sc)
    morning_light(sc)
    ch = CH.Character(people_col(sc, "runner"), "an-jogging", height=JOG_HEIGHT)
    act = ch.action
    spd = ch.ground_speed(act)
    ch.use_action(act, frames=N + 30)
    ch.place((-3.2, -0.35, 0.04), yaw_deg=90)              # runs toward +X, left arm (+Y) to camera
    pod_on(ch, "live")
    walk_forward(ch, spd)
    cam = RG.camera(sc, 55, fstop=2.2)
    def pos(t, e):
        return Vector((-3.2 + spd * (t * (N - 1)) + 2.4 - 1.2 * e, 3.1 - 0.4 * e, 1.25 + 0.05 * e))
    def look(t, e):
        return Vector((-3.2 + spd * (t * (N - 1)) + 0.1, -0.2, 1.28))
    RG.keyframe_path(cam, N, pos, look, lambda t, e, tgt: (tgt - cam.location).length)
    return N


def gym_base(sc, haze=0.003):
    RG.build_gym(sc)
    RG.lighting(sc, haze=haze)
    RG.build_bench(sc)


def treadmill_with_runner(sc, scenario, action_from=None):
    col = people_col(sc, "treadmill")
    tr, tobjs = RG.import_gltf("treadmill", col)
    RG.place(tr, tobjs, scale=0.001, at=RG.RUNNER_AT)
    lo, hi = RG.bounds(tobjs)
    tops = []
    for o in tobjs:
        if o.type == "MESH":
            mw = o.matrix_world
            tops += [(mw @ v.co) for v in o.data.vertices if (mw @ v.co).z > lo.z + 0.8 * (hi.z - lo.z)]
    if tops and sum(p.y for p in tops) / len(tops) > (lo.y + hi.y) / 2:
        RG.place(tr, tobjs, scale=0.001, at=RG.RUNNER_AT, rot_z=math.pi)
    lo, hi = RG.bounds(tobjs)
    belt = lo.z + 0.21
    ch = CH.Character(people_col(sc, "runner"), "an-jogging", height=JOG_HEIGHT)
    ch.use_action(ch.action, frames=N + 30)
    ch.place((RG.RUNNER_AT.x, RG.RUNNER_AT.y + 0.2, belt), yaw_deg=0)
    pod_on(ch, scenario)
    return ch


def shot_treadmill(sc):
    gym_base(sc)
    ch = treadmill_with_runner(sc, "run")
    cam = RG.camera(sc, 35, fstop=2.4)
    centre = Vector((RG.RUNNER_AT.x, RG.RUNNER_AT.y + 0.2, 1.40))
    def pos(t, e):
        a = math.radians(48 + 55 * e)
        return centre + Vector((math.sin(a) * 2.4, -math.cos(a) * 2.4, 0.22 - 0.08 * e))
    RG.keyframe_path(cam, N, pos, lambda t, e: centre + Vector((0.12, 0, 0.0)),
                     lambda t, e, tgt: (tgt - cam.location).length)
    return N


def jog_scale(sc):
    """The push-up and jogging files are the same person: reuse the jogger's scale."""
    tmp = people_col(sc, "tmp")
    j = CH.Character(tmp, "an-jogging", height=JOG_HEIGHT)
    k = j.root.scale.x
    remove(j.objs + [j.root])
    bpy.data.collections.remove(tmp)
    return k


def shot_pushups(sc):
    gym_base(sc)
    k = jog_scale(sc)
    ch = CH.Character(people_col(sc, "athlete"), "an-pushup")
    ch.root.scale = (k, k, k)
    bpy.context.view_layer.update()
    ch.use_action(ch.action, frames=N + 30)
    at = RG.BENCH_AT + Vector((0.4, -1.55, 0))
    RG.box(bpy.context.scene.collection, "Mat", (0.75, 2.0, 0.012), at + Vector((0, 0, 0.006)),
           RG.mat("mat", "#1d2530", rough=0.8), bevel=0.004)
    ch.place((at.x, at.y, 0.012), yaw_deg=0)
    pod_on(ch, "live")
    cam = RG.camera(sc, 40, fstop=2.8)
    bpy.context.scene.frame_set(1)
    head, sh = ch.bone_world("head"), ch.bone_world("leftarm")
    look = head.lerp(sh, 0.55)
    side = (sh - head).normalized()
    RG.keyframe_path(cam, N,
                     lambda t, e: look + Vector((1.25 - 0.25 * e, -1.05 + 0.35 * e, 0.55 - 0.1 * e)),
                     lambda t, e: look + Vector((0, 0, -0.05)),
                     lambda t, e, tgt: (tgt - cam.location).length)
    return N


def phone_in_hand(ch, frame):
    """The phone-call motion has no phone: put the Sketchfab phone in the right hand,
    screen to the cheek, parented to the hand bone."""
    sc = bpy.context.scene
    sc.frame_set(frame)
    bpy.context.view_layer.update()
    col = people_col(sc, "phone")
    root, objs = RG.import_gltf("phone", col)
    lo, hi = RG.bounds(objs)
    ctr = (lo + hi) / 2
    h = ch.bone_world("righthand")
    tip = ch.bone_world("righthandmiddle1") if "righthandmiddle1" in ch.bones else h + Vector((0, 0, 0.08))
    head = ch.bone_world("head")
    up = (tip - h).normalized()
    face = head - h
    face = (face - up * face.dot(up)).normalized()
    x = face.cross(up)
    holder = bpy.data.objects.new("PhoneHolder", None)
    col.objects.link(holder)
    from mathutils import Matrix
    holder.matrix_world = Matrix.Translation(h.lerp(tip, 0.55) + face * 0.012) @ Matrix((x, face, up)).transposed().to_4x4()
    root.parent = holder
    root.matrix_parent_inverse.identity()
    root.location = -ctr                                   # model origin -> its centre sits in the palm
    bone = ch.arm.pose.bones[ch.bones["righthand"]]
    mw = holder.matrix_world.copy()
    holder.parent = ch.arm
    holder.parent_type = "BONE"
    holder.parent_bone = bone.name
    bpy.context.view_layer.update()
    holder.matrix_world = mw


def shot_coach(sc):
    gym_base(sc)
    treadmill_with_runner(sc, "alert")
    coach = CH.Character(people_col(sc, "coach"), "an-phone", height=1.80)
    coach.use_action(coach.action, frames=N + 30, offset=180)   # mid-call: phone to the ear
    at = Vector((RG.RUNNER_AT.x + 0.55, RG.RUNNER_AT.y - 2.6, 0))
    coach.place((at.x, at.y, 0), yaw_deg=8)
    phone_in_hand(coach, frame=60)
    cam = RG.camera(sc, 70, fstop=2.0)
    head = Vector((at.x, at.y, 1.55))
    RG.keyframe_path(cam, N,
                     lambda t, e: head + Vector((0.95 - 0.25 * e, -2.3 + 0.3 * e, 0.02)),
                     lambda t, e: head + Vector((0.42, 0, -0.12)),
                     lambda t, e, tgt: (tgt - cam.location).length)
    return N


def shot_recovery(sc):
    gym_base(sc, haze=0.0)
    ch = CH.Character(people_col(sc, "runner"), "an-jogging", height=JOG_HEIGHT)
    src = CH.Character(people_col(sc, "sit_src"), "an-sitting")
    sit = ch.retarget(src.action)
    remove(src.objs + [src.root])
    ch.use_action(sit, frames=N + 30)
    bpy.context.scene.frame_set(1)
    top_z = 0.45
    seat = RG.BENCH_AT + Vector((0.42, 0.0, top_z))
    ch.place((seat.x, seat.y - 0.45, 0), yaw_deg=0)
    # slide so the hips sit over the bench
    hip = ch.bone_world("hips")
    ch.root.location += Vector((seat.x - hip.x, seat.y - hip.y + 0.05, 0))
    bpy.context.view_layer.update()
    pod_on(ch, "ready")
    cam = RG.camera(sc, 50, fstop=2.2)
    sh = ch.bone_world("leftarm")
    RG.keyframe_path(cam, N,
                     lambda t, e: sh + Vector((1.35 - 0.25 * e, -2.0 + 0.3 * e, 0.10)),
                     lambda t, e: sh + Vector((-0.18, 0, 0.02)),
                     lambda t, e, tgt: (tgt - cam.location).length)
    return N


def shot_walk(sc):
    build_park(sc, seed=11)
    morning_light(sc)
    ch = CH.Character(people_col(sc, "walker"), "an-nathan-walk", height=1.80)
    act = ch.action
    travel = hips_travel(ch, act)
    ch.use_action(act, frames=N + 30)
    ch.place((6.0, 0.3, 0.04), yaw_deg=-90)               # walks toward -X, toward the camera
    pod_on(ch, "walk")
    if travel < 0.25:                                      # in-place cycle: move the root
        walk_forward(ch, ch.ground_speed(act), axis=Vector((-1, 0, 0)))
        ch.use_action(act, frames=N + 30)
    by = CH.Character(people_col(sc, "bystander"), "an-sophia", height=1.66)
    by.use_action(by.action, frames=N + 30, offset=60)
    by.place((0.5, 2.1, 0), yaw_deg=150)
    cam = RG.camera(sc, 60, fstop=2.4)
    RG.keyframe_path(cam, N,
                     lambda t, e: Vector((0.6 - 0.8 * e, -2.4 + 0.2 * e, 1.45)),
                     lambda t, e: ch.root.matrix_world.translation * 0 + Vector((5.0 - 3.2 * e, 0.2, 1.3)),
                     lambda t, e, tgt: (tgt - cam.location).length)
    return N


SHOTS = {"park_run": shot_park_run, "treadmill": shot_treadmill, "pushups": shot_pushups,
         "coach": shot_coach, "recovery": shot_recovery, "walk": shot_walk}


def render(name):
    sc = setup()
    n = SHOTS[name](sc)
    d = os.path.join(OUT, name)
    os.makedirs(d, exist_ok=True)
    def go():
        if TEST:
            sc.frame_set(int(TEST))
            sc.render.filepath = os.path.join(OUT, "test_%s.jpg" % name)
            bpy.ops.render.render(write_still=True)
        else:
            sc.render.filepath = os.path.join(d, "f_")
            sc.frame_start = int(START or 1) if not os.listdir(d) else max(int(START or 1), len(os.listdir(d)) + 1)
            sc.frame_end = int(END or n)
            bpy.ops.render.render(animation=True)
    try:
        go()
    except RuntimeError as e:                              # the GPU is shared: fall back to the CPU
        if "GPU memory" not in str(e):
            raise
        print("GPU out of memory -> rendering %s on the CPU" % name)
        sc.cycles.device = "CPU"
        go()
    print("USECASE DONE", name, n)


if __name__ == "__main__":
    for s in (SHOTS if SHOT == "all" else SHOT.split(",")):
        render(s)
