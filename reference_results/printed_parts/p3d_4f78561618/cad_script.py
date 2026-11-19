import cadquery as cq
from bricks.printed import PrintedPart

def part():
 p=PrintedPart('balanced_flat_front_frame','Half of long eight wheel rubber rover, central support wheels, pin-mounted XL drives, elevated belly and receiver pads')
 body=cq.Workplane('XY').box(56,112,4).translate((28,0,67.6))
 body=body.union(cq.Workplane('XY').box(8,96,4).translate((4,0,67.6)))
 for y in [-44,44]:
  body=body.union(cq.Workplane('XY').box(8,8,28).translate((4,y,75.6)))
  body=body.union(cq.Workplane('XY').box(164,8,6).translate((82,y,67.6)))
  body=body.union(cq.Workplane('XY').box(14,8,102).translate((152,y,75)))
  p.pin_hole((152,y,90),axis='y',length=8)
  p.pin_hole((4,y,67.6),axis='x',length=8)
  p.pin_hole((4,y,83.6),axis='x',length=8)
 p.pin_hole((152,-44,114),axis='y',length=8)
 body=body.union(cq.Workplane('XY').box(8,64,62).translate((126,-72,95)))
 for yy in [-60,-100]:p.pin_hole((126,yy,114),axis='x',length=8)
 studs=[]
 studs += [(x,y) for x in [20,28,36,44] for y in [-84,-76,-68,-60]]
 p.studs_top(studs,z=69.6)
 for yy in [-36,36]:
  body=body.union(cq.Workplane('XY').box(14,8,41.28).translate((0,yy,44.96)))
  p.pin_hole((0,yy,31.32),axis='y',length=8)
 body=body.union(cq.Workplane('XY').box(34,8,6).translate((169,-44,67.6)))
 body=body.union(cq.Workplane('XY').box(8,24,66).translate((182,-52,93)))
 p.pin_hole((182,-60,114),axis='x',length=8)

 # Receiver pad, auxiliary L motor base, and the two-stage foot drive.
 body=body.union(cq.Workplane('XY').box(32,40,4).translate((32,-72,67.6)))
 for yy in [-28,28]:
  body=body.union(cq.Workplane('XY').box(36,8,45).translate((50,yy,68.1)))
 body=body.union(cq.Workplane('XY').box(74,64,4).translate((37,78.5,63.6)))
 body=body.cut(cq.Workplane('XY').box(24,56,40).translate((38,76.5,85.6)))
 for xx,yy,zz,hh,cc in [(54,52.5,89.6,28,79.6),(54,100.5,73.6,16,73.6),(22,100.5,89.6,28,79.6)]:
  body=body.union(cq.Workplane('XY').box(8,8,hh).translate((xx,yy,cc)))
  p.pin_hole((xx,yy,zz),axis='x',length=8)
 foot_x=38+(24**2-4.8**2)**0.5
 p.pin_hole((38,28,81.6),axis='y',length=8)
 for yy in [-28,28]:
  p.pin_hole((38,yy,57.6),axis='y',length=8)
  p.pin_hole((foot_x,yy,52.8),axis='y',length=8)
 # Rear stroke stop arrests the foot before it reaches the centre axle.
 body=body.union(cq.Workplane('XY').box(8,16,19.6).translate((foot_x-15,0,59.8)))
 body=body.cut(cq.Workplane('XY').box(48,16,50).translate((38,46,59)))
 body=body.cut(cq.Workplane('XY').box(48,16,60).translate((foot_x,-40,54)))
 body=body.union(cq.Workplane('XY').box(92,8,4).translate((58,-56,67.6)))
 for xx in [16,100]:body=body.union(cq.Workplane('XY').box(8,20,4).translate((xx,-50,67.6)))
 # A low reinforced receiver tray balances the outboard auxiliary drive.
 body=body.union(cq.Workplane('XY').box(80,48,12).translate((30,-76,59.6)))
 p.add(body)
 return p
