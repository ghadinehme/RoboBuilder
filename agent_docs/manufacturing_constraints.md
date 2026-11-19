# Manufacturing constraints

What a design must satisfy to be buildable from the real parts. The validator (`brick-bench validate`) checks the connections, structure and mechanism rules below and names each violation; the design review flags what would not survive being built and run. The design file itself is described in `design_format.md`.

## Connections

Every part must be joined to the assembly. Declare each joint as a connection:

| kind | what it is | how it is simulated |
|---|---|---|
| `stud` | child pressed on top of, or hung under, the parent; `studs` = number of engaged studs | each stud a point constraint that can be pulled, levered or rocked out (`simulator.md`) |
| `pin` | a pin (child) in a pin hole of the parent. A pin joins two parts (a 3L pin up to three), so declare one `pin` connection per joined part | parts can turn about a single friction pin against its friction (`simulator.md`); frictionless pins (3673) and axle-pins (65249) are free **pivots** |
| `cross` | a gear, wheel, bush, liftarm or connector on an axle through its cross hole | rigid: it turns with the axle |
| `hinge` | an axle turning in a round hole (a beam brick hole, a liftarm or connector pin hole); also a round-bore gear on an axle | revolute joint, light friction |
| `motor` | an axle in a motor output | revolute joint driven by the motor (`motor_program.md`) |
| gear mesh (`gear_meshes`) | two gears whose teeth engage | real tooth contact |

The validator checks the geometry of each connection:
- **`stud`:** the faces touch (±0.3 mm), and the declared studs line up on the 8 mm grid.
- **`hinge`:** the axle lies on a hole's centre line (±0.35 mm), at least 4 mm into it.
- **`cross`:** coaxial (±0.35 mm), with the hub on the axle. Parts held on the same axle through cross holes sit at multiples of 90° to each other: a cross axle allows no other angle.
- **`pin`:** coaxial with a pin hole and at least 4 mm into it. A pair of parts joined by a single pin gets a warning, because it can turn about the pin.
- **`motor`:** the shaft is on the output axis, at least 3 mm inside it and 3 mm sticking out.

**Studs are real.** Studs are not in the collision shapes, so the validator checks them separately:
- A part resting on studs must be stud-connected to that part, and every stud under it must land in its anti-stud grid.
- Any other part (a motor body, a beam, an axle, a battery box) must clear the studs: at least 1.7 mm above the top face.
- The M motor's anti-studs sit half a stud off its body centre.

**No interpenetration.** No two parts may overlap by more than 0.3 mm. Meshing gears, connected pairs and axles through holes are exempt.

**Required structure:**
- the motor and battery box are stud- or pin-connected to the chassis cluster;
- at least one motor drives something that moves the vehicle: wheels, treads, legs or another mechanism;
- all wheels driven by one motor turn the same way at the same speed.

## Gears and mechanisms

- **Spur gears** (module 1): the centre distance is (z1 + z2) / 2 mm, within −0.15 / +0.6 mm.
  - 8T + 24T: 16 mm; 16T + 16T: 16 mm; 8T + 16T: 12 mm; 16T + 24T: 20 mm; 8T + 40T: 24 mm; 24T + 40T: 32 mm; 12T + 20T: 16 mm.
  - The gears must be in one plane (±1 mm), and the train must be consistent (no locked loops).
  - **A double bevel (12T 32270, 20T 32269, 36T 32498) meshing a plain spur gear** is allowed within −0.15 / +0.15 mm of (z1 + z2) / 2; how the simulator treats such a mesh is in `simulator.md`.
- **Worm (4716)** + spur gear:
  - axes at right angles; the gear's centre is z/2 + 4 mm from the worm's axis (16 mm for a 24T);
  - ratio 1 : z;
  - it is **self-locking**: the gear cannot turn the worm, so it holds a position with the motor off (and a floating motor);
  - its tooth force acts along the worm's own axle.
- **Bevel gears:** two equal double bevels (12T 32270, 20T 32269, 36T 32498), or a single bevel (12T 6589, 20T 32198) with a bevel of the same tooth count. A single bevel's toothed face must point towards the point where the two axles cross.
  - The axes are at right angles and intersect, with each gear's centre z/2 mm from the intersection.
  - Ratio 1 : 1.
