import cadquery as cq
from bricks.printed import PrintedPart
def part():
 p=PrintedPart('medium_nose_support_wheel','Driven 112mm spoked nose wheel')
 p.add(cq.Workplane('XZ').circle(56).circle(52).extrude(6,both=True))
 p.add(cq.Workplane('XZ').circle(8).extrude(4,both=True))
 for a in [0,60,120]:p.add(cq.Workplane('XY').box(108,8,4).rotate((0,0,0),(0,1,0),a))
 p.axle_hole((0,0,0),axis='y',length=8)
 return p
