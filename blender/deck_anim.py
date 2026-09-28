# ============================================================
# Nova-Band deck — animated assets (Blender CLI, Cycles GPU)
#
#   blender -b -P blender/deck_anim.py
#   blender -b -P blender/deck_anim.py -- --only heart,gyroscope --frames 12 --samples 16
#   blender -b -P blender/deck_anim.py -- --list
#
# Renders seamless RGBA loops to build/deck/anim/<name>/f_####.png:
#   * icons      — the web icon library, each given its own motion
#                  (a heart that beats, gyro rings that spin, a bell that swings…)
#   * ornaments  — floating capsules and a glossy ring
#   * corners    — side-corner decorations: orbiting rings, a live dotted wave
#   * device     — the band turning on a turntable, PPG LEDs beating
#
# tools/pack-gifs.py mattes the loops onto the deck's flat neumorphic
# background and writes the animated GIFs PowerPoint plays natively.
#
# Every motion is a periodic function of t in [0, 1): the last frame
# flows straight into the first, so the GIFs loop without a hitch.
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
OUT = os.path.join(PROJECT, "build", "deck", "anim")
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def arg(name, default=None):
    return ARGS[ARGS.index(name) + 1] if name in ARGS else default


ONLY = set(filter(None, (arg("--only", "") or "").split(",")))
SAMPLES = int(arg("--samples", 40))
FRAME_CAP = int(arg("--frames", 0))
FPS = 25

spec = importlib.util.spec_from_file_location("nb_assets", os.path.join(SCRIPT_DIR, "novaband_assets.py"))
A = importlib.util.module_from_spec(spec)
spec.loader.exec_module(A)

TAU = 2 * math.pi


# ---------------------------------------------------------------- motion kit
def ob(name):
    o = bpy.data.objects.get(name)
    if o is None:
        for x in bpy.data.objects:
            if x.name.split(".")[0] == name:
                return x
    return o


def obs(prefix):
    return [x for x in bpy.data.objects if x.name.split(".")[0].startswith(prefix)]


def key(target, path, fn, n, index=None):
    """Sample a periodic function once per frame, plus frame n+1 (== frame 1)."""
    for f in range(1, n + 2):
        t = ((f - 1) % n) / n
        v = fn(t)
        if index is None:
            setattr(target, path, v)
            target.keyframe_insert(path, frame=f)
        else:
            getattr(target, path)[index] = v
            target.keyframe_insert(path, index=index, frame=f)
    ad = target.animation_data
    if ad and ad.action:
        for fc in ad.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"


def key_socket(mat_name, socket, fn, n):
    m = bpy.data.materials.get(mat_name)
    if not m:
        return
    s = m.node_tree.nodes["Principled BSDF"].inputs.get(socket)
    if s is None:
        return
    for f in range(1, n + 2):
        t = ((f - 1) % n) / n
        s.default_value = fn(t)
        s.keyframe_insert("default_value", frame=f)


def beat(t, beats=2):
    """Double-thump heartbeat, same curve as the website and the showreel."""
    p = (t * beats) % 1.0
    return math.exp(-40 * p * p) + 0.45 * math.exp(-60 * (p - 0.22) ** 2)


def hinge(names, loc):
    """Re-parent parts under a new empty at loc (object space) so they can swing."""
    pivot = ob("pivot")
    e = bpy.data.objects.new("hinge", None)
    bpy.context.scene.collection.objects.link(e)
    e.parent = pivot
    e.location = loc
    for n in names:
        o = ob(n)
        if o is None:
            continue
        o.parent = e
        o.matrix_parent_inverse = Matrix.Translation(-Vector(loc))
    return e


def rock(ctx, deg=14, bob=0.035):
    """Default life: a slow sway and a gentle float."""
    h, n = ctx["holder"], ctx["n"]
    base_z = h.location.z
    key(h, "rotation_euler", lambda t: math.radians(deg) * math.sin(TAU * t), n, index=2)
    key(h, "location", lambda t: base_z + bob * math.sin(TAU * t), n, index=2)


def spin(obj, axis, n, turns=1.0, phase=0.0):
    base = obj.rotation_euler[axis]
    key(obj, "rotation_euler", lambda t: base + TAU * turns * t + phase, n, index=axis)


def pulse_scale(obj, n, amp=0.12, phase=0.0, fn=None):
    s0 = tuple(obj.scale)
    for i in range(3):
        key(obj, "scale", (lambda i: lambda t: s0[i] * (1 + amp * (fn(t) if fn else
            math.sin(TAU * (t + phase)))))(i), n, index=i)


