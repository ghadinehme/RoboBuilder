import cadquery as cq
from bricks.printed import PrintedPart

def part():
 p=PrintedPart('fork_lifting_foot110','Two narrow lifting toes straddling the centre drive chain; 25:1 auxiliary drive folds them under the chassis')
 b=cq.Workplane('XZ').circle(4.5).extrude(12,both=True)
 for y in [-7,7]:
  leg=cq.Workplane('XZ').rect(110,8).extrude(2,both=True).translate((55,y,0))
  toe=cq.Workplane('XZ').center(110,0).circle(4.5).extrude(2,both=True).translate((0,y,0))
  b=b.union(leg).union(toe)
 p.add(b);p.axle_hole((0,0,0),axis='y',length=24)
 return p
