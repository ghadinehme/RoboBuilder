import cadquery as cq
from bricks.printed import PrintedPart
def part():
 p=PrintedPart('tail_actuator_mount','Pinned five-to-one servo mount for deployable anti-pitch tail')
 p.add(cq.Workplane('XY').box(16,48,16).translate((-124,0,35)))
 for y in [-20,20]:
  for z in [31,39]:p.pin_hole((-120,y,z),axis='x',length=8)
  p.add(cq.Workplane('XY').box(28,8,8).translate((-134,y,35)))
  p.add(cq.Workplane('XY').box(8,8,57).translate((-144,y,59.5)))
  p.pin_hole((-144,y,80),axis='y',length=8)
 p.add(cq.Workplane('XY').box(32,8,64).translate((-144,28,104)))
 for x,z in [(-144,80),(-144,104),(-152,112),(-136,112),(-144,128)]:p.pin_hole((x,28,z),axis='y',length=8)
 return p
