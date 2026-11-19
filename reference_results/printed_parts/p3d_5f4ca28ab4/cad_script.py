import cadquery as cq
from bricks.printed import PrintedPart

def part():
 p=PrintedPart('stilt_I_beam_small_boss','Light stilt root: full-width axle and pin bosses, 1.3 mm web/flanges; 12 mm deep I-section resists drive-plane bending')
 b=cq.Workplane('XY').box(14,8,8).translate((3,4,0))
 b=b.union(cq.Workplane('XZ').circle(5).extrude(8).translate((0,8,0)))
 b=b.union(cq.Workplane('XY').box(228,1.3,9.4).translate((122,4,0)))
 for zz in [-5.35,5.35]:b=b.union(cq.Workplane('XY').box(228,6,1.3).translate((122,4,zz)))
 for xx in [208,232]:b=b.union(cq.Workplane('XZ').circle(4).extrude(8).translate((xx,8,0)))
 p.add(b);p.axle_hole((0,4,0),axis='y',length=8)
 for xx in [208,232]:p.pin_hole((xx,4,0),axis='y',length=8)
 return p
