# ============================================================
# NovaBand — procedural 3D model for Blender (headless)
#
#   blender -b -P blender/novaband_model.py
#   blender -b -P blender/novaband_model.py -- --no-render
#
# Outputs:
#   assets/novaband.glb            -> loaded by Three.js on the website
#   build/novaband-render.png      -> reference still (the site uses assets/3d/*)
#
# Everything is generated from primitives + modifiers, so there is no
# .blend binary to keep in the repo: re-run the script and you get the
# exact same band back.
#
# Orientation: the arm runs along Y, the strap ring lies in the XZ
# plane, and the sensor module sits at the top of the ring (+Z).
# One Blender unit is one metre and the band is modelled at true scale.
# ============================================================

import bpy
import math
import os
import sys

# ---------------------------------------------------------------
# Paths — resolved from the script location, not the CWD
# ---------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
PROJECT = os.path.dirname(SCRIPT_DIR)
ASSETS = os.path.join(PROJECT, "assets")
os.makedirs(ASSETS, exist_ok=True)

GLB_PATH = os.path.join(ASSETS, "novaband.glb")
PNG_PATH = os.path.join(PROJECT, "build", "novaband-render.png")   # reference still, not shipped

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
DO_RENDER = "--no-render" not in ARGS

# ---------------------------------------------------------------
# Dimensions (metres)
# ---------------------------------------------------------------
BAND_R = 0.050          # ring radius — fits an upper arm
BAND_T = 0.0022         # strap thickness (radial half-extent)
BAND_W = 0.0130         # strap half-width along the arm
TOP_Z = BAND_R + BAND_T  # where the module meets the strap

# ---------------------------------------------------------------
# Brand palette
#
# Blender wants LINEAR values, while the brand is specified in sRGB
# hex, so every colour goes through srgb() rather than being eyeballed
# — that is what keeps the render burgundy instead of drifting pink.
# ---------------------------------------------------------------
def srgb(hex_str):
    hex_str = hex_str.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(hex_str[i:i + 2], 16) / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return (out[0], out[1], out[2], 1.0)


C_BAND    = srgb("#6b1230")   # strap burgundy
C_CASE    = srgb("#7d1233")   # module, a touch brighter
C_CASE_DK = srgb("#2c0711")   # skin-side pod
C_GLASS   = srgb("#0b0a0c")   # optical window
C_METAL   = srgb("#c9c4cc")   # buckle
C_LED     = (0.090, 1.000, 0.320, 1.0)   # PPG green
C_IR      = (0.850, 0.110, 0.140, 1.0)   # IR / red channel


# ---------------------------------------------------------------
# Scene reset
# ---------------------------------------------------------------
def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for block in (bpy.data.meshes, bpy.data.materials, bpy.data.lights,
                  bpy.data.cameras, bpy.data.objects, bpy.data.collections):
        for item in list(block):
            if item.users == 0:
                block.remove(item)


# ---------------------------------------------------------------
# Material helpers — Principled socket names moved around between
# Blender versions, so every set is name-tolerant.
# ---------------------------------------------------------------
def set_input(node, names, value):
    if isinstance(names, str):
        names = [names]
    for n in names:
        if n in node.inputs:
            node.inputs[n].default_value = value
            return True
    return False


