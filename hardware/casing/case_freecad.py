"""
Solid model of the Nova-Band pod (FreeCAD 1.x, headless):

    "C:/Program Files/FreeCAD 1.1/bin/freecadcmd.exe" hardware/casing/case_freecad.py

-> hardware/casing/out/  case_top.stl  case_bottom.stl  button_cap.stl  novaband_case.step

Print both shells face-down on their flat joint (no supports), 0.2 mm layers,
PETG or ASA for sweat; button caps upright. Assembly: board into the tray,
caps into the lid, lid on, 4 x M2 x 8 self-tapping screws from below.
"""
import os
import sys

import FreeCAD as App
import MeshPart
import Part

HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in dir() else os.path.join(os.getcwd(), "hardware", "casing")
sys.path.insert(0, HERE)
import case_params as P  # noqa: E402

OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)
V = App.Vector


def rbox(x0, x1, y0, y1, z0, z1, r):
    """Box with rounded vertical edges."""
    b = Part.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, y0, z0))
    if r <= 0:
        return b
    vert = [e for e in b.Edges if abs(e.Vertexes[0].Point.z - e.Vertexes[1].Point.z) > 1e-6]
    return b.makeFillet(min(r, (x1 - x0) / 2 - 0.01, (y1 - y0) / 2 - 0.01), vert)


def round_edges_at(shape, z, r):
    edges = [e for e in shape.Edges
             if all(abs(v.Point.z - z) < 1e-6 for v in e.Vertexes)]
    return shape.makeFillet(r, edges)


def cyl(x, y, z0, z1, d):
    return Part.makeCylinder(d / 2, z1 - z0, V(x, y, z0))


hl, hw = P.L / 2, P.W / 2
bx, by = P.BOARD_L / 2 + P.CLEAR, P.BOARD_W / 2 + P.CLEAR
screws = [(sx * P.SCREW_X, sy * P.SCREW_Y) for sx in (-1, 1) for sy in (-1, 1)]

# ------------------------------------------------------------------ bottom tray
tray = rbox(-hl, hl, -hw, hw, 0, P.SPLIT, P.R)
tray = round_edges_at(tray, 0.0, 1.2)
floor_top = P.TUNNEL_Z0 + P.TUNNEL_H + P.FLOOR
cuts = [
    rbox(-bx, bx, -by, by, P.PCB_Z, P.SPLIT + 1, 1.0),                         # board pocket
    rbox(-bx, bx, -(by - P.LEDGE), by - P.LEDGE, floor_top, P.PCB_Z + 0.01, 1.0),  # under-board cavity
    Part.makeBox(P.TUNNEL_L, P.W + 2, P.TUNNEL_H, V(-P.TUNNEL_L / 2, -hw - 1, P.TUNNEL_Z0)),  # strap tunnel
]
for x, y in screws:
    cuts.append(cyl(x, y, -1, P.SPLIT + 1, 2.2))                               # clearance
    cuts.append(cyl(x, y, -1, P.HEAD_T + 0.2, P.HEAD_D + 0.3))                  # counterbore
for c in cuts:
    tray = tray.cut(c)

# ------------------------------------------------------------------ top shell
top = rbox(-hl, hl, -hw, hw, P.SPLIT, P.H, P.R)
top = round_edges_at(top, P.H, P.EDGE)
cuts = [
    rbox(-bx, bx, -by, by, P.SPLIT - 1, P.GLASS_TOP, 1.0),                     # board + display cavity
    rbox(P.WIN_X0, P.WIN_X1, -P.WIN_W / 2, P.WIN_W / 2, P.GLASS_TOP - 0.5, P.H + 1, P.WIN_R),  # window
]
for sy in (-1, 1):
    cuts.append(cyl(P.BTN_X, sy * P.BTN_Y, P.GLASS_TOP - 0.5, P.H + 1, P.BTN_HOLE))
for x, y in screws:
    cuts.append(cyl(x, y, P.SPLIT - 1, P.SPLIT + 7.0, P.SCREW_D))               # pilot for M2
for c in cuts:
    top = top.cut(c)

# USB-C: through the -X end wall of both shells
usb_z = P.PCB_TOP + P.USB_Z_ABOVE_PCB + P.USB_H / 2
# a stadium-shaped opening: four cylinders + two boxes
w2 = P.USB_CUT_W / 2 - P.USB_CUT_R
h2 = P.USB_CUT_H / 2 - P.USB_CUT_R
blocks = []
for yy in (-w2, w2):
    for zz in (-h2, h2):
        blocks.append(Part.makeCylinder(P.USB_CUT_R, 8, V(-hl - 2, yy, usb_z + zz), V(1, 0, 0)))
blocks.append(Part.makeBox(8, P.USB_CUT_W, P.USB_CUT_H - 2 * P.USB_CUT_R, V(-hl - 2, -P.USB_CUT_W / 2, usb_z - h2)))
blocks.append(Part.makeBox(8, P.USB_CUT_W - 2 * P.USB_CUT_R, P.USB_CUT_H, V(-hl - 2, -w2, usb_z - P.USB_CUT_H / 2)))
usb = blocks[0]
for b in blocks[1:]:
    usb = usb.fuse(b)
usb = usb.removeSplitter()
tray = tray.cut(usb)
top = top.cut(usb)

# ------------------------------------------------------------------ button cap
cap_z0 = P.PCB_TOP + 1.8
cap = cyl(0, 0, 0, P.CAP_FLANGE_T, P.CAP_FLANGE_D).fuse(cyl(0, 0, 0, P.H + 0.6 - cap_z0, P.CAP_D))
cap = cap.removeSplitter()

parts = {"case_bottom": tray, "case_top": top, "button_cap": cap}
for name, shp in parts.items():
    shp = shp.removeSplitter()
    assert shp.isValid(), name
    # binary STL, 0.02 mm chord error: smooth curves at a tenth of the ASCII size
    MeshPart.meshFromShape(Shape=shp, LinearDeflection=0.02, AngularDeflection=0.2).write(
        os.path.join(OUT, name + ".stl"))
    print("%-12s volume %.1f cm3  bbox %s" % (name, shp.Volume / 1000, shp.BoundBox))

# assembly STEP (caps placed in their holes)
asm = [tray, top]
for sy in (-1, 1):
    c = cap.copy()
    c.translate(V(P.BTN_X, sy * P.BTN_Y, cap_z0))
    asm.append(c)
Part.makeCompound(asm).exportStep(os.path.join(OUT, "novaband_case.step"))
print("CASE DONE", OUT)
