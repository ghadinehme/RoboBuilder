import cadquery as cq
from bricks.printed import PrintedPart
def part():
 p=PrintedPart('deployable_tail','Rounded anti-pitch tail keyed to a servo-geared axle')
 p.add(cq.Workplane('XZ').circle(8).extrude(8,both=True))
 p.add(cq.Workplane('XZ').polyline([(0,-4),(-56,-40.8),(-56,-32.8),(0,4)]).close().extrude(6,both=True))
 p.add(cq.Workplane('XZ').center(-56,-36.8).circle(15.2).extrude(6,both=True))
 p.axle_hole((0,0,0),axis='y',length=16)
 return p
