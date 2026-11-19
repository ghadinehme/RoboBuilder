import cadquery as cq
from bricks.printed import PrintedPart

def part():
 p=PrintedPart('flat_battery_back_frame','Half of long eight wheel rubber rover, central support wheels, pin-mounted XL drives, elevated belly and receiver pads')
 body=cq.Workplane('XY').box(56,112,4).translate((28,0,67.6))
 body=body.union(cq.Workplane('XY').box(8,96,4).translate((4,0,67.6)))
 for y in [-44,44]:
  body=body.union(cq.Workplane('XY').box(8,8,28).translate((4,y,75.6)))
  body=body.union(cq.Workplane('XY').box(164,8,6).translate((82,y,67.6)))
  body=body.union(cq.Workplane('XY').box(14,8,44).translate((152,y,46.32)))
  p.pin_hole((152,y,31.32),axis='y',length=8)
  p.pin_hole((4,y,67.6),axis='x',length=8)
  p.pin_hole((4,y,83.6),axis='x',length=8)
 p.pin_hole((152,-44,55.32),axis='y',length=8)
 body=body.union(cq.Workplane('XY').box(8,64,24).translate((126,-72,55.32)))
 for yy in [-60,-100]:p.pin_hole((126,yy,55.32),axis='x',length=8)
 studs=[]
 studs += [(x,y) for x in [20,28,36,44] for y in [-52,-44,-36,-28]]
 body=body.union(cq.Workplane('XY').box(24,48,6).translate((80,-56,66.6)))
 studs += [(x,y) for x in [76,84] for y in [-36,-44,-52,-60,-68,-76]]
 p.studs_top(studs,z=69.6)
 body=body.union(cq.Workplane('XY').box(34,8,6).translate((169,-44,67.6)))
 body=body.union(cq.Workplane('XY').box(8,24,24).translate((182,-52,55.32)))
 p.pin_hole((182,-60,55.32),axis='x',length=8)
 p.add(body)
 return p
