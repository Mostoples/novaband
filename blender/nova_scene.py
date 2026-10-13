# ============================================================
# Shared helpers for the ad and the tutorial: build the detailed Nova
# (mascot.py + mascot_detail.py), pivots for blinking lids / talking mouth,
# blend the keyed poses from mascot_anim.py, and a generic driver that
# renders one Blender process per job and resumes after a crash.
# ============================================================
import math
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BLENDER = os.environ.get("BLENDER", r"C:\Program Files\Blender Foundation\Blender 4.0\blender.exe")


def drive(script, jobs, out_dirs, extra=(), tries=40):
    """Plain-Python side: run `blender -b -P script -- --job J extra` until every frame exists."""
    for job, out in zip(jobs, out_dirs):
        t0 = time.time()
        for _ in range(tries):
            r = subprocess.run([BLENDER, "-b", "-P", script, "--", "--job", job] + list(extra),
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if r.returncode == 0:
                break
        n = len([f for f in os.listdir(out) if f.startswith("f_") and os.path.getsize(os.path.join(out, f)) > 0]) \
            if os.path.isdir(out) else 0
        print("%-10s %4d frames  exit %d  %6.0fs" % (job, n, r.returncode, time.time() - t0), flush=True)


try:
    import bpy
    from mathutils import Matrix, Vector
except ImportError:
    bpy = None

if bpy:
    import importlib.util

    def _load(name, path):
        spec = importlib.util.spec_from_file_location(name, path)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m

    _argv = sys.argv
    sys.argv = _argv[:_argv.index("--")] if "--" in _argv else _argv   # keep mascot_anim's arg parser quiet
    MA = _load("nb_mascot_anim", os.path.join(HERE, "mascot_anim.py"))
    sys.argv = _argv
    M = MA.M
    D = _load("nb_mascot_detail", os.path.join(HERE, "mascot_detail.py"))
    rad = math.radians

    def build_nova(expr="smirk", pose="stand", screen=None, screen_frames=1, fur=1.0):
        sc = M.A.reset()
        M.COLL = bpy.data.collections.new("mascot")
        sc.collection.children.link(M.COLL)
        M.materials()
        D.materials(M)
        M.build_rig()
        M.build_torso()
        M.build_chest_logo()
        M.build_hips()
        for s in ("L", "R"):
            M.build_arm(s)
            M.build_hand(s, thumb_up=(pose == "thumbs" and s == "R"))
            M.build_leg(s)
        M.build_tail(pose)
        M.build_head(expr)
        D.apply(M, screen=screen, fur=fur, sequence=screen_frames > 1, frames=screen_frames)
        bpy.context.view_layer.update()
        lids = {}
        lo = M.EXPR[expr][:2]
        slant = M.EXPR[expr][2]
        for s, sx, deg in (("L", 1, lo[0]), ("R", -1, lo[1])):
            o = bpy.data.objects.get("Lid." + s)
            if o is None or deg > 60:
                continue
            c = Vector((0.08 * sx, -0.168, 1.708))
            Mr = (Matrix.Translation(c) @ Matrix.Rotation(rad(15 * sx), 4, "Z")
                  @ Matrix.Rotation(rad(-slant * sx), 4, "Y"))
            lids[s] = (MA.pivot("LidPivot." + s, Mr, [o]), 78 - deg)
        return sc, lids

    def blend(pa, pb, w):
        """Linear blend of two pose results (rots, rz, blink, mouth)."""
        ra, za, ba, ma = pa
        rb, zb, bb, mb = pb
        keys = set(ra) | set(rb)
        rots = {}
        for k in keys:
            a, b = ra.get(k, (0, 0, 0)), rb.get(k, (0, 0, 0))
            rots[k] = tuple(x + (y - x) * w for x, y in zip(a, b))
        return rots, za + (zb - za) * w, max(ba, bb) if 0 < w < 1 else (ba if w == 0 else bb), ma + (mb - ma) * w

    def key_pose(f, pose, lids):
        rots, rz, bl, _ = pose
        for j, e in M.EMP.items():
            x, y, z = rots.get(j, (0, 0, 0))
            e.rotation_euler = (rad(x), rad(y), rad(z))
            e.keyframe_insert("rotation_euler", frame=f)
        M.EMP["root"].location = (0, 0, rz)
        M.EMP["root"].keyframe_insert("location", frame=f)
        for s, (ctl, close) in lids.items():
            ctl.rotation_euler = (rad(close * bl), 0, 0)
            ctl.keyframe_insert("rotation_euler", frame=f)

    def linear_keys():
        for ob in bpy.data.objects:
            ad = ob.animation_data
            if ad and ad.action:
                for fc in ad.action.fcurves:
                    for k in fc.keyframe_points:
                        k.interpolation = "LINEAR"

    def render_frames(sc, out, frames, test=None):
        os.makedirs(out, exist_ok=True)
        for f in ([test] if test else range(1, frames + 1)):
            path = os.path.join(out, ("test_%04d.png" if test else "f_%04d.png") % f)
            if not test and os.path.exists(path) and os.path.getsize(path) > 0:
                continue
            sc.frame_set(f)
            sc.render.filepath = path
            bpy.ops.render.render(write_still=True)