- **14T / 22T bevels (69762 / 69761):** they mesh only with each other or 14T with 14T, never with other gears.
  - **14T + 22T**, at right angles with the axes intersecting: the 14T's centre is 16 mm from the 22T's axis, and the 22T's centre is 8 mm from the 14T's axis. Ratio 14 : 22.
  - **14T + 14T**, at right angles: each centre 12 mm from the other's axis. Ratio 1 : 1, a shallow mesh.
  - The 22T has a round bore, so it can only be a free-turning idler: its axle may carry nothing else but bushes.
- **Knob cogs (32072):** they mesh only with other knob cogs, 1 : 1. Their knobs push at about 9 mm from the axle, and part of the force acts along the two axles.
  - At right angles, with the axes intersecting: for example 8 mm and 12 mm from each other's axes (not 8 / 8, where the knobs collide).
  - In parallel: centre distance 16.8…20 mm (2 studs is too tight; 2 holes along and 1 brick up = 18.7 mm works).
- **Worm gearbox (6588):** a 2 × 4 housing standing on studs. The worm goes on the lengthwise axle, 7.2 mm above the bottom, and the 24T on the cross axle, 16 mm above it. Ratio 1 : 24, self-locking.
- **Round-bore gears** (16T clutch gears 18946 / 6542b, the 22T 69761) turn freely on their axle: they are idlers, joined by a `hinge`. An idler meshed between two gears passes their drive on (it reverses the sense, not the ratio).
- **Differential (62821b, one-piece, with a 28T bevel ring):** `"differentials": [{"name": "diff", "case": "d", "outputs": ["o1", "o2"], "satellites": ["s1"]}]`.
  - The two outputs are 12T bevels (6589) on the two output axles, and the satellites 1 or 2 more 12T bevels inside. All count as pieces.
  - The case turns on the output axis. Its ring meshes in parallel with a 12T, 20T or 36T double bevel (20, 24 and 32 mm apart), or at right angles with a 12T or 20T bevel.
  - It behaves as an open differential: the two outputs share the case's turn (ω_left + ω_right = 2 ω_case) and get equal torque. This lets the wheels of one axle turn at different speeds in a turn.
  - The 65414 housings in the inventory have no ring gear, so they are plain parts, not differentials.
