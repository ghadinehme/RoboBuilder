import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common5 import *
from bricks.printed import PrintedPart

def part():
    p = PrintedPart("mid_frame6", "central frame: two driven middle axles with L motors, low decks (rear: battery + receiver)")
    for s in (1, -1):
        ylo, yhi = sorted((s * 24.0, s * 32.0))
        pts = [(-116, 35.2), (-56, 35.2), (-44, 16), (44, 16), (56, 35.2), (116, 35.2),
               (116, 54.4), (-64, 54.4), (-64, 41.6), (-100, 41.6), (-100, 54.4), (-116, 54.4)]
        p.add(prism_xz(pts, ylo, yhi))
    for sx in (1, -1):
        x0, x1 = sorted((sx * 68.0, sx * 116.0))
        p.add(box(x0, x1, -32, 32, 35.2, 41.6))
    for s in (1, -1):
        for x in (MX, -MX):
            p.pin_hole((x, s * AX_Y, MZ), axis="y", length=8)
        for x in JOIN_X:
            for z in JOIN_Z:
                p.pin_hole((x, s * AX_Y, z), axis="y", length=8)
                p.pin_hole((-x, s * AX_Y, z), axis="y", length=8)
    for sx, sy in ((1, -1), (-1, 1)):
        for dx, dz in ((-8, 0), (8, 0), (0, 8)):
            p.pin_hole((sx * MX + dx, sy * AX_Y, MZ + dz), axis="y", length=8)
    studs = [(x, y) for x in (-96, -88, -80, -72) for y in (-28, -20, -12, -4, 4, 12, 20, 28)]
    p.studs_top(studs, z=41.6)
    return p
