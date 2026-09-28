"""
LibreCAD sketch of the Nova-Band pod: an A3 sheet at 2:1 with top, front,
end and section views, dimensions and a title block.

    python hardware/casing/sketch_dxf.py
    "C:/Program Files/LibreCAD/LibreCAD.exe" dxf2pdf -p 420x297 -s 2 -c -o out/novaband_case_sketch.pdf out/novaband_case_sketch.dxf

The DXF is plain R2000 (lines, polylines with bulges, circles, hatches and
dimensions) so it opens and stays editable in LibreCAD. Model units are mm
at 1:1; the 2:1 happens at print time.
"""
import math
import os
import sys

import ezdxf
from ezdxf.enums import TextEntityAlignment

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import case_params as P  # noqa: E402

OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)

doc = ezdxf.new("R2000", setup=True)
doc.units = ezdxf.units.MM
msp = doc.modelspace()
for name, color, lt, lw in (("OUTLINE", 7, "Continuous", 50), ("HIDDEN", 8, "DASHED", 25),
                            ("CENTER", 1, "CENTER", 18), ("BOARD", 5, "DASHED", 18),
                            ("DIM", 3, "Continuous", 18), ("TEXT", 7, "Continuous", 25),
                            ("HATCH", 8, "Continuous", 13), ("FRAME", 7, "Continuous", 50)):
    doc.layers.add(name, color=color, linetype=lt, lineweight=lw)

ds = doc.dimstyles.get("EZDXF")
ds.dxf.dimtxt = 1.6          # 3.2 mm on paper at 2:1
ds.dxf.dimasz = 1.0
ds.dxf.dimexe = 0.6
ds.dxf.dimexo = 0.5
ds.dxf.dimgap = 0.4
ds.dxf.dimdec = 1
ds.dxf.dimclrd = 3
ds.dxf.dimclre = 3
ds.dxf.dimclrt = 7
ds.dxf.dimtad = 1
ds.dxf.dimzin = 8            # 78 not 78.0
# LibreCAD draws dimensions from the HEADER variables, not the style table
for k, v in dict(DIMTXT=1.6, DIMASZ=1.0, DIMEXE=0.6, DIMEXO=0.5, DIMGAP=0.4, DIMDEC=1,
                 DIMTAD=1, DIMZIN=8, DIMSCALE=1.0, DIMCLRD=3, DIMCLRE=3, DIMLUNIT=2, DIMDSEP=46).items():
    doc.header["$" + k] = v


def rr(x0, y0, x1, y1, r, layer="OUTLINE"):
    """Rounded rectangle as a closed LWPOLYLINE (bulge 0.4142 = quarter arc)."""
    r = min(r, (x1 - x0) / 2, (y1 - y0) / 2)
    b = math.tan(math.radians(90) / 4)
    pts = [(x0 + r, y0, 0), (x1 - r, y0, b), (x1, y0 + r, 0), (x1, y1 - r, b),
           (x1 - r, y1, 0), (x0 + r, y1, b), (x0, y1 - r, 0), (x0, y0 + r, b)]
    if r <= 0:
        pts = [(x0, y0, 0), (x1, y0, 0), (x1, y1, 0), (x0, y1, 0)]
    msp.add_lwpolyline(pts, format="xyb", close=True, dxfattribs={"layer": layer})


def poly(pts, layer="OUTLINE", close=True):
    msp.add_lwpolyline(pts, close=close, dxfattribs={"layer": layer})


def line(a, b, layer="OUTLINE"):
    msp.add_line(a, b, dxfattribs={"layer": layer})


def circ(c, d, layer="OUTLINE"):
    msp.add_circle(c, d / 2, dxfattribs={"layer": layer})


def text(s, p, h=1.6, layer="TEXT", align=TextEntityAlignment.LEFT):
    msp.add_text(s, height=h, dxfattribs={"layer": layer}).set_placement(p, align=align)


