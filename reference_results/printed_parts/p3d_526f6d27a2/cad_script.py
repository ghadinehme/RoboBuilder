import cadquery as cq
from bricks.printed import PrintedPart
def part():
 p=PrintedPart('shaft_coupler','16 mm long axle coupling for two butted stock axles')
 p.add(cq.Workplane('XZ').circle(7).extrude(8,both=True));p.axle_hole((0,0,0),axis='y',length=16)
 return p
