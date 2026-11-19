import cadquery as cq
from bricks.printed import PrintedPart

def part():
 p=PrintedPart('two_lobe_climber','Two rounded climbing lobes keyed to a drive axle; small hub and broad blunt feet')
 p.add(cq.Workplane('XZ').circle(10).extrude(4,both=True))
 p.add(cq.Workplane('XZ').box(144,12,8))
 for x in [-72,72]:p.add(cq.Workplane('XZ').center(x,0).circle(8).extrude(4,both=True))
 p.axle_hole((0,0,0),axis='y',length=8)
 return p