def dim(p1, p2, base, angle=0, txt=None):
    # the measured value is written as explicit text: LibreCAD's own number
    # formatting drops the decimal separator ("78.00" printed as "7800")
    v = abs(p2[1] - p1[1]) if angle == 90 else abs(p2[0] - p1[0])
    val = ("%.2f" % v).rstrip("0").rstrip(".")
    d = msp.add_linear_dim(base=base, p1=p1, p2=p2, angle=angle, dimstyle="EZDXF",
                           text=(txt or "<>").replace("<>", val), dxfattribs={"layer": "DIM"})
    d.render()


def diam(c, d, ang=45, txt=None):
    dd = msp.add_diameter_dim(center=c, radius=d / 2, angle=ang, dimstyle="EZDXF",
                              text=txt or "<>", dxfattribs={"layer": "DIM"})
    dd.render()


def hatch(pts):
    h = msp.add_hatch(color=8, dxfattribs={"layer": "HATCH"})
    h.set_pattern_fill("ANSI31", scale=0.35)
    h.paths.add_polyline_path(pts, is_closed=True)


def cross(c, s=2.5):
    line((c[0] - s, c[1]), (c[0] + s, c[1]), "CENTER")
    line((c[0], c[1] - s), (c[0], c[1] + s), "CENTER")


hl, hw = P.L / 2, P.W / 2
bx, by = P.BOARD_L / 2 + P.CLEAR, P.BOARD_W / 2 + P.CLEAR
winw = P.WIN_W / 2
usb_z = P.PCB_TOP + P.USB_Z_ABOVE_PCB + P.USB_H / 2

# ================================================================ TOP VIEW
ox, oy = 60.0, 100.0                       # view centre
T = lambda x, y: (ox + x, oy + y)
rr(*T(-hl, -hw), *T(hl, hw), P.R)
rr(*T(-hl + P.EDGE, -hw + P.EDGE), *T(hl - P.EDGE, hw - P.EDGE), P.R - P.EDGE, "HATCH")   # edge round tangent
rr(*T(P.WIN_X0, -winw), *T(P.WIN_X1, winw), P.WIN_R)                                   # window
rr(*T(P.GLASS_X0, -P.GLASS_W / 2), *T(P.GLASS_X1, P.GLASS_W / 2), P.GLASS_R, "BOARD")  # touch glass
a0 = P.ACTIVE_CX - P.ACTIVE_L / 2
rr(*T(a0, -P.ACTIVE_W / 2), *T(a0 + P.ACTIVE_L, P.ACTIVE_W / 2), 0, "BOARD")          # active area
rr(*T(-P.BOARD_L / 2, -P.BOARD_W / 2), *T(P.BOARD_L / 2, P.BOARD_W / 2), 0.5, "BOARD")  # PCB
rr(*T(-P.TUNNEL_L / 2, -hw), *T(P.TUNNEL_L / 2, hw), 0, "HIDDEN")                      # strap tunnel
rr(*T(-hl, -P.USB_CUT_W / 2), *T(-bx + 0.5, P.USB_CUT_W / 2), 0, "HIDDEN")            # USB opening
for sy in (-1, 1):
    circ(T(P.BTN_X, sy * P.BTN_Y), P.BTN_HOLE)
    circ(T(P.BTN_X, sy * P.BTN_Y), P.CAP_D, "HATCH")
    cross(T(P.BTN_X, sy * P.BTN_Y), 2.6)
for sx in (-1, 1):
    for sy in (-1, 1):
        c = T(sx * P.SCREW_X, sy * P.SCREW_Y)
        circ(c, 2.2, "HIDDEN")
        circ(c, P.HEAD_D + 0.3, "HIDDEN")
        cross(c, 3.0)
