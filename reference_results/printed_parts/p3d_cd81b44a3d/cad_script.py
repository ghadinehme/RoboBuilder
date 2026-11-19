import cadquery as cq,math
from bricks.printed import PrintedPart

def part():
 p=PrintedPart('front_climb_wheel','90 mm radius narrow spoked climbing wheel, balanced rim and six spokes')
 b=cq.Workplane('XZ').circle(90).circle(82).extrude(8)
 b=b.union(cq.Workplane('XZ').circle(10).extrude(8))
 for a in range(0,360,60):
  t=math.radians(a);x,z=86*math.cos(t),86*math.sin(t);nx,nz=-4*math.sin(t),4*math.cos(t)
  b=b.union(cq.Workplane('XZ').polyline([(nx,nz),(x+nx,z+nz),(x-nx,z-nz),(-nx,-nz)]).close().extrude(8))
 p.add(b);p.axle_hole((0,-4,0),axis='y',length=8)
 return p
