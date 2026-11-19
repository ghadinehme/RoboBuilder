import cadquery as cq
from bricks.printed import PrintedPart

def part():
 p=PrintedPart('narrow_spring_chassis','Compact spring drive with inner motor mounts, forward battery bridge, leading rollers and high rear anti-tip shoe')
 def box(x,y,z,dx,dy,dz):return cq.Workplane('XY').box(dx,dy,dz).translate((x,y,z))
 p.add(box(20,0,6.4,64,88,3.2))
 p.add(box(68,0,6.4,32,48,3.2))
 for y in [-16,16]:
  p.add(box(28,y,12.8,40,8,9.6))
  for x in [32,16]:p.pin_hole((x,y,13.6),axis='y',length=8)
 p.add(box(32,0,18.4,64,32,3.2))
 for y in [-28,28]:
  p.add(box(80,y,10.4,16,8,11.2));p.pin_hole((80,y,12),axis='y',length=8)
 p.add(box(80,0,6.4,16,64,3.2))
 p.add(cq.Workplane('XZ').polyline([(-40,24),(-12,4.8),(-12,8),(-40,27.2)]).close().extrude(8,both=True))
 p.studs_top([(x,y) for x in range(4,61,8) for y in [-12,-4,4,12]],z=20)
 return p