line(T(-hl - 4, 0), T(hl + 4, 0), "CENTER")
line(T(0, -hw - 4), T(0, hw + 4), "CENTER")
text("ACTIVE AREA 42.7 x 22.7  (320 x 170 px)", T(a0 + 1, P.ACTIVE_W / 2 - 3), 1.1, "BOARD")
text("USB-C", T(-hl + 1.2, -1.5), 1.1, "HIDDEN")
text("STRAP TUNNEL 40 x 2.4 (under)", T(-P.TUNNEL_L / 2 + 1, -hw + 1.2), 1.0, "HIDDEN")
# section marker A-A at x = 10
for s in (-1, 1):
    line(T(10, s * (hw + 2)), T(10, s * (hw + 6)), "OUTLINE")
    text("A", T(11, s * (hw + 5) - 0.8), 2.0)
dim(T(-hl, hw), T(hl, hw), T(0, hw + 9))                                  # 78
dim(T(hl, -hw), T(hl, hw), T(hl + 8, 0), angle=90)                        # 34
dim(T(P.WIN_X0, -winw), T(P.WIN_X1, -winw), T(0, -hw - 6))                # window length
dim(T(P.WIN_X1, -winw), T(P.WIN_X1, winw), T(hl + 3.5, 0), angle=90)      # window width
dim(T(-hl, -hw), T(P.WIN_X0, -winw), T(0, -hw - 11))                      # window from USB end
dim(T(-P.SCREW_X, -P.SCREW_Y), T(P.SCREW_X, -P.SCREW_Y), T(0, -hw - 16))  # 70 screws
dim(T(-P.SCREW_X, -P.SCREW_Y), T(-P.SCREW_X, P.SCREW_Y), T(-hl - 5, 0), angle=90)
dim(T(-P.TUNNEL_L / 2, hw), T(P.TUNNEL_L / 2, hw), T(0, hw + 4.5))        # tunnel
dim(T(P.BTN_X, -P.BTN_Y), T(P.BTN_X, P.BTN_Y), T(-hl - 10, 0), angle=90)
text("TOP VIEW", T(-hl, hw + 14), 2.4)

# ================================================================ FRONT VIEW (from -Y)
fx, fy = 60.0, 42.0
F = lambda x, z: (fx + x, fy + z)
poly([F(-hl, 0), F(hl, 0), F(hl, P.H), F(-hl, P.H)])
line(F(-hl, P.SPLIT), F(hl, P.SPLIT))                                     # joint
rr(*F(-P.TUNNEL_L / 2, P.TUNNEL_Z0), *F(P.TUNNEL_L / 2, P.TUNNEL_Z0 + P.TUNNEL_H), 0)  # tunnel mouth
for sy in (-1, 1):                                                       # cap proud of the lid
    rr(*F(P.BTN_X - P.CAP_D / 2, P.H), *F(P.BTN_X + P.CAP_D / 2, P.H + 0.6), 0)
rr(*F(-P.BOARD_L / 2, P.PCB_Z), *F(P.BOARD_L / 2, P.PCB_TOP), 0, "BOARD")
rr(*F(P.GLASS_X0, P.PCB_TOP), *F(P.GLASS_X1, P.GLASS_TOP), 0, "BOARD")
rr(*F(-hl, usb_z - P.USB_CUT_H / 2), *F(-bx + 0.5, usb_z + P.USB_CUT_H / 2), 0, "HIDDEN")
rr(*F(P.BATT_CX - P.BATT[0] / 2, P.PCB_Z - 0.2 - P.BATT[2]), *F(P.BATT_CX + P.BATT[0] / 2, P.PCB_Z - 0.2), 0, "HIDDEN")
text("LiPo 302530 (opt.)", F(P.BATT_CX - 9, P.PCB_Z - 2.6), 0.9, "HIDDEN")
dim(F(hl, 0), F(hl, P.H), F(hl + 8, 0), angle=90)                         # 15.8
dim(F(hl, 0), F(hl, P.SPLIT), F(hl + 4, 0), angle=90)                     # joint height
dim(F(-P.TUNNEL_L / 2, P.TUNNEL_Z0), F(-P.TUNNEL_L / 2, P.TUNNEL_Z0 + P.TUNNEL_H), F(-P.TUNNEL_L / 2 - 4, 0), angle=90)
dim(F(-hl, 0), F(-hl, P.PCB_Z), F(-hl - 4, 0), angle=90)                  # PCB seat height
text("FRONT VIEW", F(-hl, P.H + 3.5), 2.4)
text("joint: top shell / bottom tray", F(hl - 30, P.SPLIT + 0.5), 1.0)

