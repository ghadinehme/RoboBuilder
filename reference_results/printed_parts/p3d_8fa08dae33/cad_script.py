import cadquery as cq
from bricks.printed import PrintedPart

def part():
 p=PrintedPart('cross_step_medium','Four diagonal legs catch the top edge of a tall wall; print flat on side with perimeters along each leg.')
 # Broad diagonal beams, clipped to 248 mm square; 8 mm extrusion.
 a=cq.Workplane('XZ').rect(340,16).extrude(3,both=True).rotate((0,0,0),(0,1,0),45)
 b=cq.Workplane('XZ').rect(340,16).extrude(3,both=True).rotate((0,0,0),(0,1,0),-45)
 clip=cq.Workplane('XY').box(248,8,248)
 body=a.union(b).translate((0,1,0)).intersect(clip).union(cq.Workplane('XZ').circle(14).extrude(4,both=True))
 p.add(body.translate((0,-4,0)));p.axle_hole((0,-4,0),axis='y',length=8)
 return p
