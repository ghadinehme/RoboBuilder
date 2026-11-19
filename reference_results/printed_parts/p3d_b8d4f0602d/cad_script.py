import cadquery as cq
from bricks.printed import PrintedPart
def part():
 p=PrintedPart('central_receiver_shelf','Rearward receiver shelf on sixteen studs of the existing forward bracket')
 p.add(cq.Workplane('XY').box(72,32,6.4).translate((36,-24,99.2)))
 p.sockets_bottom([(x,y) for x in [44,52,60,68] for y in [-36,-28,-20,-12]],z=96)
 p.studs_top([(x,y) for x in [4,12,20,28] for y in [-36,-28,-20,-12]],z=102.4)
 return p
