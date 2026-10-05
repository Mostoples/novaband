# ============================================================
# 20 s "how to use" tutorial: five 4-second 3D shots of the detailed Nova.
#   python blender/tutorial.py [--samples 20]     # driver: all shots, resumes after crashes
#   blender -b -P blender/tutorial.py -- --job s2 [--test 50]
# Output: build/tut/<shot>/f_####.png (transparent, 960x960, 96 frames @ 24 fps)
#   s1 switch on   - close-up: the band screen powers up
#   s2 wear it     - the band flies onto the upper arm and snugs down
#   s3 pair        - Bluetooth rings pulse from the band, Nova waves
#   s4 run         - run cycle, the band shows the RUN page
#   s5 stay safe   - heart-rate alert: red pulses, Nova's stop gesture
# tools/make-tutorial.py adds the steps, phone, captions and voice.
# ============================================================
import math
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import nova_scene as NS  # noqa: E402

ROOT = NS.ROOT
N = 96
SHOTS = ["s1", "s2", "s3", "s4", "s5"]
SCREENS = {"s1": ("ready", 1), "s2": ("live", 1), "s3": ("live", 97), "s4": ("run", 1), "s5": ("alert", 40)}
OUT = lambda s: os.path.join(ROOT, "build", "tut", s)
SCR = lambda s: os.path.join(ROOT, "build", "tut_screen", s)

if NS.bpy is None:
    for s, (scen, first) in SCREENS.items():
        os.makedirs(SCR(s), exist_ok=True)
        for i in range(N):
            src = os.path.join(ROOT, "build", "sim", scen, "f_%04d.png" % min(first + i, 220))
            shutil.copyfile(src, os.path.join(SCR(s), "f_%04d.png" % (i + 1)))
    argv = sys.argv[1:]
    only = argv[argv.index("--only") + 1].split(",") if "--only" in argv else SHOTS
    rest = [a for i, a in enumerate(argv) if a != "--only" and (i == 0 or argv[i - 1] != "--only")]
    NS.drive(os.path.abspath(__file__), only, [OUT(s) for s in only], extra=rest)
    sys.exit(0)

import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
arg = lambda n, d=None: ARGS[ARGS.index(n) + 1] if n in ARGS else d
JOB = arg("--job", "s1")
MA, M = NS.MA, NS.M
TAU = 2 * math.pi
rad = math.radians


def sm(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def band_centre():
    S, E = Vector(M.J["shoulder.L"]), Vector(M.J["elbow.L"])
    P = S.lerp(E, 0.52)
    axis = (E - S).normalized()
    o = (Vector((1, -0.8, 0)) - axis * Vector((1, -0.8, 0)).dot(axis)).normalized()
    return P, o


BAND_PARTS = ("Armband", "BandModule", "BandGlass", "BandScreen", "BandN", "BandLed")


def band_pivot():
    """An empty at the band centre (child of the shoulder) that the band parts ride on."""
    P, _ = band_centre()
    frame = bpy.data.objects.new("BandPivot_frame", None)
    M.COLL.objects.link(frame)
    frame.parent = M.EMP["shoulder.L"]
    bpy.context.view_layer.update()
    frame.matrix_world = Matrix.Translation(P)
    ctl = bpy.data.objects.new("BandPivot", None)
    M.COLL.objects.link(ctl)
    ctl.parent = frame
    bpy.context.view_layer.update()
    for n in BAND_PARTS:
        o = bpy.data.objects.get(n)
        if not o:
            continue
        mw = o.matrix_world.copy()
        o.parent = ctl
        o.matrix_parent_inverse = ctl.matrix_world.inverted() @ mw @ o.matrix_basis.inverted()
    return ctl


def screen_strength(keys):
    mat = bpy.data.materials.get("M_BandScreen")
    em = next(n for n in mat.node_tree.nodes if n.type == "EMISSION")
    for f, v in keys:
        em.inputs["Strength"].default_value = v
        em.inputs["Strength"].keyframe_insert("default_value", frame=f)


def pulse_rings(colour, strength, period, count=3):
    """Glowing rings that expand from the band and fade (Bluetooth / alert pulses)."""
    P, o = band_centre()
    mat = bpy.data.materials.new("M_Pulse")
    mat.use_nodes = True
    nt = mat.node_tree
    for nd in list(nt.nodes):
        if nd.type == "BSDF_PRINCIPLED":
            nt.nodes.remove(nd)
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = colour
    em.inputs["Strength"].default_value = strength
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], nt.nodes["Material Output"].inputs["Surface"])
    mat.blend_method = "BLEND"
    rings = []
    for k in range(count):
        bpy.ops.mesh.primitive_torus_add(major_radius=0.07, minor_radius=0.0016, major_segments=64,
                                         minor_segments=8, location=P + o * 0.11)
        r = bpy.context.active_object
        for c in list(r.users_collection):
            c.objects.unlink(r)
        M.COLL.objects.link(r)
        r.rotation_euler = o.to_track_quat("Z", "Y").to_euler()
        m = mat.copy()
        r.data.materials.append(m)
        fac = m.node_tree.nodes["Mix Shader"].inputs["Fac"]
        mw = r.matrix_world.copy()
        r.parent = M.EMP["shoulder.L"]
        r.matrix_parent_inverse = M.EMP["shoulder.L"].matrix_world.inverted()
        r.matrix_world = mw
        for f in range(1, N + 1):
            u = ((f - 1) / period + k / count) % 1.0
            s = 0.7 + (4.2 if colour[2] > 0.5 else 3.0) * u
            r.scale = (s, s, s)
            r.keyframe_insert("scale", frame=f)
            fac.default_value = (1 - u) ** 1.5
            fac.keyframe_insert("default_value", frame=f)
        rings.append(r)
    return rings


