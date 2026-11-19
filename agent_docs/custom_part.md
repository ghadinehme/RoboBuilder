# Your custom printed part

In this extension you may add **one custom part type**, 3D-printed in PLA, to your design: up to **4 copies** of it. It is designed in code (CadQuery), connects to the bricks only through the interfaces below, and is printed from the STL the harness exports.

## Limits

- **One part type**, one solid piece, used at most 4 times in a design.
- **Size:** fits the printer's build volume: 256 × 256 × 256 mm.
- **Walls:** at least 1.2 mm thick everywhere (the check measures the local thickness over the whole surface).
- **Overhangs:** reported, not refused: faces pointing down steeper than 45° need print supports in every orientation tried; prefer shapes that print without them.
- **Material model:** PLA 1.24 g/cm³, printed with a 1.2 mm solid shell and 35 % infill inside: mass = 1.24 g/cm³ × (shell volume + 0.35 × the rest). The harness computes the mass and centre of mass from your solid.
- **Strength:** printed studs and sockets hold like brick studs; pins and axles in its holes behave like in a beam. The part itself is rigid.

## The script

Write a Python file in `/work` (use paths relative to `/work`) that defines `part()`:

```python
import cadquery as cq
from bricks.printed import PrintedPart, STUD, PLATE, BRICK

def part():
    p = PrintedPart("example_block", "what it is for")
    body = cq.Workplane("XZ").polyline([(-16, -9.6), (40, -9.6), (24, 0), (-16, 0)]).close().extrude(8, both=True)
    p.add(body)                                                         # any CadQuery solids: add(), cut()
    p.studs_top([(x, y) for x in (-12, -4, 4, 12, 20) for y in (-4, 4)], z=0.0)   # studs on its top face
    p.sockets_bottom([(-12, -4), (-12, 4)], z=-9.6)                     # anti-stud sockets in its bottom face
    p.pin_hole((4, 0, -5.6), axis="y", length=16)                       # round pin hole(s)
    p.axle_hole((-4, 0, -5.6), axis="y", length=16)                     # cross hole(s)
    return p
```

Then `brick-bench part <script.py>`. It runs the script, adds the studs and cuts the sockets and holes, checks the part, exports the STL (`/work/printed_parts/<id>.stl`) and registers it. It answers with the **part id** (`p3d_...`), its mass, size, the wall and overhang checks, and how its collision shape was approximated. Use the id in your design as any other part: `{"name": "shoe", "part": "p3d_...", "pos_mm": [...], "yaw_deg": 0, "spin_deg": 0}`. Its frame is your CAD frame (mm, z up). `brick-bench validate` and the simulator know it; to use it in your own Python (`validate`, `place`, stats), load it first: `from bricks.printed import load_part; load_part("/work/printed_parts/<id>.json")`.

A revised part gets a **new id**; designs that use the old id keep the old geometry. A design may use only one printed part id.

## Interfaces (the only ways it connects)

| helper | what it makes | connect with |
|---|---|---|
| `studs_top(xy, z)` | studs (4.8 × 1.7 mm) on the top face at height `z` | `stud`: a brick or plate pressed on it (the part is the parent or the child, as for bricks) |
| `sockets_bottom(xy, z)` | anti-stud sockets (4.9 mm, 2 mm deep) in the bottom face at `z` | `stud`: the part pressed onto the studs below it |
| `pin_hole(centre, axis, length)` | round pin hole(s), 4.9 mm | `pin`: a pin in it; `hinge`: an axle turning in it |
| `axle_hole(centre, axis, length)` | cross hole(s) | `cross`: the part on an axle turns with it (the axle is the parent) |

- Stud and socket positions lie on one 8 mm grid; one stud face (one height) on top and one socket face underneath; the top face sits a multiple of the plate height (3.2 mm) above the socket face.
- Holes are along the part's x, y or z axis, in 8 mm segments: a 16 mm hole is two holes, as on a beam. Each needs a closed wall around it.
- The connection checks are the same as for brick parts (`manufacturing_constraints.md`): faces touching and studs on the grid, a pin or axle coaxial and at least 4 mm in, and so on.

Without the helpers you may return `(solid, INTERFACES)` from `part()`, with `INTERFACES = {"studs_top": {"z": 0, "xy": [[x, y], ...]}, "studs_bottom": {...}, "pin_holes": [[x, y, z, "y"], ...], "axle_holes": [...]}`; the solid must then really have those features (the check looks for the studs, the empty sockets and holes and the material around them).

## How it is simulated

The solid is voxelised and merged into a few dozen boxes for collisions (studs left out, as for every brick part); the faces on the stud grid are exact, curved surfaces are approximated to about a voxel (1 mm for a part up to 48 mm, coarser for larger parts; `collision` in the answer). Its mass and centre of mass are the printed part's.
