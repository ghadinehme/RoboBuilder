import cadquery as cq
from bricks.printed import PrintedPart

def part():
 p=PrintedPart('battery_socket_and_pad_cage','Pinned battery hold-down with 0.2 mm roof pad clearance between studs; open connector and switch window')
 b=cq.Workplane('XY').box(72,40,8.4).translate((0,0,4.2))
 b=b.cut(cq.Workplane('XY').box(50,16,16).translate((-1,0,5.2)))
 b=b.cut(cq.Workplane('XY').box(20,20,16).translate((-16,0,5.2)))
 b=b.cut(cq.Workplane('XY').box(32,31,2.2).translate((-16,0,1.1)))
 b=b.union(cq.Workplane('XY').box(4,12,2.4).translate((-30,0,1.2)))
 for y in [-44,44]:
  b=b.union(cq.Workplane('XY').box(8,32,6.4).translate((4,y/44*32,5.2)))
  b=b.union(cq.Workplane('XY').box(8,8,37.2).translate((4,y,-10.2)))
  p.pin_hole((4,y,-24.4),axis='x',length=8)
 for sx in [-1,1]:
  for sy in [-1,1]:
   b=b.union(cq.Workplane('XY').box(4,8,44.8).translate((sx*34.2,sy*12,-14.0)))
   b=b.union(cq.Workplane('XY').box(8,4,44.8).translate((sx*28,sy*18.2,-14.0)))
 p.sockets_bottom([(x,y) for x in [4,12,20,28] for y in [-12,12]]+[(28,-4),(28,4)],z=0)
 p.add(b)
 return p