def make_material(name, base, roughness=0.5, metallic=0.0,
                  emission=None, emission_strength=0.0, coat=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf is None:
        bsdf = mat.node_tree.nodes.new("ShaderNodeBsdfPrincipled")
    set_input(bsdf, "Base Color", base)
    set_input(bsdf, "Roughness", roughness)
    set_input(bsdf, "Metallic", metallic)
    if coat:
        set_input(bsdf, ["Coat Weight", "Clearcoat"], coat)
        set_input(bsdf, ["Coat Roughness", "Clearcoat Roughness"], 0.05)
    if emission is not None:
        set_input(bsdf, ["Emission Color", "Emission"], emission)
        set_input(bsdf, "Emission Strength", emission_strength)
    return mat


def assign(obj, mat):
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    return obj


def shade_smooth(obj, angle=math.radians(35)):
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.shade_smooth()
    mesh = obj.data
    if hasattr(mesh, "use_auto_smooth"):        # Blender <= 4.0
        mesh.use_auto_smooth = True
        mesh.auto_smooth_angle = angle
    return obj


def bevel(obj, width=0.0015, segments=4, angle=math.radians(50)):
    m = obj.modifiers.new("Bevel", "BEVEL")
    m.width = width
    m.segments = segments
    m.limit_method = "ANGLE"
    m.angle_limit = angle
    return obj


def apply_transform(obj, location=False, rotation=True, scale=True):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=location, rotation=rotation, scale=scale)
    return obj


def ring_point(angle_deg):
    """A point on the strap ring, plus the tangent rotation for accessories."""
    a = math.radians(angle_deg)
    return (BAND_R * math.cos(a), 0.0, BAND_R * math.sin(a)), (0.0, -a, 0.0)


# ---------------------------------------------------------------
# Strap
# ---------------------------------------------------------------
def build_strap(mat_band, mat_metal):
    parts = []

    # --- main elastic loop, flattened into a band ---------------
    bpy.ops.mesh.primitive_torus_add(
        major_radius=BAND_R, minor_radius=BAND_T,
        major_segments=96, minor_segments=12, location=(0, 0, 0))
    strap = bpy.context.object
    strap.name = "Strap"
    strap.rotation_euler[0] = math.radians(90)          # ring axis -> Y
    apply_transform(strap, rotation=True, scale=False)
    strap.scale = (1.0, BAND_W / BAND_T, 1.0)           # rope -> flat band
    apply_transform(strap, rotation=False, scale=True)
    shade_smooth(strap)
    parts.append(assign(strap, mat_band))

    # --- woven ribs: thin rings arrayed across the band width ---
    bpy.ops.mesh.primitive_torus_add(
        major_radius=BAND_R + BAND_T * 0.55, minor_radius=BAND_T * 0.30,
        major_segments=56, minor_segments=8, location=(0, 0, 0))
    rib = bpy.context.object
    rib.name = "StrapRib"
    rib.rotation_euler[0] = math.radians(90)
    apply_transform(rib, rotation=True, scale=False)
    arr = rib.modifiers.new("Array", "ARRAY")
    arr.count = 9
    arr.use_relative_offset = False
    arr.use_constant_offset = True
    arr.constant_offset_displace = (0, BAND_W * 2 / 9.0, 0)
    rib.location = (0, -BAND_W + BAND_W / 9.0, 0)
    shade_smooth(rib)
    parts.append(assign(rib, mat_band))

    # --- loops that wrap right around the strap -----------------
    # After the tangent rotation the torus' local X is radial and its
    # local Y runs along the band width, so the loop is built at full
    # band width and squashed on X to clear the strap thickness.
    def wrap_loop(name, angle_deg, gap, tube, mat, width_factor=1.0):
        loc, rot = ring_point(angle_deg)
        major = (BAND_W + gap) * width_factor
        bpy.ops.mesh.primitive_torus_add(
            major_radius=major, minor_radius=tube,
            major_segments=36, minor_segments=8, location=loc)
        obj = bpy.context.object
        obj.name = name
        obj.rotation_euler = rot
        obj.scale = ((BAND_T + gap) / major, 1.0, 1.0)
        shade_smooth(obj)
        parts.append(assign(obj, mat))
        return obj

    wrap_loop("Keeper", 212, 0.0016, 0.0012, mat_band)
    wrap_loop("Buckle", 250, 0.0013, 0.0009, mat_metal, width_factor=0.86)

    return parts


