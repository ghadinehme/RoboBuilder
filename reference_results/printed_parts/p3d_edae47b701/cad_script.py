import cadquery as cq
from bricks.printed import PrintedPart
def part():
 p=PrintedPart('pinned_transfer_deck','Battery deck with integral pinned cheeks to carry transfer bending without stud peel')
 p.add(cq.Workplane('XY').box(64,40,3.2).translate((0,0,5.6)))
 p.add(cq.Workplane('XY').box(48,32,3.2).translate((0,36,5.6)))
 for y in [-16,16]:
  p.add(cq.Workplane('XY').box(56,8,12).translate((0,y,-2)))
  for x in [-24,-8,8,24]:p.pin_hole((x,y,0),axis='y',length=8)
 xy=[(x,y) for x in range(-28,29,8) for y in [-8,0,8,16]]
 p.studs_top(xy+[(x,y) for x in [-20,-12,-4,4] for y in [24,32,40,48]],z=7.2)
 p.sockets_bottom([(x,y) for x in range(-28,29,8) for y in [-8,0,8]],z=4)
 return p
