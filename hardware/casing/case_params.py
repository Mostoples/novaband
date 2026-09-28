"""
Nova-Band prototype pod for the LILYGO T-Display-S3 *Touch* (ESP32-S3R8).
One set of numbers, shared by the LibreCAD sketch (sketch_dxf.py) and the
FreeCAD solid model (case_freecad.py). Units: mm.

Frame: X along the board (USB-C at -X), Y across it, Z up (screen side).
Z = 0 is the underside of the case.

!! Board numbers are nominal (LILYGO lists the Touch board as 62 x 26 x 10 mm).
   Measure your board with calipers and edit the BOARD_* / GLASS_* / BTN_*
   values before printing; everything else follows from them.
"""

# ------------------------------------------------------------ the board
BOARD_L, BOARD_W, BOARD_T = 62.0, 26.0, 1.2        # PCB
BOARD_UNDER = 3.2                                  # tallest part under the PCB (JST connectors)
GLASS_ABOVE = 5.6                                  # PCB top -> touch-glass top
GLASS_X0, GLASS_X1 = -19.5, 29.5                   # touch glass extent along X
GLASS_W, GLASS_R = 25.2, 4.0                       # glass width and corner radius
ACTIVE_CX, ACTIVE_L, ACTIVE_W = 4.3, 42.7, 22.7    # 320 x 170 px @ 0.1335 mm
BTN_X, BTN_Y = -26.6, 9.6                          # the two tact switches (top-press), at +/-Y
USB_W, USB_H, USB_Z_ABOVE_PCB = 9.0, 3.2, 0.0      # USB-C receptacle on the PCB top, at -X

# ------------------------------------------------------------ the case
CLEAR = 0.35                                       # board-to-case clearance per side
WALL = 2.0
L, W, R = 78.0, 34.0, 7.0                          # outline and plan corner radius
EDGE = 1.6                                         # top edge rounding
FLOOR = 1.2                                        # floor above the strap tunnel
TUNNEL_Z0, TUNNEL_H = 1.0, 2.4                     # strap tunnel (runs along Y, under the board)
TUNNEL_L = 40.0                                    # fits straps up to 38-40 mm
PCB_Z = TUNNEL_Z0 + TUNNEL_H + FLOOR + BOARD_UNDER + 0.2   # underside of the PCB
PCB_TOP = PCB_Z + BOARD_T
GLASS_TOP = PCB_TOP + GLASS_ABOVE
LID = 1.0                                          # bezel thickness over the glass
H = GLASS_TOP + LID                                # overall height
SPLIT = PCB_TOP                                    # top shell / bottom tray joint
LIP = 0.8                                          # bezel overlap onto the glass edge
WIN_X0, WIN_X1 = GLASS_X0 + LIP, GLASS_X1 - LIP
WIN_W, WIN_R = GLASS_W - 2 * LIP, GLASS_R - LIP
LEDGE = 1.0                                        # PCB rests on ledges along the long edges
BTN_HOLE = 3.4                                     # button cap bore
CAP_D, CAP_FLANGE_D, CAP_FLANGE_T = 3.0, 4.6, 0.6
USB_CUT_W, USB_CUT_H, USB_CUT_R = 11.6, 5.8, 2.4   # USB-C plug overmould clearance
SCREW_X, SCREW_Y = 35.0, 11.0                      # 4 x M2 x 8 (self-tapping) at the ends
SCREW_D, BOSS_D, HEAD_D, HEAD_T = 1.7, 5.0, 3.9, 1.4
BATT = (26.0, 21.0, 3.2)                           # optional 302530 LiPo, under the right half
BATT_CX = 14.0

if __name__ == "__main__":
    for k, v in sorted(globals().items()):
        if k.isupper():
            print("%-18s %s" % (k, v))