# ---------------------------------------------------------------
# Sensor module
# ---------------------------------------------------------------
def build_module(mat_case, mat_case_dk, mat_glass, mat_led, mat_ir):
    parts = []

    def box(name, loc, scale, mat, bevel_w=0.0015, segs=6, smooth=True):
        bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
        obj = bpy.context.object
        obj.name = name
        obj.scale = scale
        apply_transform(obj, rotation=False, scale=True)
        if bevel_w:
            bevel(obj, width=bevel_w, segments=segs)
        if smooth:
            shade_smooth(obj)
        parts.append(assign(obj, mat))
        return obj

    # Proportions follow the product photos in the ISIF deck: the module is
    # a pill elongated ALONG the strap (X, the ring tangent at the top),
    # slightly wider than the 26 mm strap, with the optics stacked along
    # its long axis. primitive_cube_add(size=1) scaled by (sx, sy, sz)
    # gives full extents of exactly sx * sy * sz metres.

    # main housing: 36 x 28 x 9 mm
    box("ModuleCase", (0, 0, TOP_Z + 0.0045),
        (0.0360, 0.0280, 0.0090), mat_case, bevel_w=0.0060, segs=8)

    # skin-side pod that presses the optics against the arm
    box("SensorPod", (0, 0, TOP_Z - 0.0013),
        (0.0240, 0.0180, 0.0026), mat_case_dk, bevel_w=0.0020, segs=5)

    # raised optical window
    box("OpticalWindow", (0, 0, TOP_Z + 0.0096),
        (0.0180, 0.0120, 0.0012), mat_glass, bevel_w=0.0035, segs=6)

    # PPG emitters along the long axis: two green LEDs + one IR diode
    for name, loc, r, mat in (
        ("LedGreenA", (-0.0012, 0, TOP_Z + 0.0103), 0.0016, mat_led),
        ("LedGreenB", (0.0030, 0, TOP_Z + 0.0103), 0.0016, mat_led),
        ("LedIR",     (0.0066, 0, TOP_Z + 0.0103), 0.0011, mat_ir),
    ):
        bpy.ops.mesh.primitive_cylinder_add(
            radius=r, depth=0.0006, vertices=28, location=loc)
        led = bpy.context.object
        led.name = name
        shade_smooth(led)
        parts.append(assign(led, mat))

    # photodetector at the other end of the window
    box("Photodetector", (-0.0056, 0, TOP_Z + 0.0103),
        (0.0024, 0.0024, 0.0005), mat_case_dk, bevel_w=0.0004, segs=3, smooth=False)

    # the small pill-shaped status light near the end of the module
    box("StatusLed", (0.0150, 0, TOP_Z + 0.0091),
        (0.0012, 0.0050, 0.0008), mat_led, bevel_w=0.0005, segs=4)

    return parts


# ---------------------------------------------------------------
def build():
    clear_scene()

    mat_band    = make_material("NB_Strap",    C_BAND,    roughness=0.78, metallic=0.03)
    mat_case    = make_material("NB_Case",     C_CASE,    roughness=0.34, metallic=0.45, coat=0.7)
    mat_case_dk = make_material("NB_CaseDark", C_CASE_DK, roughness=0.46, metallic=0.30)
    mat_glass   = make_material("NB_Glass",    C_GLASS,   roughness=0.05, metallic=0.10, coat=1.0)
    mat_metal   = make_material("NB_Metal",    C_METAL,   roughness=0.24, metallic=1.0)
    mat_led     = make_material("NB_LedGreen", C_LED,     roughness=0.15,
                                emission=C_LED, emission_strength=3.2)
    mat_ir      = make_material("NB_LedIR",    C_IR,      roughness=0.15,
                                emission=C_IR, emission_strength=1.6)

    col = bpy.data.collections.new("NovaBand")
    bpy.context.scene.collection.children.link(col)

    parts = []
    parts += build_strap(mat_band, mat_metal)
    parts += build_module(mat_case, mat_case_dk, mat_glass, mat_led, mat_ir)

    for obj in parts:
        for c in list(obj.users_collection):
            c.objects.unlink(obj)
        col.objects.link(obj)

    root = bpy.data.objects.new("NovaBand", None)
    root.empty_display_size = 0.02
    col.objects.link(root)
    for obj in parts:
        obj.parent = root

    return root, parts


