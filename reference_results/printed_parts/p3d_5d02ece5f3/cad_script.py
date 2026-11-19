import cadquery as cq
from bricks.printed import PrintedPart
R=95; W=8.0; TB=1.2; WEB=1.2; WH=5; NS=5; SW=2.4; SY=3; HR=7.0
def part():
    p=PrintedPart("rimwheel","T-section rim wheel")
    p.add(cq.Workplane("XZ").circle(R).circle(R-TB).extrude(W/2,both=True))
    p.add(cq.Workplane("XZ").circle(R-TB+0.2).circle(R-TB-WH).extrude(WEB/2,both=True))
    p.add(cq.Workplane("XZ").circle(HR).extrude(8,both=True))
    for i in range(NS):
        a=360.0/NS*i+18
        p.add(cq.Workplane("XY").box(R-TB-WH/2-6,SY,SW,centered=(False,True,True)).translate((6,0,0)).rotate((0,0,0),(0,1,0),a))
    p.axle_hole((0,0,0),axis="y",length=16)
    return p
