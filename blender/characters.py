# ============================================================
# Animated people for the Nova-Band use-case film.
#
# Characters are rigged, motion-captured Sketchfab models (CC-BY, see
# build/sketchfab/credits.json). Most use Mixamo skeletons, so a motion from
# one file can drive another character: bones are matched on their base name
# ("mixamorig7:LeftArm_09" and "mixamorig9:LeftArm_08" are both "LeftArm").
# The Nova-Band pod and its strap are parented to the upper-arm bone, so they
# ride the arm through every swing.
# ============================================================
import bmesh
import bpy
import math
import os
import re
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
SF = os.path.join(os.path.dirname(HERE), "build", "sketchfab")
JUNK = ("Icosphere", "Plane", "Cube")


def base_name(bone):
    """'mixamorig7:LeftArm_09' -> 'leftarm'; 'rp_x_upperarm_l_024' -> 'upperarm_l'."""
    n = bone.split(":")[-1]
    n = re.sub(r"_\d+$", "", n)
    n = re.sub(r"^rp_[a-z]+_animated_\d+_[a-z]+_", "", n)
    return n.lower()


class Character:
    def __init__(self, col, name, height=None, action_hint=None):
        before = set(bpy.data.objects)
        acts_before = set(bpy.data.actions)
        bpy.ops.import_scene.gltf(filepath=os.path.join(SF, name, "scene.gltf"))
        self.objs = [o for o in bpy.data.objects if o not in before]
        for o in self.objs:
            for c in list(o.users_collection):
                c.objects.unlink(o)
            col.objects.link(o)
            if o.type == "MESH" and o.name.split(".")[0] in JUNK:
                o.hide_render = True
                o.hide_viewport = True
        self.name = name
        self.root = bpy.data.objects.new("char_" + name, None)
        col.objects.link(self.root)
        for o in self.objs:
            if o.parent is None:
                o.parent = self.root
        self.arm = next(o for o in self.objs if o.type == "ARMATURE")
        self.meshes = [o for o in self.objs if o.type == "MESH" and not o.hide_render]
        new_acts = [a for a in bpy.data.actions if a not in acts_before and a.frame_range[1] > 1]
        self.action = self.arm.animation_data.action if self.arm.animation_data else (new_acts[0] if new_acts else None)
        self.bones = {base_name(b.name): b.name for b in self.arm.data.bones}
        if height:
            self.set_height(height)

    # ---------------------------------------------------------------- geometry
    def bounds(self):
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        lo, hi = Vector((1e9,) * 3), Vector((-1e9,) * 3)
        for o in self.meshes:
            ev = o.evaluated_get(dg)
            for c in ev.bound_box:
                p = ev.matrix_world @ Vector(c)
                lo = Vector(map(min, lo, p))
                hi = Vector(map(max, hi, p))
        return lo, hi

    def bone_world(self, base, tail=False):
        pb = self.arm.pose.bones[self.bones[base]]
        return self.arm.matrix_world @ (pb.tail if tail else pb.head)

    def set_height(self, h):
        """Scale so the head top sits at `h` metres in the first frame, feet on z = 0."""
        bpy.context.scene.frame_set(1)
        lo, hi = self.bounds()
        k = h / max(hi.z - lo.z, 1e-6)
        self.root.scale = (k, k, k)
        bpy.context.view_layer.update()
        lo, hi = self.bounds()
        self.root.location.z -= lo.z
        bpy.context.view_layer.update()

    def place(self, at, yaw_deg=0.0):
        """Put the character's feet centre at `at` (x, y on the floor), facing yaw."""
        self.root.rotation_euler = (0, 0, math.radians(yaw_deg))
        bpy.context.view_layer.update()
        lo, hi = self.bounds()
        c = (lo + hi) / 2
        self.root.location.x += at[0] - c.x
        self.root.location.y += at[1] - c.y
        self.root.location.z += (at[2] if len(at) > 2 else 0) - lo.z
        bpy.context.view_layer.update()

    # ---------------------------------------------------------------- motion
    def use_action(self, action, offset=0, speed=1.0, loop=True, frames=None):
        """Play `action` through an NLA strip (lets us offset, retime and loop)."""
        ad = self.arm.animation_data or self.arm.animation_data_create()
        ad.action = None
        for t in list(ad.nla_tracks):
            ad.nla_tracks.remove(t)
        tr = ad.nla_tracks.new()
        s = tr.strips.new(action.name, 1, action)
        s.scale = 1.0 / speed
        s.frame_start = 1 - offset
        if loop and frames:
            span = (action.frame_range[1] - action.frame_range[0]) / speed
            s.repeat = max(1.0, (frames + offset) / max(span, 1) + 1)
        s.extrapolation = "HOLD"
        return s

    def retarget(self, src_action):
        """Copy an action from another Mixamo-style rig onto this one, by bone base name."""
        new = bpy.data.actions.new(src_action.name + "_on_" + self.name)
        new.use_fake_user = True                          # survives orphan purges until used
        for fc in src_action.fcurves:
            m = re.match(r'pose\.bones\["(.+?)"\]\.(.+)', fc.data_path)
            if not m:
                continue
            tgt = self.bones.get(base_name(m.group(1)))
            if not tgt:
                continue
            nfc = new.fcurves.new('pose.bones["%s"].%s' % (tgt, m.group(2)), index=fc.array_index)
            nfc.keyframe_points.add(len(fc.keyframe_points))
            for a, b in zip(fc.keyframe_points, nfc.keyframe_points):
                b.co, b.interpolation = a.co.copy(), a.interpolation
        return new

    def ground_speed(self, action, fps_scale=1.0):
        """For an in-place cycle: how fast the planted foot slides back (m/frame).
        Moving the character forward at this speed plants the feet."""
        self.use_action(action)
        sc = bpy.context.scene
        f0, f1 = int(action.frame_range[0]) + 1, int(action.frame_range[1]) + 1
        foot = next((k for k in ("leftfoot", "l_foot", "foot_l") if k in self.bones), None)
        if not foot:
            return 0.0
        pts = []
        for f in range(f0, f1):
            sc.frame_set(f)
            pts.append(self.bone_world(foot))
        # stance: the lowest 40 % of samples by height; speed = median horizontal step there
        zs = sorted(p.z for p in pts)
        thr = zs[int(len(zs) * 0.4)]
        steps = [(pts[i + 1] - pts[i]).xy.length for i in range(len(pts) - 1) if pts[i].z <= thr and pts[i + 1].z <= thr]
        steps.sort()
        return steps[len(steps) // 2] if steps else 0.0

    # ---------------------------------------------------------------- the Nova-Band on the upper arm
    def strap_pod(self, pod_module, screen_dir=None, start=1, side="left", case_color="#4e101b", along=0.42):
        """Build the pod + an arm band around the upper arm and parent both to the bone."""
        sc = bpy.context.scene
        sc.frame_set(1)
        bpy.context.view_layer.update()
        up = "leftarm" if side == "left" else "rightarm"
        lo_ = "leftforearm" if side == "left" else "rightforearm"
        if up not in self.bones:
            up, lo_ = ("upperarm_l", "lowerarm_l") if side == "left" else ("upperarm_r", "lowerarm_r")
        a, b = self.bone_world(up), self.bone_world(lo_)
        ax = (b - a).normalized()
        centre = a.lerp(b, along)
        chest_key = next((k for k in ("spine2", "spine_02", "spine1", "spine") if k in self.bones), None)
        chest = self.bone_world(chest_key) if chest_key else centre - Vector((0.2, 0, 0))
        out = centre - chest
        out = (out - ax * out.dot(ax)).normalized()
        # arm radius from the skinned mesh around the centre
        r = self._arm_radius(centre, ax, out) or 0.05
        y = out.cross(ax)
        R = Matrix((ax, y, out)).transposed().to_4x4()
        col = bpy.data.collections.new("pod_" + self.name)
        sc.collection.children.link(col)
        pod = pod_module.build(col, case_color=case_color, screen=screen_dir, start=start, strap=False)
        pod.matrix_world = Matrix.Translation(centre + out * (r + 0.004)) @ R
        band = _arm_band(col, centre, ax, out, r + 0.0025)
        bone = self.arm.pose.bones[self.bones[up]]
        for o in (pod, band):
            mw = o.matrix_world.copy()
            o.parent = self.arm
            o.parent_type = "BONE"
            o.parent_bone = bone.name
            bpy.context.view_layer.update()
            o.matrix_world = mw
        return pod

    def _arm_radius(self, c, ax, out):
        """Distance from the bone axis to the skin, sampled outward (evaluated mesh)."""
        dg = bpy.context.evaluated_depsgraph_get()
        best = None
        for o in self.meshes:
            ev = o.evaluated_get(dg)
            me = ev.to_mesh()
            mw = ev.matrix_world
            ds = []
            for v in me.vertices:
                p = mw @ v.co
                d = p - c
                t = d.dot(ax)
                if abs(t) > 0.03:
                    continue
                radial = d - ax * t
                if radial.length < 0.12 and radial.normalized().dot(out) > 0.6:
                    ds.append(radial.length)
            ev.to_mesh_clear()
            if ds:
                ds.sort()
                val = ds[int(len(ds) * 0.8)]
                best = max(best or 0, val)
        return best


def _arm_band(col, c, ax, out, r):
    import importlib.util
    spec = importlib.util.spec_from_file_location("nb_hero_band", os.path.join(HERE, "novaband_hero.py"))
    H = importlib.util.module_from_spec(spec)
    import sys
    argv = sys.argv
    sys.argv = argv[:1]
    spec.loader.exec_module(H)
    sys.argv = argv
    fab = H.fabric("ArmStrap", "#1c0409", "#431019", period=0.0009, bump=0.6)
    y = out.cross(ax)
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    N, hw, t = 72, 0.019, 0.0016
    rings = []
    for i in range(N):
        a = 2 * math.pi * i / N
        d = out * math.cos(a) + y * math.sin(a)
        rr = r * (1.0 + 0.06 * math.cos(2 * a))
        rings.append([bm.verts.new(c + d * (rr + dz) + ax * dx) for dx, dz in ((-hw, 0), (hw, 0), (hw, t), (-hw, t))])
    for i in range(N):
        a, b = rings[i], rings[(i + 1) % N]
        for j in range(4):
            f = bm.faces.new((a[j], a[(j + 1) % 4], b[(j + 1) % 4], b[j]))
            for loop, uv in zip(f.loops, ((i * .005, j * .02), (i * .005, (j + 1) * .02), ((i + 1) * .005, (j + 1) * .02), ((i + 1) * .005, j * .02))):
                loop[uvl].uv = uv
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new("ArmBand")
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    o = bpy.data.objects.new("ArmBand", me)
    col.objects.link(o)
    me.materials.append(fab)
    return o