# ================================================================ END VIEW (from -X, USB side)
ex, ey = 140.0, 42.0
E = lambda y, z: (ex + y, ey + z)
rr(*E(-hw, 0), *E(hw, P.H), 1.2)
line(E(-hw, P.SPLIT), E(hw, P.SPLIT))
# USB stadium opening
w2 = P.USB_CUT_W / 2
rr(*E(-w2, usb_z - P.USB_CUT_H / 2), *E(w2, usb_z + P.USB_CUT_H / 2), P.USB_CUT_R)
line(E(-hw, P.TUNNEL_Z0), E(hw, P.TUNNEL_Z0), "HIDDEN")
line(E(-hw, P.TUNNEL_Z0 + P.TUNNEL_H), E(hw, P.TUNNEL_Z0 + P.TUNNEL_H), "HIDDEN")
line(E(0, -3), E(0, P.H + 3), "CENTER")
dim(E(-w2, usb_z + P.USB_CUT_H / 2), E(w2, usb_z + P.USB_CUT_H / 2), E(0, P.H + 3))
dim(E(w2, usb_z - P.USB_CUT_H / 2), E(w2, usb_z + P.USB_CUT_H / 2), E(hw + 4, 0), angle=90)
dim(E(-hw, 0), E(-hw, usb_z), E(-hw - 4, 0), angle=90)
text("END VIEW (USB-C)", E(-hw, P.H + 8), 2.4)

# ================================================================ SECTION A-A (x = 10)
sx_, sy_ = 140.0, 92.0
S = lambda y, z: (sx_ + y, sy_ + z)
fl = P.TUNNEL_Z0 + P.TUNNEL_H + P.FLOOR
regions = [
    [S(-hw, 0), S(hw, 0), S(hw, P.TUNNEL_Z0), S(-hw, P.TUNNEL_Z0)],
    [S(-hw, P.TUNNEL_Z0 + P.TUNNEL_H), S(hw, P.TUNNEL_Z0 + P.TUNNEL_H), S(hw, P.SPLIT), S(by, P.SPLIT),
     S(by, P.PCB_Z), S(by - P.LEDGE, P.PCB_Z), S(by - P.LEDGE, fl), S(-(by - P.LEDGE), fl),
     S(-(by - P.LEDGE), P.PCB_Z), S(-by, P.PCB_Z), S(-by, P.SPLIT), S(-hw, P.SPLIT)],
]
for s in (-1, 1):
    regions.append([S(s * hw, P.SPLIT), S(s * by, P.SPLIT), S(s * by, P.GLASS_TOP), S(s * winw, P.GLASS_TOP),
                    S(s * winw, P.H), S(s * hw, P.H)])
for reg in regions:
    poly(reg)
    hatch(reg)
rr(*S(-P.BOARD_W / 2, P.PCB_Z), *S(P.BOARD_W / 2, P.PCB_TOP), 0, "BOARD")
rr(*S(-P.GLASS_W / 2, P.GLASS_TOP - 1.1), *S(P.GLASS_W / 2, P.GLASS_TOP), 0, "BOARD")
text("PCB", S(-3, P.PCB_Z + 0.2), 0.9, "BOARD")
text("touch glass", S(-5, P.GLASS_TOP - 0.95), 0.8, "BOARD")
text("strap", S(-3, P.TUNNEL_Z0 + 0.7), 0.9, "HIDDEN")
dim(S(-hw, P.H), S(-winw, P.H), S(0, P.H + 3))                            # wall to window
dim(S(winw, P.GLASS_TOP), S(winw, P.H), S(hw + 4, 0), angle=90)           # lid 1.0
dim(S(winw, P.GLASS_TOP), S(P.GLASS_W / 2, P.GLASS_TOP), S(0, P.GLASS_TOP - 3), txt="lip <>")
text("SECTION A-A", S(-hw, P.H + 8), 2.4)

