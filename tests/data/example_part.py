import cadquery as cq
from bricks.printed import PrintedPart


def part():
    p = PrintedPart("example_block", "a wedge with studs, sockets, a pin hole and a cross hole")
    body = cq.Workplane("XZ").polyline([(-16, -9.6), (40, -9.6), (24, 0), (-16, 0)]).close().extrude(8, both=True)
    p.add(body)
    p.studs_top([(x, y) for x in (-12, -4, 4, 12, 20) for y in (-4, 4)], z=0.0)
    p.sockets_bottom([(-12, -4), (-12, 4)], z=-9.6)
    p.pin_hole((4, 0, -5.6), axis="y", length=16)
    p.axle_hole((-4, 0, -5.6), axis="y", length=16)
    return p
