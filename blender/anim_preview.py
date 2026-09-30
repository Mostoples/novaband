# Preview animated Sketchfab characters: rig, actions, size, and 3 frames each.
#   blender -b -P blender/anim_preview.py -- an-jogging an-phone ...
import bpy, os, sys
from mathutils import Vector
SF = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "build", "sketchfab")
OUT = os.path.join(SF, "_preview")
names = sys.argv[sys.argv.index("--") + 1:]

for name in names:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    bpy.ops.import_scene.gltf(filepath=os.path.join(SF, name, "scene.gltf"))
    arms = [o for o in sc.objects if o.type == "ARMATURE"]
    acts = [a for a in bpy.data.actions if a.frame_range[1] > 1]
    arm_bones = [b.name for a in arms for b in a.data.bones if any(k in b.name.lower() for k in ("upperarm", "leftarm", "l_upperarm", "arm_l", "upper_arm"))]
    print("PV %s arms=%d bones=%s actions=%s" % (name, len(arms), arm_bones[:4], [(a.name, int(a.frame_range[1])) for a in acts][:6]))
    sc.render.engine = "CYCLES"; sc.cycles.samples = 32; sc.cycles.device = "GPU"
    pr = bpy.context.preferences.addons["cycles"].preferences; pr.compute_device_type = "OPTIX"; pr.get_devices()
    for d in pr.devices: d.use = d.type == "OPTIX"
    sc.view_settings.view_transform = "AgX"
    w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True; w.node_tree.nodes["Background"].inputs[1].default_value = 1.0
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN")); sun.data.energy = 3; sun.rotation_euler = (0.9, 0.2, 0.7); sc.collection.objects.link(sun)
    cam = bpy.data.objects.new("c", bpy.data.cameras.new("c")); sc.collection.objects.link(cam); sc.camera = cam; cam.data.lens = 40
    sc.render.resolution_x, sc.render.resolution_y = 360, 480
    end = int(max((a.frame_range[1] for a in acts), default=1))
    for k, fr in enumerate((1, max(1, end // 3), max(1, 2 * end // 3))):
        sc.frame_set(fr); bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        lo = Vector((1e9,) * 3); hi = Vector((-1e9,) * 3)
        for o in sc.objects:
            if o.type == "MESH":
                ev = o.evaluated_get(dg)
                for c in ev.bound_box:
                    p = ev.matrix_world @ Vector(c); lo = Vector(map(min, lo, p)); hi = Vector(map(max, hi, p))
        ctr = (lo + hi) / 2; h = max((hi - lo).z, 0.1)
        if k == 0:
            print("PV   size %.2f x %.2f x %.2f  frames %d" % ((hi - lo).x, (hi - lo).y, (hi - lo).z, end))
        cam.location = ctr + Vector((h * 0.8, -h * 1.9, h * 0.1))
        cam.rotation_euler = (ctr - cam.location).to_track_quat("-Z", "Y").to_euler()
        sc.render.filepath = os.path.join(OUT, "%s_%d.png" % (name, k))
        bpy.ops.render.render(write_still=True)
