import cadquery as cq
from bricks.printed import PrintedPart

def part():
 p=PrintedPart('vault_gear_cradle','Universal bearing cage and landing truss: common shaft seats, motor clearance, positive stop lugs, and a relieved underside for use above studded landing rails.')
 def box(x0,x1,y0,y1,z0,z1):
  p.add(cq.Workplane('XY').box(x1-x0,y1-y0,z1-z0).translate(((x0+x1)/2,(y0+y1)/2,(z0+z1)/2)))
 # twin base rails, connected across their rear end outside the rotating shaft and gears
 for y in [-24,24]:
  box(-72,56,y-4,y+4,-4,4)
  for x in range(-64,49,8):
   if abs(x)!=24:p.pin_hole((x,y,0),axis='y',length=8)
 box(-72,-64,-44,48,-4,4)
 # bearing uprights, common rigid bed joins all three shaft centres
 box(-8,8,-44,-36,0,104)

 for z in [32,56]:p.pin_hole((0,-40,z),axis='y',length=8)
 for y in [-16,0]:
  box(-8,8,y-4,y+4,-4,36)
  box(-68,8,y-4,y+4,-4,4)
  for z in [0,32]:p.pin_hole((0,y,z),axis='y',length=8)
 # motor mount on both sides, pins engage motor's side holes along X
 for x in [-24.3,24.3]:
  box(x-4,x+4,-4,48,44,68)
  for y in [4,44]:p.pin_hole((x,y,56),axis='x',length=8)
  box(x-4,x+4,20,28,0,48)
 box(-28.3,28.3,40,48,78,86)
 for x in [-24.3,24.3]:box(x-4,x+4,40,48,64,82)
 box(-28,28,-44,-36,96,104)
 box(-28.3,-20.3,-40,48,78,104)
 # braces at extreme rear keep the motor clear
 # Low, integral stop bearings: shaft catches the rotor after it has passed vertical.
 for y in [-24,24]:
  box(44,52,y-4,y+4,-12,4)
  p.pin_hole((48,y,-8),axis='y',length=8)
 # Relief under the rear crossbar clears studs when a copy braces the landing rails.
 for ya,yb in [(-44,-28),(-20,20),(28,48)]:
  p.cut(cq.Workplane('XY').box(8,yb-ya,4).translate((-68,(ya+yb)/2,-2)))
 return p