# ---------------------------------------------------------------
# Studio: three-point lighting + a tracked camera
# ---------------------------------------------------------------
def build_studio():
    scene = bpy.context.scene

    world = scene.world
    if world is None:
        world = bpy.data.worlds.new("World")
        scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.045, 0.038, 0.048, 1.0)
        bg.inputs[1].default_value = 1.0

    target = bpy.data.objects.new("CamTarget", None)
    target.location = (0, 0, 0.006)
    scene.collection.objects.link(target)

    def add_area(name, loc, size, energy, color):
        data = bpy.data.lights.new(name, "AREA")
        data.energy = energy
        data.size = size
        data.color = color
        obj = bpy.data.objects.new(name, data)
        obj.location = loc
        scene.collection.objects.link(obj)
        track = obj.constraints.new("TRACK_TO")
        track.target = target
        track.track_axis = "TRACK_NEGATIVE_Z"
        track.up_axis = "UP_Y"
        return obj

    #                        position                size  W    tint
    add_area("KeyLight",  (0.26, -0.30, 0.30), 0.34, 5.5, (1.00, 0.94, 0.96))
    add_area("RimLight",  (-0.30, 0.22, 0.18), 0.28, 3.4, (1.00, 0.42, 0.60))
    add_area("FillLight", (-0.16, -0.32, -0.14), 0.40, 1.2, (0.70, 0.80, 1.00))

    cam_data = bpy.data.cameras.new("Camera")
    cam_data.lens = 62
    cam = bpy.data.objects.new("Camera", cam_data)
    cam.location = (0.160, -0.235, 0.185)      # ~0.33 m, raised to show the LEDs
    scene.collection.objects.link(cam)
    track = cam.constraints.new("TRACK_TO")
    track.target = target
    track.track_axis = "TRACK_NEGATIVE_Z"
    track.up_axis = "UP_Y"
    scene.camera = cam
    return cam


def pick_eevee():
    items = {i.identifier for i in
             bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items}
    for candidate in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        if candidate in items:
            return candidate
    return "CYCLES"


def render_still(path):
    scene = bpy.context.scene
    scene.render.engine = pick_eevee()
    scene.render.resolution_x = 1200
    scene.render.resolution_y = 1500
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"

    view = scene.view_settings
    looks = {i.identifier for i in
             bpy.types.ColorManagedViewSettings.bl_rna.properties["look"].enum_items}
    for candidate in ("AgX - Medium High Contrast", "Medium High Contrast", "None"):
        if candidate in looks:
            view.look = candidate
            break
    view.exposure = -0.35

    ee = getattr(scene, "eevee", None)
    if ee is not None:
        for attr, value in (("use_bloom", True), ("bloom_intensity", 0.04),
                            ("bloom_threshold", 1.2), ("taa_render_samples", 128),
                            ("use_gtao", True), ("use_ssr", True),
                            ("use_raytracing", True)):
            if hasattr(ee, attr):
                setattr(ee, attr, value)

    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


def export_glb(path):
    try:
        bpy.ops.export_scene.gltf(filepath=path, export_format="GLB",
                                  export_apply=True, export_yup=True)
    except TypeError:
        bpy.ops.export_scene.gltf(filepath=path, export_format="GLB")


def main():
    root, parts = build()
    print("NovaBand: built %d objects" % len(parts))

    export_glb(GLB_PATH)
    print("NovaBand: exported -> %s" % GLB_PATH)

    if DO_RENDER:
        build_studio()
        render_still(PNG_PATH)
        print("NovaBand: rendered -> %s" % PNG_PATH)


# Guarded so novaband_assets.py can import build() and the material
# helpers without triggering an export or a render.
if __name__ == "__main__":
    main()