# ---------------------------------------------------------------- icon motions
def m_heart(ctx):
    h, n = ctx["holder"], ctx["n"]
    s = h.scale[0]
    for i in range(3):
        key(h, "scale", (lambda i: lambda t: s * (1 + 0.09 * beat(t)))(i), n, index=i)
    key_socket("white", "Emission Strength", lambda t: 1.5 * beat(t), n)


def m_ripple(prefix, amp=0.16):
    def f(ctx):
        n = ctx["n"]
        arcs = sorted(obs(prefix), key=lambda o: o.name)
        for k, a in enumerate(arcs):
            s0 = tuple(a.scale)
            ph = k / max(len(arcs), 1)
            for i in range(3):
                key(a, "scale", (lambda i, ph: lambda t: s0[i] * (0.92 + amp * (0.5 + 0.5 *
                    math.sin(TAU * (t - ph)))))(i, ph), n, index=i)
        rock(ctx, deg=8, bob=0.02)
    return f


def m_led(ctx):
    m_ripple("wave")(ctx)
    key_socket("led", "Emission Strength", lambda t: 4 + 10 * beat(t), ctx["n"])


def m_gyro(ctx):
    n = ctx["n"]
    spin(ob("r1"), 1, n, 1)
    spin(ob("r2"), 0, n, -1)
    spin(ob("r3"), 2, n, 2)
    rock(ctx, deg=0, bob=0.03)


def m_compass(ctx):
    n = ctx["n"]
    for name in ("needleN", "needleS"):
        o = ob(name)
        z0 = o.rotation_euler[2]
        key(o, "rotation_euler", lambda t, z0=z0: z0 + math.radians(38) * math.sin(TAU * t)
            + math.radians(10) * math.sin(2 * TAU * t), n, index=2)
    rock(ctx, deg=6, bob=0.015)


def m_bell(ctx):
    n = ctx["n"]
    e = hinge(["bell", "clapper", "loop"], (0, 0, 1.1))
    key(e, "rotation_euler", lambda t: math.radians(16) * math.sin(TAU * t) *
        (0.6 + 0.4 * math.cos(TAU * t * 2)), n, index=1)
    pulse_scale(ob("badge"), n, amp=0.25, fn=lambda t: beat(t, 2))


def m_medal(ctx):
    n = ctx["n"]
    parts = [o.name for o in bpy.data.objects if o.name.split(".")[0] in ("disc", "inner", "A")]
    e = hinge(parts, (0, 0, 0.9))
    key(e, "rotation_euler", lambda t: math.radians(12) * math.sin(TAU * t), n, index=1)
    key(e, "rotation_euler", lambda t: math.radians(18) * math.sin(TAU * t + 1.2), n, index=2)


def m_turn(deg=None):
    """A full turntable turn (deg=None) or a wide sway."""
    def f(ctx):
        h, n = ctx["holder"], ctx["n"]
        if deg is None:
            key(h, "rotation_euler", lambda t: TAU * t, n, index=2)
        else:
            rock(ctx, deg=deg, bob=0.03)
    return f


def m_gauge(ctx):
    n = ctx["n"]
    o = ob("needle")
    z0 = o.rotation_euler[2]
    key(o, "rotation_euler", lambda t: z0 + math.radians(55) * (0.5 - 0.5 * math.cos(TAU * t)), n, index=2)
    rock(ctx, deg=6, bob=0.015)


def m_stopwatch(ctx):
    spin(ob("hand"), 1, ctx["n"], -1)
    rock(ctx, deg=8, bob=0.02)


def m_spring(ctx):
    n = ctx["n"]
    k = lambda t: 0.82 + 0.18 * (0.5 + 0.5 * math.cos(TAU * t))
    coil, top = ob("coil"), ob("capT")
    key(coil, "scale", lambda t: k(t), n, index=2)
    key(coil, "location", lambda t: 0.9 * (k(t) - 1), n, index=2)
    key(top, "location", lambda t: 1.8 * k(t) - 0.8, n, index=2)


def m_pin(ctx):
    n = ctx["n"]
    hop = lambda t: abs(math.sin(math.pi * t))
    for name in ("pin", "hole"):
        o = ob(name)
        z0 = o.location.z
        key(o, "location", lambda t, z0=z0: z0 + 0.28 * hop(t), n, index=2)
    spot = ob("spot")
    s0 = tuple(spot.scale)
    for i in (0, 1):
        key(spot, "scale", (lambda i: lambda t: s0[i] * (1 - 0.25 * hop(t)))(i), n, index=i)


