# ============================================================
# Nova's talking head for the AI Buddy chat: one transparent still per
# mouth shape (viseme) x eyes open/closed, all from the same camera, so the
# app can swap them in real time to lip-sync the voice (js/nova-buddy.js).
#   python blender/nova_visemes.py         # driver (one Blender, resumes)
#   blender -b -P blender/nova_visemes.py -- --job heads
# Output: build/visemes/<viseme>_<eyes>.png  (eyes: o = open, c = closed)
# ============================================================
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import nova_scene as NS  # noqa: E402

OUT = os.path.join(NS.ROOT, "build", "visemes")
# mouth opening as (width scale, height scale) of the open-mouth shape on its pivot
VISEMES = {
    "rest": (0.90, 0.10),   # closed, slight smile line
    "m":    (0.80, 0.04),   # M / B / P — lips pressed
    "e":    (1.45, 0.62),   # E — wide
    "i":    (1.30, 0.42),   # I — wide, low
    "o":    (0.95, 1.25),   # O — round
    "u":    (0.72, 0.85),   # U — small round
    "a":    (1.30, 1.65),   # A — wide open
}

if NS.bpy is None:
    os.makedirs(OUT, exist_ok=True)
    NS.drive(os.path.abspath(__file__), ["heads"], [OUT], extra=sys.argv[1:])
    sys.exit(0)

import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

M, MA = NS.M, NS.MA
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
SAMPLES = int(ARGS[ARGS.index("--samples") + 1]) if "--samples" in ARGS else 40


def main():
    sc, lids = NS.build_nova("talk", "stand")
    mo = [o for o in (bpy.data.objects.get(n) for n in ("MouthOpen", "Tongue")) if o]
    y = M.front_y(0, 1.566)
    mouth = MA.pivot("MouthPivot", Matrix.Translation(Vector((0, y, 1.575))), mo)
    # a relaxed bust pose: arms down, head turned a touch toward the viewer
    pose = MA.idle(0.0)
    rots, rz, _, _ = pose
    rots = dict(rots)
    rots["head"] = (-3, 0, 6)
    NS.key_pose(1, (rots, rz, 0, 0), lids)
    # key_pose keys the lids; drop those keys or the render resets them to open
    for ctl, _ in lids.values():
        ctl.animation_data_clear()
    M.studio((0, -0.02, 1.47), 0.44, -12, 4, 85, (720, 720))
    sc.cycles.samples = SAMPLES
    sc.cycles.use_adaptive_sampling = True
    sc.frame_set(1)
    for vis, (sx, sz) in VISEMES.items():
        for eyes in ("o", "c"):
            path = os.path.join(OUT, "%s_%s.png" % (vis, eyes))
            if os.path.exists(path) and os.path.getsize(path) > 0:
                continue
            mouth.scale = (sx, 1.0, sz)
            for s, (ctl, close) in lids.items():
                ctl.rotation_euler = (NS.rad(close + 24 if eyes == "c" else 0), 0, 0)
            bpy.context.view_layer.update()
            sc.render.filepath = path
            bpy.ops.render.render(write_still=True)


main()