- **Chain drive (3711, 100 links):** `"chains": [{"name": "chain", "gears": ["g1", "g2"], "links": 25}]` couples two gears (to use the chain as a track on the ground, see Treads).
  - **At most 2 chain loops per design** (chain drives and chain tracks together).
  - It runs between two coplanar spur gears on different axles: 14T, 16T, 24T or 40T (not 8T, not the round-bore clutch gears). Both gears turn the same way, at the ratio z1 : z2.
  - Link pitch 6.4 mm. The links must fit the loop around both gears: from 2 mm shorter than the loop (the links' play takes that up) to at most half a link (3.2 mm) of slack, and the gears must be at least (z1 + z2)/2 + 2 mm apart. The chain's path must be clear.
  - Each link counts as a piece.
- **CV joint (32494 ball + 92906 cup):** `"cv_joints": [{"name": "cv", "ball": "b", "cup": "c"}]`.
  - It joins two axles 1 : 1 through a bend of up to 35° about the ball's centre (the ball stays in its cup, both shafts turn at the same rate and pass the full torque).
  - The ball must sit in the cup (within 0.5 mm).
- **Shock absorbers:** a spring between its two end fittings, which slide along the shock's axis. Pin its ends in with pins; the 9.5L's cylinder end takes an axle through its cross hole. Below its preload it stays at full length; above it, it shortens by (force − preload) / rate, down to its stroke.
  - **Hard 6.5L (731c04, ×6):** pin holes 44 mm apart extended, 8 mm stroke, 1.0 N/mm with 4.7 N preload (12.7 N fully compressed).
  - **Soft 9.5L (2909c03, ×2):** 64 mm extended, 16 mm stroke, 0.4 N/mm with 1.5 N preload.
  - It can be drawn part-compressed: the pin positions set where on its stroke it starts. Parts it links (an arm on a pivot pin, for example) count as a moving mechanism, not a broken build. There is no hydraulic damper: only light friction (0.5 N·s/m hard, 1.5 N·s/m soft), so a bounce dies out slowly.
- **Pivots and linkages:**
  - frictionless pins (3673, 65249) make joints that swing freely;
  - a liftarm cross-fitted on a turning axle is a crank;
  - a link on a pivot pin swings.
- **Servo (99498c01):** a position motor: it turns a part to one of 15 angles (±90° in 7 steps each side) with up to 0.10 N·m, then stops driving and holds the angle only by its gearbox friction (about 0.025 N·m): a heavier load turns it back (`motor_program.md`).
- **Other connectors:**
  - 3-axle hub (57585): a cross hole plus three 1L axle ends at 120°;
  - bent connector with 4 pins (55615);
  - cam (6575): cross holes, an egg-shaped crank;
  - changeover catches (6641, 35188): levers and drums on axles; their gear-shifting function is not simulated;
  - steering arm (57515): pin and cross holes; its tow-ball socket is not used.
- **Treads:** `"treads": [{"name": "left", "sprockets": ["spr_a", "spr_b"], "links": 25}]`. The two sprockets are coplanar, each cross-fitted on its own hinged or driven axle in one rigid chassis, and the links count as pieces. The tread turns both sprockets together (driving either one drives the tread), touches the ground along its whole bottom run at its outer radius, and moves the vehicle at the sprocket's turning rate × its pitch radius (below). The links are hard ABS: on the boards they grip like a hard part (μ 0.42, `simulator.md`), and their mass is carried with the vehicle. There are three kinds:
  - **Narrow (3873 links, ×50, on small 57520 sprockets):** the loop needs links × 6.4 ≥ 2·D + 77.7 mm (D = the sprocket centre distance), with at most one link of slack. That makes two loops of 25 at D = 40 mm. Pitch radius 12.4 mm, outer radius (grouser tips) 15.6 mm, 20.8 mm wide.
  - **Chain track (3711 links, ×100, on two equal 24T or 40T gears, 16T also allowed):** add `"link": "3711"`. A narrow (7.8 mm), hard track: it rides at the gear's chain radius + 2 mm (24T: 14.4 mm, 40T: 22.5 mm; pitch radius 12.4 / 20.5 mm), and the gears count as the wheels on the ground.
  - **Wide (57518 links, ×52, on large 57519 sprockets, ×4):** add `"link": "57518"`. Links are 38.4 mm wide with a 12 mm pitch; the sprocket has 10 teeth and a 19.4 mm pitch radius, and the tread runs at 25 mm radius. The loop needs about 2·D/12 + 10 links (25 links at D = 88 mm), with at most one of slack.
- **Rack slides** (racks 3743, 6630, 87761; tooth pitch 3.2 mm; one pinion turn moves the rack z × 3.2 mm): `"racks": [{"name": "lift", "racks": ["r1", "r2"], "pinion": "p", "guides": ["g1", "g2", "g3"]}]`.
  - Racks are one straight, contiguous bar, in tooth phase, joined by a shared carrier part.
  - The pinion is a spur gear with yaw 0, z/2 mm from the pitch line, on an axle whose bearing is part of the guide frame.
  - The guides are one rigid cluster that touches the rack side's back face and both side faces over ≥ 16 mm each, along the whole travel.
  - Only the slide may link the two sides: no studs, pins or gears across it.
  - The slide moves z × 3.2 mm per pinion turn. Its tooth force skips like a spur mesh of that pinion (about 120 N for 12T and up, less for an 8T).
  - It stops at the first part of the vehicle in its way; a rack that runs off its pinion fails the run.
  - The mesh is reversible: a load on the rack turns the pinion and its motor back.

## Design review

`brick-bench validate` also reviews the design as a manufacturability (DFM) report would (`review`). **Critical** findings block acceptance, even if the design passes in simulation:
- **axial retention:** an axle or pin that can slide out of its holes, or a gear that can slide out of mesh;
- **separable sub-assemblies:** a part held only by studs that all pull off the same way, too weak for its weight, a hard landing or the motor's reaction;
- **pivoting members:** a loaded group (wheels, a motor, a large mass) attached along a single hinge line, so it can swing.

Warnings are reported only: axial play over 1 mm, weak or single-row stud joints, a vehicle joined only through one plate, parts that could not be inserted.