def m_bars(ctx):
    n = ctx["n"]
    heights = (0.55, 0.95, 0.7, 1.35)
    for o in obs("trend"):
        o.hide_render = True
    for o in obs("pt"):
        o.hide_render = True
    for i, h in enumerate(heights):
        b = ob("b%d" % i)
        k = (lambda i: lambda t: 0.55 + 0.45 * (0.5 - 0.5 * math.cos(TAU * (t - i * 0.12))))(i)
        key(b, "scale", lambda t, k=k: k(t), n, index=2)
        key(b, "location", lambda t, k=k, h=h: 0.06 + h * k(t) / 2, n, index=2)


def m_blood(ctx):
    n = ctx["n"]
    for k, o in enumerate(sorted(obs("cell"), key=lambda o: o.name)):
        spin(o, 2, n, 1 if k % 2 == 0 else -1)
        z0 = o.location.z
        key(o, "location", lambda t, z0=z0, k=k: z0 + 0.06 * math.sin(TAU * t + k * 2.1), n, index=2)


def m_flame(ctx):
    n = ctx["n"]
    for name, amp in (("outer", 0.05), ("inner", 0.12)):
        o = ob(name)
        s0 = tuple(o.scale)
        key(o, "scale", lambda t, s0=s0, amp=amp: s0[0] * (1 + amp * math.sin(TAU * 2 * t)), n, index=0)
        # the outline was drawn in XY then stood up, so its height is local Y
        key(o, "scale", lambda t, s0=s0, amp=amp: s0[1] * (1 + amp * math.sin(TAU * 3 * t + 1)), n, index=1)
    rock(ctx, deg=5, bob=0.015)


def m_bulb(ctx):
    n = ctx["n"]
    key_socket("warm", "Emission Strength", lambda t: 2 + 6 * (0.5 + 0.5 * math.sin(TAU * t)), n)
    key_socket("glowW", "Emission Strength", lambda t: 1 + 3 * (0.5 + 0.5 * math.sin(TAU * t)), n)
    rock(ctx, deg=8, bob=0.025)


def m_cloud(ctx):
    n = ctx["n"]
    for o in obs("sync"):
        z0 = o.location.z
        key(o, "location", lambda t, z0=z0: z0 + 0.1 * math.sin(TAU * t), n, index=2)
    rock(ctx, deg=5, bob=0.03)


def m_coins(ctx):
    n = ctx["n"]
    e = hinge(["up", "rp"], tuple(ob("up").location))   # spin coin + "Rp" as one piece
    key(e, "rotation_euler", lambda t: TAU * t, n, index=2)
    rock(ctx, deg=6, bob=0.02)


def m_ai(ctx):
    n = ctx["n"]
    h = ctx["holder"]
    key(h, "rotation_euler", lambda t: TAU * t, n, index=2)
    pulse_scale(ob("core"), n, amp=0.14, fn=lambda t: beat(t, 2))


def m_warning(ctx):
    h, n = ctx["holder"], ctx["n"]
    s = h.scale[0]
    for i in range(3):
        key(h, "scale", (lambda i: lambda t: s * (1 + 0.06 * beat(t, 1)))(i), n, index=i)
    key(h, "rotation_euler", lambda t: math.radians(10) * math.sin(TAU * t), n, index=2)


def m_moon(ctx):
    n = ctx["n"]
    for k, o in enumerate(obs("star")):
        pulse_scale(o, n, amp=0.35, phase=k / 3)
    rock(ctx, deg=10, bob=0.03)


ICON_MOTION = {
    "heart": m_heart, "led-sensor": m_led, "wifi-iot": m_ripple("arc"),
    "photodetector": m_ripple("sig"), "gyroscope": m_gyro, "magnetometer": m_compass,
    "bell": m_bell, "medal": m_medal, "gauge": m_gauge, "stopwatch": m_stopwatch,
    "spring-tendon": m_spring, "map-pin": m_pin, "bar-chart": m_bars, "blood-cells": m_blood,
    "flame": m_flame, "lightbulb": m_bulb, "cloud": m_cloud, "coins": m_coins,
    "ai-network": m_ai, "warning": m_warning, "moon": m_moon,
    "globe": m_turn(), "target-tiers": m_turn(), "shield": m_turn(22),
    "chip": m_turn(16), "microcontroller": m_turn(16), "smartphone": m_turn(18),
    "accelerometer": m_turn(20), "calendar": m_turn(14), "clipboard": m_turn(14),
    "magnifier": m_turn(16), "school": m_turn(14), "user": m_turn(12), "gear": m_turn(),
    "footsteps": m_turn(10), "chain-link": m_turn(), "bluetooth": m_turn(18), "battery": m_turn(14),
}

