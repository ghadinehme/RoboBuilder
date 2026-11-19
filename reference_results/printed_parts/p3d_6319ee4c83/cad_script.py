import cadquery as cq
from bricks.printed import PrintedPart

def part():
 p=PrintedPart('cross125_hook','Four 125mm I-section legs with transverse feet; 1.2mm PLA webs and flanges')
 body=cq.Workplane('XZ').circle(8).extrude(4,both=True)
 for a in (45,135,225,315):
  arm=cq.Workplane('XY').box(117.4,1.2,8).translate((58.7,0,0))
  for z in (-3.4,3.4):
   arm=arm.union(cq.Workplane('XY').box(117.4,8,1.2).translate((58.7,0,z)))
  foot=cq.Workplane('XY').box(8,8,32).translate((121,0,0))
  foot=foot.cut(cq.Workplane('XY').box(5.6,5.6,34).translate((121,0,0)))
  arm=arm.union(foot)
  body=body.union(arm.rotate((0,0,0),(0,1,0),a))
 p.add(body);p.axle_hole((0,0,0),axis='y',length=8)
 return p