def cyc(fn, period):
    return lambda f: fn(((f - 1) % period) / period)


def main():
    pose = "stand"
    expr = {"s4": "fierce", "s5": "fierce", "s3": "happy"}.get(JOB, "smirk")
    sc, lids = NS.build_nova(expr, pose, screen=os.path.join(SCR(JOB), "f_0001.png"), screen_frames=N)
    P, o = band_centre()
    pv = None
    if JOB == "s1":
        posef = cyc(MA.idle, 96)
        screen_strength([(1, 0.0), (20, 0.0), (30, 2.6), (34, 2.2)])
        target, hh, az, el, dof = P + o * 0.03 + Vector((0.02, -0.02, 0)), 0.16, 50, 8, 2.8
    elif JOB == "s2":
        posef = cyc(MA.idle, 96)
        pv = band_pivot()
        start = Vector((0.42, -0.30, 0.10))
        for f in range(1, N + 1):
            u = sm((f - 8) / 46)
            pv.location = start * (1 - u)
            s = 1.0 + 0.55 * (1 - u) - 0.06 * math.sin(math.pi * sm((f - 54) / 14)) * (f > 54)
            pv.scale = (s, s, s)
            pv.rotation_euler = (0, 0, rad(-70 * (1 - u)))
            pv.keyframe_insert("location", frame=f)
            pv.keyframe_insert("scale", frame=f)
            pv.keyframe_insert("rotation_euler", frame=f)
        target, hh, az, el, dof = Vector((0.16, 0, 1.32)), 0.6, -34, 6, None
    elif JOB == "s3":
        posef = cyc(MA.wave, 48)
        pulse_rings((0.37, 0.89, 1.0, 1.0), 6.0, 36)
        target, hh, az, el, dof = Vector((0.0, 0, 1.08)), 1.18, -16, 4, None
    elif JOB == "s4":
        posef = cyc(MA.run, 24)
        target, hh, az, el, dof = Vector((0.0, 0, 1.04)), 1.16, 38, 5, None
    else:
        posef = cyc(MA.alert, 48)
        pulse_rings((1.0, 0.18, 0.25, 1.0), 9.0, 24)
        target, hh, az, el, dof = Vector((0.1, 0, 1.28)), 0.62, -22, 5, None
    for f in range(1, N + 1):
        NS.key_pose(f, posef(f), lids)
    NS.linear_keys()
    M.studio(target, hh, az, el, 70, (960, 960), dof=dof)
    # slow push-in keeps every shot alive
    cam = sc.camera
    c0 = cam.location.copy()
    for f in (1, N):
        cam.location = target + (c0 - target) * (1.0 if f == 1 else 0.93)
        cam.keyframe_insert("location", frame=f)
    sc.cycles.samples = int(arg("--samples", "20"))
    sc.cycles.use_adaptive_sampling = True
    sc.render.fps = 24
    sc.frame_start, sc.frame_end = 1, N
    test = arg("--test")
    NS.render_frames(sc, OUT(JOB), N, int(test) if test else None)


main()