# ---------------------------------------------------------------- non-icon loops
def b_device(c):
    A.build_device(c).rotation_euler = (math.radians(72), 0, 0)


def m_device(ctx):
    h, n = ctx["holder"], ctx["n"]
    key(h, "rotation_euler", lambda t: TAU * t, n, index=2)
    key_socket("NB_LedGreen", "Emission Strength", lambda t: 3 + 10 * beat(t, 3), n)
    key_socket("NB_LedIR", "Emission Strength", lambda t: 1.5 + 4 * beat(t, 3), n)


def b_pills(c):
    A.ASSETS["pills"]["fn"](c)


def m_pills(ctx):
    n = ctx["n"]
    things = obs("pill") + obs("ball") + obs("ring")
    for k, o in enumerate(things):
        z0 = o.location.z
        key(o, "location", lambda t, z0=z0, k=k: z0 + 0.12 * math.sin(TAU * t + k * 1.3), n, index=2)
        r0 = o.rotation_euler[2]
        key(o, "rotation_euler", lambda t, r0=r0, k=k: r0 + math.radians(25) * math.sin(TAU * t + k),
            n, index=2)


def b_ring(c):
    A.torus(c, "ring", 0.8, 0.26, rot=(math.radians(70), 0, math.radians(20)), material=A.M("wine"))
    A.torus(c, "ring2", 0.42, 0.1, loc=(0.9, -0.2, 0.6), rot=(math.radians(20), math.radians(50), 0),
            material=A.M("cream"))


def m_ring(ctx):
    n = ctx["n"]
    spin(ob("ring"), 2, n, 1)
    spin(ob("ring2"), 0, n, -1)
    rock(ctx, deg=0, bob=0.04)


def b_corner_rings(c):
    """Concentric broken rings lying on the slide surface — seen from above."""
    rings = [(1.6, 0.05, 20, 250, "wine"), (1.25, 0.08, 120, 330, "rose"),
             (0.95, 0.05, -40, 190, "wineM"), (0.65, 0.10, 60, 300, "cream"),
             (2.0, 0.035, 200, 330, "rose")]
    for i, (R, r, a0, a1, m) in enumerate(rings):
        A.arc_tube(c, "cr%d" % i, R, r, math.radians(a0), math.radians(a1),
                   loc=(0, 0, r + 0.02), material=A.M(m))
    A.sphere(c, "hub", 0.28, loc=(0, 0, 0.28), material=A.M("wine"))
    for k in range(5):
        a = TAU * k / 5
        A.sphere(c, "sat%d" % k, 0.07 + 0.03 * (k % 2), loc=(1.42 * math.cos(a), 1.42 * math.sin(a), 0.1),
                 material=A.M("wine") if k % 2 else A.M("cream"))


def m_corner_rings(ctx):
    n = ctx["n"]
    for i in range(5):
        o = ob("cr%d" % i)
        spin(o, 2, n, turns=(1 if i % 2 == 0 else -1))
    sats = [ob("sat%d" % k) for k in range(5)]
    for k, s in enumerate(sats):
        a0 = TAU * k / 5
        key(s, "location", lambda t, a0=a0: 1.42 * math.cos(a0 + TAU * t), n, index=0)
        key(s, "location", lambda t, a0=a0: 1.42 * math.sin(a0 + TAU * t), n, index=1)
    pulse_scale(ob("hub"), n, amp=0.1, fn=lambda t: beat(t, 2))


WAVE = {"host": None, "grid": None}


def b_corner_wave(c):
    """The deck's dotted wave as live geometry; a frame handler moves every dot."""
    NX, NY = 64, 28
    bm = bmesh.new()
    grid = []
    for i in range(NX):
        for j in range(NY):
            x = (i / (NX - 1) - 0.5) * 4.2
            y = (j / (NY - 1) - 0.5) * 1.9
            bm.verts.new((x, y, 0.0))
            grid.append((x, y))
    host = A.mesh_obj("wavehost", bm, c, A.M("rose"))
    dot = A.sphere(c, "wdot", 0.028, material=A.mat("dots", A.srgb("#b88c8c"), rough=0.5))
    dot.parent = host
    host.instance_type = "VERTS"
    WAVE["host"], WAVE["grid"] = host, grid
    set_wave(0.0)


def set_wave(t):
    host = WAVE["host"]
    if host is None:
        return
    me = host.data
    for v, (x, y) in zip(me.vertices, WAVE["grid"]):
        v.co.z = 0.32 + 0.26 * math.sin(x * 1.7 + TAU * t) * math.cos(y * 1.6 - TAU * t) + \
            0.12 * math.sin(x * 3.1 - y * 2.0 + TAU * 2 * t)
    me.update()


