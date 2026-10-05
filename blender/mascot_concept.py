# Concept stills for the detailed Nova (blender/mascot_detail.py).
#   blender -b -P blender/mascot_concept.py -- --shot hero|face|arm --detail 1 --samples 64
# Output: build/mascot_concept/<shot>_<detail>.png
import importlib.util
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
arg = lambda n, d=None: ARGS[ARGS.index(n) + 1] if n in ARGS else d
SHOT = arg("--shot", "hero")
DETAIL = int(arg("--detail", "1"))
OUT = os.path.join(os.path.dirname(HERE), "build", "mascot_concept")
os.makedirs(OUT, exist_ok=True)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


M = load("nb_mascot", os.path.join(HERE, "mascot.py"))
D = load("nb_detail", os.path.join(HERE, "mascot_detail.py"))
CAMS = {   # pose, expr, target, half h, az, el, lens, res
    "hero": ("thumbs", "smirk", (0, 0, 0.99), 1.07, -24, 5, 70, (1200, 1500)),
    "face": ("stand", "smirk", (0, -0.05, 1.66), 0.27, -14, 3, 85, (1200, 1080)),
    "arm": ("stand", "smirk", None, 0.15, 52, 8, 85, (1200, 1200)),
}
pose, expr, target, hh, az, el, lens, res = CAMS[SHOT]
sc = M.A.reset()
M.COLL = bpy.data.collections.new("mascot")
sc.collection.children.link(M.COLL)
M.materials()
if DETAIL:
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
if DETAIL:
    n = D.apply(M, screen=os.path.join(os.path.dirname(HERE), "build", "sim", "live", "f_0120.png"))
    print("FUR STRANDS", n)
M.apply_pose(pose)
dof = None
if target is None:
    S, E = Vector(M.J["shoulder.L"]), Vector(M.J["elbow.L"])
    P = S.lerp(E, 0.52)
    target = M.EMP["shoulder.L"].matrix_world @ (P - S) + Vector((0.03, -0.02, 0))
    dof = 2.8
M.studio(target, hh, az, el, lens, res, dof=dof)
sc.cycles.samples = int(arg("--samples", "64"))
sc.cycles.use_adaptive_sampling = True
sc.render.filepath = os.path.join(OUT, "%s_%d.png" % (SHOT, DETAIL))
bpy.ops.render.render(write_still=True)
print("CONCEPT DONE", sc.render.filepath)
