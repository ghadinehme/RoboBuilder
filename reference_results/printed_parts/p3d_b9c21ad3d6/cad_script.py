import math
import cadquery as cq
from bricks.printed import PrintedPart

RR = 110.0      # hard rim outer radius
RW = 8.0        # rim radial width
TH = 8.0        # disc thickness: local y -8..0 (voxel-aligned)
BOSS = 32.0     # boss local y -8..-40
ROUT = 118.0    # rubber lobe tread radius
# lobe angle (deg), tyre radius -> hole radius = ROUT - r
LOBES = [(0, 31.32), (72, 21.6), (144, 15.2), (216, 21.6), (288, 15.2)]

def part():
    p = PrintedPart("studrim5b_r110", "hard r110 rim + five cross holes for rubber tyre lobes (tread r118); 32 mm hub boss")
    wp = lambda: cq.Workplane("XZ")
    body = wp().circle(RR).circle(RR - RW).extrude(TH)
    body = body.union(wp().circle(20).extrude(TH))
    for a_deg, r in LOBES:
        a = math.radians(a_deg); ux, uz = math.cos(a), math.sin(a); nx, nz = -uz, ux
        rh = ROUT - r
        pts = [(rr * ux + w * nx, rr * uz + w * nz) for (rr, w) in ((12, 6.0), (RR - 2, 6.0), (RR - 2, -6.0), (12, -6.0))]
        body = body.union(wp().polyline(pts).close().extrude(TH))
        body = body.union(wp().center(rh * ux, rh * uz).circle(7.5).extrude(TH))
    body = body.union(wp().workplane(offset=TH).circle(8.0).extrude(BOSS))
    for a_deg, r in LOBES:   # outer bosses (local y 0..8) carrying a round hole on each lobe axis
        a = math.radians(a_deg); rh = ROUT - r
        body = body.union(wp().workplane(offset=-8).center(rh * math.cos(a), rh * math.sin(a)).circle(7.5).extrude(8))
    p.add(body)
    p.axle_hole((0, -20.0, 0), axis="y", length=40)
    for a_deg, r in LOBES:
        a = math.radians(a_deg); rh = ROUT - r
        p.axle_hole((rh * math.cos(a), -4.0, rh * math.sin(a)), axis="y", length=8)
        p.pin_hole((rh * math.cos(a), 4.0, rh * math.sin(a)), axis="y", length=8)
    return p
