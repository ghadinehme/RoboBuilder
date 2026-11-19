import cadquery as cq
from bricks.printed import PrintedPart

def part():
 p=PrintedPart('rear_corner_bearing','Rear axle bearing lifts tyre3.2mm and moves it8mm forward; two pin anchors on original rear rails')
 body=cq.Workplane('XZ').polyline([(-148,11.2),(-124,11.2),(-124,19.2),(-132,22.4),(-140,22.4),(-148,19.2)]).close().extrude(4,both=True)
 p.add(body)
 for x,z in [(-144,15.2),(-128,15.2),(-136,18.4)]:p.pin_hole((x,0,z),axis='y',length=8)
 return p
