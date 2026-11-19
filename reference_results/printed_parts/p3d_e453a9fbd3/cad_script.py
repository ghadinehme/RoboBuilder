import math
import cadquery as cq
from bricks.printed import PrintedPart
ARM=94.8; BEND=51.6
def part():
    p=PrintedPart("elbow_crank","rigid elbow crank: cross hole at the hub, arm to the knee, then 3 pin holes along the leg")
    ux,uz=math.cos(math.radians(BEND)),math.sin(math.radians(BEND))
    nx,nz=-uz,ux
    w=6.0
    E=(ARM+ux*36,uz*36)
    pts=[(-7,-w),(ARM+w*math.tan(math.radians(BEND/2)),-w),(E[0]-nx*-w+0,E[1]+nz*-w*-1*-1)]
    # outline: lower edge along arm, around the leg section, back along upper edge
    a=[(-7,-w),(ARM+w*math.tan(math.radians(BEND/2)),-w),(E[0]+uz*w,E[1]-ux*w),(E[0]-uz*w,E[1]+ux*w),
       (ARM-w*math.tan(math.radians(BEND/2)),w),(-7,w)]
    body=cq.Workplane("XZ").polyline(a).close().extrude(4,both=True)
    p.add(body)
    p.axle_hole((0,0,0),axis="y",length=8)
    for k in (0,2,4):
        p.pin_hole((ARM+ux*8*k,0,uz*8*k),axis="y",length=8)
    return p
