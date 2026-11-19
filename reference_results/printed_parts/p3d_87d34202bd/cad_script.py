import sys, os, math; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common5 import *
from bricks.printed import PrintedPart
# Modelled in its own tilted frame: origin at the underside's low front edge, local x up the slope,
# local z normal to it.  Mounted with spin = -ANG so the underside is one flat, exact collision face.
ANG = 40.0
S = (185.0, 19.2)            # world (x, z) of the underside low edge
L, T = 94.0, 6.0

def to_local(px, pz):
    a = math.radians(ANG); dx, dz = px - S[0], pz - S[1]
    return (dx * math.cos(a) + dz * math.sin(a), -dx * math.sin(a) + dz * math.cos(a))

def part():
    p = PrintedPart("plow_plate", "front plow: a flat plate tilted 40 deg; lifts the front over edges and presses the seesaw plank down")
    p.add(box(0.0, L, -40.0, 40.0, 0.0, T))
    for s in (1, -1):
        ylo, yhi = sorted((s * 32.0, s * 40.0))
        p.add(box(-11.0, 10.0, ylo, yhi, 12.0, 37.0))
        p.add(box(0.0, 10.0, ylo, yhi, 0.0, 12.0))
    for x, z in ((168.0, 28.8), (164.0, 44.8)):
        lx, lz = to_local(x, z)
        for s in (1, -1):
            p.pin_hole((round(lx, 3), s * 36.0, round(lz, 3)), axis="y", length=8)
    return p
