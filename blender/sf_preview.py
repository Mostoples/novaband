# Quick look at every downloaded Sketchfab asset: import, frame, render a thumbnail.
#   blender -b -P blender/sf_preview.py -- name1 name2 ...
import bpy, os, sys, math
from mathutils import Vector
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SF = os.path.join(ROOT, "build", "sketchfab")
OUT = os.path.join(SF, "_preview"); os.makedirs(OUT, exist_ok=True)
names = sys.argv[sys.argv.index("--") + 1:]
for name in names:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE"
    bpy.ops.import_scene.gltf(filepath=os.path.join(SF, name, "scene.gltf"))
    objs = [o for o in sc.objects if o.type == "MESH"]
    bpy.context.view_layer.update()
    lo = Vector((1e9,) * 3); hi = Vector((-1e9,) * 3)
    for o in objs:
        for c in o.bound_box:
            w = o.matrix_world @ Vector(c)
            lo = Vector(map(min, lo, w)); hi = Vector(map(max, hi, w))
    ctr, size = (lo + hi) / 2, (hi - lo)
    print("ASSET %s dims=%.2f x %.2f x %.2f  meshes=%d" % (name, size.x, size.y, size.z, len(objs)))
    r = size.length / 2
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam)
    cam.data.lens = 35; cam.data.clip_end = r * 50; cam.data.clip_start = r / 1000
    cam.location = ctr + Vector((0.9, -1.4, 0.7)).normalized() * r * 2.4
    cam.rotation_euler = (ctr - cam.location).to_track_quat("-Z", "Y").to_euler()
    sc.camera = cam
    w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[1].default_value = 1.0
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN")); sun.data.energy = 3
    sun.rotation_euler = (0.8, 0.2, 0.6); sc.collection.objects.link(sun)
    sc.render.resolution_x, sc.render.resolution_y = 640, 400
    sc.render.filepath = os.path.join(OUT, name + ".png")
    bpy.ops.render.render(write_still=True)