# ================================================================ BUTTON CAP DETAIL (4:1 feel, drawn 1:1)
cx, cy = 185.0, 100.0
C = lambda x, z: (cx + x, cy + z)
stem = P.H + 0.6 - (P.PCB_TOP + 1.8)
poly([C(-P.CAP_FLANGE_D / 2, 0), C(P.CAP_FLANGE_D / 2, 0), C(P.CAP_FLANGE_D / 2, P.CAP_FLANGE_T),
      C(P.CAP_D / 2, P.CAP_FLANGE_T), C(P.CAP_D / 2, stem), C(-P.CAP_D / 2, stem),
      C(-P.CAP_D / 2, P.CAP_FLANGE_T), C(-P.CAP_FLANGE_D / 2, P.CAP_FLANGE_T)])
line(C(0, -2), C(0, stem + 2), "CENTER")
dim(C(P.CAP_FLANGE_D / 2, 0), C(P.CAP_FLANGE_D / 2, stem), C(P.CAP_FLANGE_D / 2 + 3, 0), angle=90)
dim(C(-P.CAP_D / 2, stem), C(P.CAP_D / 2, stem), C(0, stem + 2.5))
dim(C(-P.CAP_FLANGE_D / 2, 0), C(P.CAP_FLANGE_D / 2, 0), C(0, -2.8))
text("BUTTON CAP x2", C(-5, stem + 7), 2.0)

# ================================================================ notes + title block (paper A3 @ 2:1 = 210 x 148.5 model)
text("NOTES", (8, 26), 1.8)
notes = [
    "1. Units mm. Board values nominal (LILYGO: 62 x 26 x 10) - verify with calipers, edit case_params.py.",
    "2. Print PETG/ASA, 0.2 mm layers, both shells face-down on the joint, no supports.",
    "3. Assembly: board into tray, caps into lid, lid on, 4 x M2 x 8 self-tapping from below.",
    "4. Strap tunnel under the board takes a 38-40 mm band, worn on the upper arm.",
    "5. Clearance 0.35 mm per side around the PCB; lid overlaps the glass by 0.8 mm.",
]
for i, n in enumerate(notes):
    text(n, (8, 23 - i * 2.4), 1.1)
tb_x, tb_y = 140.0, 4.0
rr(tb_x, tb_y, 206.0, tb_y + 22.0, 0, "FRAME")
for yy in (tb_y + 7, tb_y + 14):
    line((tb_x, yy), (206.0, yy), "FRAME")
line((tb_x + 33, tb_y), (tb_x + 33, tb_y + 14), "FRAME")
text("NOVA-BAND pod  |  T-Display-S3 Touch", (tb_x + 1.5, tb_y + 17), 1.6)
text("NB-CASE-01  rev A", (tb_x + 1.5, tb_y + 9.5), 1.4)
text("Scale 2:1 on A3  |  mm", (tb_x + 34.5, tb_y + 9.5), 1.4)
text("Team Nova-Band, SMAN 1 Ska", (tb_x + 1.5, tb_y + 2.5), 1.2)
text("2026-09-28  |  sheet 1/1", (tb_x + 34.5, tb_y + 2.5), 1.4)
rr(2.0, 2.0, 208.0, 146.5, 0, "FRAME")                                     # sheet border

path = os.path.join(OUT, "novaband_case_sketch.dxf")
doc.saveas(path)
print("DXF", path)
