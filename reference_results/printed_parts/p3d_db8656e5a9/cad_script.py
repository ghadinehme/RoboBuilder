import cadquery as cq, math
from bricks.printed import PrintedPart
RT=132.0; W=8.0; T=3.2; N=8
def part():
    p=PrintedPart("star8L","8 blade spokes, reach 136 mm, light")
    body=cq.Workplane("XZ").circle(16).extrude(W/2,both=True)
    for i in range(N):
        a=math.radians(22.5+360.0/N*i)
        c,s=math.cos(a),math.sin(a)
        def P(r,w): return (r*c-w*s, r*s+w*c)
        pts=[P(10,-8),P(RT,-3.5),P(RT,3.5),P(10,8)]
        body=body.union(cq.Workplane("XZ").polyline(pts).close().extrude(T/2,both=True))
    body=body.intersect(cq.Workplane("XY").box(255,W,255)).translate((0,-4,0))
    p.add(body)
    p.axle_hole((0,-4,0),axis="y",length=8)
    return p