def m_corner_wave(ctx):
    n = ctx["n"]

    def handler(scene, *_):
        set_wave(((scene.frame_current - 1) % n) / n)
    bpy.app.handlers.frame_change_pre.clear()
    bpy.app.handlers.frame_change_pre.append(handler)


# name -> (builder, motion, kind, res, frames, camera)
# "device-spin" is rendered by novaband_hero.py (the detailed product model):
#   blender -b -P blender/novaband_hero.py -- --shot spin --spin-dir build/deck/anim/device-spin
LOOPS = {
    "orn-pills":     (b_pills, m_pills, "orn", (560, 560), 75, dict(az=30, el=20, lens=85, shadow=True)),
    "orn-ring":      (b_ring, m_ring, "orn", (420, 420), 75, dict(az=30, el=24, lens=85, shadow=True)),
    "corner-rings":  (b_corner_rings, m_corner_rings, "corner", (760, 760), 100, dict(az=0, el=90, lens=50, shadow=True)),
    "corner-wave":   (b_corner_wave, m_corner_wave, "corner", (900, 520), 75, dict(az=12, el=38, lens=50, shadow=True)),
}


def render(name, builder, motion, res, frames, cam):
    sc = A.reset()
    A.MATS.clear()
    bpy.app.handlers.frame_change_pre.clear()
    sc.cycles.samples = SAMPLES
    col = bpy.data.collections.new(name)
    sc.collection.children.link(col)
    builder(col)
    centre, radius = A.normalise(col)
    A.studio(centre, radius, dict(shadow=cam.get("shadow", True), lens=cam["lens"], az=cam["az"], el=cam["el"]))
    if cam["el"] >= 89:
        # straight down: TRACK_TO gets gimbal-locked, so aim the camera explicitly
        cam_o = sc.camera
        cam_o.constraints.clear()
        cam_o.location = centre + Vector((0, 0, cam_o.location.z - centre.z + 0.0))
        cam_o.location = centre + Vector((0, 0, radius / math.sin(math.atan(18 / cam["lens"])) * 1.02))
        cam_o.rotation_euler = (0, 0, 0)
    ctx = dict(holder=ob("holder"), n=frames, centre=centre, radius=radius)
    motion(ctx)
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.fps = FPS
    sc.frame_start = 1
    sc.frame_end = min(frames, FRAME_CAP) if FRAME_CAP else frames
    out = os.path.join(OUT, name)
    os.makedirs(out, exist_ok=True)
    for f in os.listdir(out):
        os.remove(os.path.join(out, f))
    sc.render.filepath = os.path.join(out, "f_")
    # Keep the GPU device, kernels and denoiser alive between frames. Without
    # it Cycles rebuilds everything per frame: ~4 s a frame for a 0.4 s render.
    sc.render.use_persistent_data = True
    bpy.ops.render.render(animation=True)


def main():
    jobs = []
    for name, motion in ICON_MOTION.items():
        s = A.ASSETS[name]
        jobs.append((name, s["fn"], motion, (320, 320), 50,
                     dict(az=s["az"], el=s["el"], lens=s["lens"], shadow=True)))
    for name, (b, m, kind, res, frames, cam) in LOOPS.items():
        jobs.append((name, b, m, res, frames, cam))
    if "--list" in ARGS:
        for j in jobs:
            print("%-16s %4dx%-4d %3d frames" % (j[0], j[3][0], j[3][1], j[4]))
        return
    jobs = [j for j in jobs if not ONLY or j[0] in ONLY]
    if "--force" not in ARGS and not FRAME_CAP:
        def complete(j):
            d = os.path.join(OUT, j[0])
            return os.path.isdir(d) and len([f for f in os.listdir(d) if f.endswith(".png")]) >= j[4]
        skipped = [j[0] for j in jobs if complete(j)]
        jobs = [j for j in jobs if not complete(j)]
        if skipped:
            print("skipping finished loops:", ", ".join(skipped))
    done, failed = [], []
    for i, j in enumerate(jobs):
        print("\n[anim %d/%d] %s" % (i + 1, len(jobs), j[0]), flush=True)
        try:
            render(*j)
            done.append(j[0])
        except Exception as e:
            import traceback
            traceback.print_exc()
            failed.append((j[0], str(e)))
    print("\nANIM DONE: %d ok, %d failed" % (len(done), len(failed)))
    for n, e in failed:
        print("  FAILED %s: %s" % (n, e))


if __name__ == "__main__":
    main()
