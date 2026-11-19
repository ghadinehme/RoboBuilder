import cadquery as cq
from bricks.printed import PrintedPart

def part():
 p=PrintedPart('pin_mounted_transfer_arch','Rigid deck/rope bearing arch with a four-pin L-motor mount, positive shaft stop and a stiff top bar; mirrored copies serve four wheel stations.')
 p.add(cq.Workplane('XY').box(20,24,32,centered=(True,True,False)).translate((50,12,8)))
 p.add(cq.Workplane('XZ').center(48,31.32).circle(5.5).circle(2.45).extrude(1.6).translate((0,25.6,0)))
 p.add(cq.Workplane('XZ').polyline([(44,40),(56,40),(56,60.8),(80,80),(68,80),(44,64)]).close().extrude(4,both=True).translate((0,4,0)))
 p.add(cq.Workplane('XY').box(15,8,9.6).translate((71.5,11,78.4)))
 p.add(cq.Workplane('XY').box(8,44.5,31.2).translate((93,14.25,95.6)))
 p.add(cq.Workplane('XY').box(48,8,6.4).translate((72,-4,112)))
 p.add(cq.Workplane('XY').box(8,8,16.8).translate((48,-4,103.6)))
 p.add(cq.Workplane('XZ').center(48,95.2).circle(4.4).extrude(4,both=True).translate((0,-4,0)))
 face=cq.Workplane('XZ').center(76.4,95.2).polyline([(-16,0),(0,-16),(16,0),(0,16)]).close().extrude(8).translate((0,15,0))
 p.add(face)
 p.cut(cq.Workplane('XZ').center(76.4,95.2).rect(8,8).extrude(8).translate((0,15,0)))
 p.add(cq.Workplane('XY').box(24,8,16).translate((80.4,32.5,95.2)))
 # Support the crown close to both faces, avoiding a long cantilevered ABS axle.
 p.add(cq.Workplane('XY').box(56,8,6.4).translate((68,28.5,112)))
 p.add(cq.Workplane('XY').box(8,8,16.8).translate((48,28.5,103.6)))
 p.add(cq.Workplane('XZ').center(48,95.2).circle(4.4).extrude(4,both=True).translate((0,28.5,0)))
 p.pin_hole((48,28.5,95.2),axis='y',length=8)
 for x,y,z,length in [(48,12,15.2,24),(56,4,31.2,8),(48,12,31.32,24),(48,-4,95.2,8),(68.4,11,95.2,8),(84.4,11,95.2,8),(76.4,11,87.2,8),(76.4,11,103.2,8)]:p.pin_hole((x,y,z),axis='y',length=length)
 return p
