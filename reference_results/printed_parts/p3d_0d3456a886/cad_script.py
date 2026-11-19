import cadquery as cq
from bricks.printed import PrintedPart
def part():
 p=PrintedPart('large_nose_extension','Raised driven nose for seesaw entry; pinned to main chassis')
 for y in [-20,20]:
  p.add(cq.Workplane('XY').box(12,8,16).translate((122,y,83)))
  p.add(cq.Workplane('XY').box(8,8,69).translate((120,y,61.5)))
  for z in [31,39]:p.pin_hole((120,y,z),axis='x',length=8)
  p.add(cq.Workplane('XY').box(64,8,4).translate((88,y,94)))
 p.add(cq.Workplane('XY').box(32,32,4).translate((56,-24,94)))
 for y in [-28,28]:p.add(cq.Workplane('XY').box(8,8,56).translate((124,y,103)))
 p.add(cq.Workplane('XY').box(8,64,4).translate((124,0,133)))
 for y in [-36,36]:
  p.add(cq.Workplane('XY').box(78,8,40).translate((157,y,95)))
  p.pin_hole((180,y,79),axis='y',length=8)
 p.add(cq.Workplane('XY').box(24,56,8).translate((180,-60,71)))
 p.add(cq.Workplane('XY').box(24,8,48).translate((180,-84,91)))
 for x,z in [(172,103),(188,103),(180,111),(180,103),(180,79)]:p.pin_hole((x,-84,z),axis='y',length=8)
 p.studs_top([(x,y) for x in [44,52,60,68] for y in [-36,-28,-20,-12]],z=96)
 return p
