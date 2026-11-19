import cadquery as cq
from bricks.printed import PrintedPart
L=256.0; H=19.2
def part():
    p = PrintedPart("jackbar9", "rigid 1x32 jack bar: 3743 racks on its studs; rear column (both sides) carries the locked foot axle; side lug at the front end is the extension stop; two underside notches")
    body = cq.Workplane("XY").box(L, 8.0, H, centered=(False, False, False))
    col = cq.Workplane("XY").box(8.0, 24.0, H, centered=(False, False, False)).translate((0, -8.0, 0))
    lug = cq.Workplane("XY").box(8.0, 8.0, 8.0, centered=(False, False, False)).translate((L-8.0, 8.0, 8.0))
    solid = body.union(col).union(lug)
    for xn in (88.0, 168.0):
        solid = solid.cut(cq.Workplane("XY").box(8.0, 8.0, 8.0, centered=(False, False, False)).translate((xn, 0, 0)))
    p.add(solid)
    p.studs_top([(4+8*i, 4.0) for i in range(32)], z=H)
    for y in (4.0, 12.0):
        p.axle_hole((4.0, y, 5.6), axis="y", length=8)
    for y in (-4.0,):
        p.pin_hole((4.0, y, 5.6), axis="y", length=8)
    return p
