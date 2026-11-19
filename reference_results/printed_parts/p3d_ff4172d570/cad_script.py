import os, sys, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cadquery as cq
from bricks.printed import PrintedPart
cfg = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "cfg12.json")))
DX = cfg["DX"]; W = cfg["W"]; ROLL = cfg.get("roll", 0); PAD = cfg.get("pad", 0); SWL = cfg.get("sw", 0);  XM = cfg.get("xm", 112); AZR = cfg.get("azr", 30.2)
AZ = 31.32
CD = cfg.get("cd", 26.0)
DZ = math.sqrt(CD**2 - DX**2)
ZM = AZ + DZ
TOP = ZM - 12.0
T = cfg.get("t", 4.8)
BOT = TOP - T
YE = 36.0

def box(x0, x1, y0, y1, z0, z1):
    return cq.Workplane("XY").box(x1-x0, y1-y0, z1-z0, centered=False).translate((x0, y0, z0))

ROWS4 = (-12, -4, 4, 12)
ROWSM = (36, 28, 20, 12, 4, -4)
ROWSM2 = (36, 28, 20, 4, -4)

def part():
    p = PrintedPart("body12", "single-piece 2-axle chassis")
    x0, x1 = -DX-8, W+8
    if ROLL:
        p.add(box(x0, XM-17, -24, 24, BOT, TOP)); p.add(box(XM+17, x1, -24, 24, BOT, TOP))
        for sg in (1, -1):
            ya, yb = (9.5, 24) if sg > 0 else (-24, -9.5)
            p.add(box(XM-17, XM+17, ya, yb, BOT, TOP))
            ya, yb = (9.5, 17.5) if sg > 0 else (-17.5, -9.5)
            p.add(box(XM-8, XM+8, ya, yb, AZR-8, BOT))
            p.pin_hole((XM, sg*13.5, AZR), axis="y", length=8)
    else:
        p.add(box(x0, x1, -24, 24, BOT, TOP))
    p.add(box(x0, 8, -40, 40, BOT, TOP))
    p.add(box(W-DX-8, W+8, -40, 40, BOT, TOP))
    for ax in (0, W):
        for s in (1, -1):
            y0, y1 = (32, 40) if s > 0 else (-40, -32)
            p.add(box(ax-8, ax+8, y0, y1, AZ-8, BOT))
            p.pin_hole((ax, s*YE, AZ), axis="y", length=8)
    if SWL:
        for ax in (0, W):
            for (ya, yb) in ((8, 16), (-16, -8)):
                p.cut(box(ax-16, ax+16, ya, yb, BOT-1, TOP+1))
    if PAD:
        hb = BOT - PAD
        ch = hb  # 45 deg chamfer
        pts = [(XM-12, PAD), (XM+12, PAD), (XM+12+ch, BOT), (XM-12-ch, BOT)]
        pad = cq.Workplane("XZ").polyline(pts).close().extrude(12, both=True)
        p.add(pad)
    ph = (-DX-4) % 8
    studs = set()
    for mx in (-DX, W-DX):
        for x in (mx-4, mx+4):
            for y in (ROWSM2 if SWL else ROWSM):
                studs.add((round(x,3), y))
    # spine studs on the grid phase ph
    xs = [x for x in range(-64, 400) if (x - ph) % 8 == 0 and 12 <= x <= W-20]
    for x in xs:
        for y in ROWS4:
            if ROLL and abs(y) < 9 and abs(x-XM) < 21: continue
            if SWL and abs(y) > 8 and (abs(x) < 20 or abs(x-W) < 20): continue
            studs.add((float(x), float(y)))
    p.studs_top(sorted(studs), z=TOP)
    return p
