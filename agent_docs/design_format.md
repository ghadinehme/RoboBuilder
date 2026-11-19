# Design format: the design file, frames and the library

How a design is written down and handled. What it must satisfy to be buildable is in `manufacturing_constraints.md`.

## The design file

A design is one JSON file. `example_design.json` is a complete, valid example (a compact 4-wheel car, 20 parts: a M motor on a stack of five 4x4 plates, on 8 studs, drives the rear axle through a 40T and a 24T spur gear 32 mm apart; the IR receiver sits on the battery box beside its power connector). It shows the format; it is not tuned to any level.

```json
{
 "name": "my_car",
 "description": "what it is and why it works",
 "part_set": "inventory",
 "chassis": "rail_l",            // reference body: progress, flip and break checks
 "motor": "drive_motor",         // the main motor (any motor part)
 "battery": "battery",
 "parts": [
  {"name": "rail_l", "part": "2730", "pos_mm": [0, 12, 19.2], "yaw_deg": 0, "spin_deg": 0},
  ...
 ],
 "connections": [
  {"child": "deck", "parent": "rail_l", "kind": "stud", "studs": 6},
  {"child": "rear_axle", "parent": "rail_l", "kind": "hinge"},
  {"child": "wheel_rl", "parent": "rear_axle", "kind": "cross"},
  {"child": "drive_shaft", "parent": "drive_motor", "kind": "motor"},
  {"child": "pin1", "parent": "beam_a", "kind": "pin"}, {"child": "pin1", "parent": "beam_b", "kind": "pin"},
  ...
 ],
 "gear_meshes": [{"gear_a": "pinion", "gear_b": "crown", "teeth_a": 8, "teeth_b": 24}],
 "treads": [],                   // optional mechanism lists (manufacturing_constraints.md): chains, treads,
 "racks": [],                    //   racks, differentials, cv_joints; pullback winding: motor_program.md
 "motor_program": [ ... ],       // motor_program.md
 "start_gap_mm": 40              // optional: where it starts (below)
}
```

Keep `"part_set": "inventory"`.

## Where the vehicle starts: `start_gap_mm`

Every bench has a flat **approach board** before the obstacle: 500 mm (1000 mm on the gap; `task.json` `start.approach_board_mm`); the obstacle starts at x = 0 (the ramp's foot, the first step's face, the edge of the start table over a chasm, the bump plate's edge, the wall's face, the near end of the rope or bridge).
- `start_gap_mm` is the distance from the **front of the vehicle** (its foremost part) to that start line. You choose it.
- The whole vehicle must be on the board: **0 ≤ start_gap_mm** and **start_gap_mm + vehicle length ≤ the board's length** (validated).
- Leave it out to start at the level's default (`task.json`: `start.front_x`, a few centimetres from the obstacle).

## Frames and units

- **Design frame:**
  - x forward (the direction of travel), y left, z up;
  - lengths in **mm**, angles in degrees;
  - the lowest wheel bottoms at z = 0. The harness places the vehicle at the level's start pose.
- **Part pose:** `pos_mm` is the position of the part's origin. The rotation is `yaw_deg` about z, then `spin_deg` about the part's own y axis (quaternion = yaw · spin).
- **Brick grid:**
  - stud pitch 8 mm;
  - a brick is 9.6 mm tall, a plate 3.2 mm;
  - studs rise 1.6 mm above a top face.

| part kind | origin and axes |
|---|---|
| bricks, plates, AAA battery box, IR receiver | top centre of the body (the AAA box's top has studs only along its long edges and at the −x end: its power connector and switch sit in the middle strip; the receiver's origin is at its low front step, its dome rises 22 mm above it). pin holes run along local y, 4 mm below the top face, at x = multiples of 8 mm between the studs |
| AA battery box (59510c01) | centre of its studless 88 × 32 × 56 mm body; pin it on through the 3 + 3 pin holes in each end; power connector pad on top at x = 8…24 mm, switch at x ≈ −8 mm |
| liftarms (studless beams), frames, connectors | centre of the beam; holes along local y at z = 0 |
| axles | centre; axle along local x |
| gears, wheels, bushes | centre; rotation axis local y |
| M motor | on the output axis at the output face; body along local +y (0…48 mm); 2 × 6 anti-studs underneath at z = −12 mm, offset half a stud (x = ±4 mm) |
| L / XL motor, servo | the same output frame; studless: pin them on through the pin holes in their faces |
| pin | centre (the collar); pin along local x, 8 mm into each of its two holes |
| tyred wheels | on the axle axis; rotation axis local y. Some have an off-centre tyre or bore: 32020c01 tyre −13.8…6.2, bore −8…4 |

The exact geometry of every part (studs, anti-studs, holes, pin holes, cross holes, axle lengths, teeth, wheel radius, tyre friction, motor line) is in the library:

```python
from bricks.parts import bench_parts
bp = bench_parts()["3895"]   # title, kind, mass_g, shape, studs_top, studs_bottom, holes, pin_holes, teeth, wheel_radius, tyre_mu, notes
```

## The design library (in `python`)

```python
from bricks.design import Design, DesignPart, DesignConnection, validate, Budget, place
from bricks.parts import bench_parts, inventory_part_set

d = Design.load("example_design.json")              # or build Design(name=..., parts=[...], connections=[...])
d.parts.append(DesignPart("w", "56145c01", (0, 30, 21.6), yaw_deg=0))
rep = validate(d, Budget.for_part_set("inventory"))
print(rep.ok, rep.errors, rep.warnings)
print(rep.stats)                                    # mass, centre of mass, size, clearance, wheelbase, drive, gear ratio,
                                                    # expected speed, stall force, quasi-static capability estimates
P = place(d)                                        # name -> placed part: world position, rotation, axes, bounding box
d.save("candidate.json")
```

- **`rep.stats`** includes quasi-static estimates: max slope, max step, max gap rolled or spanned, minimum plank width, tip angles, and rope hang. They are rough guides to rank ideas; the simulation decides.
- **Generator scripts:** functions of a few parameters (wheel size, wheelbase, gear ratio, arm length, timings…) that place parts on the stud grid and emit the connections; change parameters between runs instead of editing JSON.
