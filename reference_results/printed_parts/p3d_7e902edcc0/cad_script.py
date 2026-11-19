import cadquery as cq
from bricks.printed import PrintedPart
def part():
 p=PrintedPart('dual_battery_drive_frame','Twin bearing rails with pinned L drive motor mounts and balanced battery deck')
 for y in [-20,20]:p.add(cq.Workplane('XY').box(232,8,16).translate((0,y,35)))
 p.add(cq.Workplane('XY').box(64,176,4).translate((0,24,41)))
 for x in [-96,96,-48,56]:
  for y in [-20,20]:p.pin_hole((x,y,31),axis='y',length=8)
 for sg in [-1,1]:
  for y in [-20,20]:
   for z in [31,39]:p.pin_hole((sg*112,y,z),axis='x',length=8)
   p.add(cq.Workplane('XY').box(8,8,20).translate((sg*80,y,53)))
  p.add(cq.Workplane('XY').box(8,48,8).translate((sg*80,0,59)))
  for y in [20,-28]:
   p.add(cq.Workplane('XY').box(8,8,32).translate((sg*112,y,55)))
   for z in [47,63]:p.pin_hole((sg*112,y,z),axis='x',length=8)
  p.add(cq.Workplane('XY').box(8,16,16).translate((sg*112,-24,39)))
  p.cut(cq.Workplane('XY').box(24,56,8).translate((sg*96,-4,43)))
 p.cut(cq.Workplane('XZ').center(-48,31).circle(24).extrude(14,both=True))
 p.add(cq.Workplane('XY').box(8,32,4).translate((36,-48,41)))
 p.cut(cq.Workplane('XZ').center(-48,31).circle(25).extrude(8,both=True).translate((0,-40,0)))
 p.studs_top([(x,y) for x in range(-28,29,8) for y in [84,92,100,108]] + [(x,y) for x in range(-20,37,8) for y in [-60,-52,-44,-36]],z=43)
 return p
