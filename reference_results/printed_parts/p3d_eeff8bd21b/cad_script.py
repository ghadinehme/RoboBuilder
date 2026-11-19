import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common5 import *
from bricks.printed import PrintedPart

def part():
    p = PrintedPart("end_frame8", "end frame: chain-driven end axle; front edge kept inside the tyre circle")
    for s in (1, -1):
        ylo, yhi = sorted((s * 24.0, s * 32.0))
        p.add(prism_xz([(116, 35.2), (138, 35.2), (146, 16.0), (168, 16.0), (176, 26.4), (174, 40.0), (168, 54.4), (116, 54.4)], ylo, yhi))
        olo, ohi = sorted((s * 32.0, s * 40.0))
        p.add(box(92, 124, olo, ohi, 35.2, 54.4))
    p.add(box(116, 132, -24, 24, 41.6, 54.4))
    for s in (1, -1):
        p.pin_hole((EX, s * AX_Y, EZ), axis="y", length=8)
        p.pin_hole((EX, s * AX_Y, EZ + 12.0), axis="y", length=8)
        p.pin_hole((EX, s * AX_Y, EZ + 24.0), axis="y", length=8)
        for x, z in ((168.0, 28.8), (164.0, 44.8)):
            p.pin_hole((x, s * AX_Y, z), axis="y", length=8)
        for x in JOIN_X:
            for z in JOIN_Z:
                p.pin_hole((x, s * 36.0, z), axis="y", length=8)
    return p
