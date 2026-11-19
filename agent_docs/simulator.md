# The simulator

Your design runs in a rigid-body simulator (MuJoCo 3) whose parameters were **fitted to real runs**: filmed runs of built designs on the real benches, plus bench measurements of the real parts (stud pull-off, peel, pin friction, motor start and climb thresholds, top speeds). It is the same for every level and every agent.

## Engine

- **Time step** 0.5 ms, implicit contact solver.
- **Deterministic:** the same design file gives the same result on every run.
- **Start:** the design is spawned fully assembled at the level's start pose (`start_gap_mm`, `design_format.md`) and settles for 0.5 s with the motors off. Then t = 0 and the motor program starts.

## How the assembly is modelled

- **Rigid groups:** parts joined by cross fits (an axle through a gear, a wheel, a cross hole) form one rigid body with the real masses and inertias.
- **Turning groups:** an axle with everything cross-fitted on it turns in its holes on a hinge. Motor outputs are hinges driven by the motor.
- **Axles slide:** an axle not held at both ends can slide along its holes up to whatever stops it (a bush, a gear or wheel hub against a beam, the axle's end), held only by friction (1.13 N).
- **Studs** are point constraints, one per stud (two across a single row, so a single row can rock). Each stud is checked every step:
  - **pulled straight** above its clutch: 1.2 N per stud on motor, battery-box and receiver housings, 1.32 N between plates and bricks;
  - **levered open** (the other studs of the joint pressed together): up to 1.83× more per stud;
  - **rocked in its tube** (a single row bent about the row): 42.3 N·mm per stud;
  - past its limit a stud **slides out** gradually; once out by its height (1.7 mm) it lets go: the joint is released and the run fails (`breaks`, `rules.md`). Strengths vary ±15 % from stud to stud.
- **Friction pins** turn in their holes against their ridges' friction (4 N·mm); frictionless pins are free pivots.
- **Free wheel axles** (no motor, gear, chain or other coupling drives them) rub in their holes in proportion to the load their wheels carry: friction 0.2 at the 2.4 mm axle radius. Driven axles' losses are inside the motor and gear terms.
- **Gears** mesh by their tooth ratio while engaged:
  - engagement depends on the centre distance (ideal: (z1 + z2) / 2 mm) and the axial overlap of the teeth. A pair built off the ideal distance, or pushed apart under load (the tooth force has a separating part, tan 20°), loses engagement;
  - each mesh carries at most about 120 N of tooth force at full engagement (less for small pinions, and × 0.576 when a double-bevel gear meshes with a spur gear, falling further as such a pair is built off the ideal centre distance); above that the teeth **skip**;
  - meshing double-bevel gears push each other apart along their axles (0.352 of the tooth force);
  - losses: 0.0001 N·m drag per mesh plus 0.387 × tooth force × radius;
  - chains couple their sprockets 1 : 1 by teeth while their spacing holds. A chain skips above a tension of 0.625 N per tooth of its smaller sprocket (16T about 10 N, 24T about 15 N, 40T 25 N), and disengages (it skips or falls off) when its sprockets come more than 3.2 mm (half a link) closer or 1 mm further apart than built, or move more than 9 mm out of line.
- **Mechanisms** (`manufacturing_constraints.md`):
  - **idler gears** (round bore) turn on their own hinge about their axle and pass the drive between the gears they mesh;
  - **worm:** the worm turns the gear 1 : z; the gear cannot turn the worm (friction on the worm shaft of 1.25 × the tooth torque on it, so about 45 % of the worm's torque reaches the teeth, before the mesh losses below); the tooth force acts along the worm's axle;
  - **knob wheels** push at 9 mm from their axles;
  - **rack slides:** the moving side slides on its guides along the rack, coupled to the pinion at z × 3.2 mm per turn; the coupling skips like a spur mesh of that pinion; it stops at its travel ends; running off the pinion fails the run (`broke`);
  - **differential:** the case turns on the output axis, its ring meshes like a 28T double bevel, and the outputs share its turn (ω_left + ω_right = 2 ω_case) with equal torque;
  - **CV joint:** the ball is held in its cup and the two shafts turn 1 : 1;
  - **shock absorbers:** the rod end slides along the shock's axis against preload + rate × compression, with hard stops at full length and full stroke and light damping;
  - **treads:** rollers along the bottom run at the tread's outer radius (every 6.4 mm), turning at the belt speed (sprocket rate × pitch radius); both sprockets turn together; the links are hard plastic: they grip like ABS on the boards (μ 0.42); the links' mass rides on the rollers;
  - **chains** add their links' mass (0.09 g each), half on each sprocket;
  - **pullback motor:** held until t = 0, then torque 0.05 N·m × (unwound fraction left) × (1 − ω / 600 rpm), freewheeling when turned faster;
  - **servo:** after 0.12 s it drives towards its angle at up to 13 rad/s with up to 0.10 N·m, stops within 1° (or after 0.25 s blocked) and then holds only by gearbox friction (0.25 × 0.10 N·m).
- **Motors** (M, L, XL): torque = stall × (level / 7)^0.874 − back-EMF; the back-EMF term scales with (level / 7)^0.394 (the output floats between pulses, so low levels lose torque but keep speed). Fitted values: M motor stall 0.0972 N·m, L motor 0.158 N·m (the XL scales from the M by its rating: 0.259 N·m), M no-load 50 rad/s (the nominal ratings are in `motor_program.md`). Gearbox friction: 0.253 of stall to start from rest, 0.14 running. Commands act 35 ms after they are sent. `"brake"` shorts the motor, `0` floats it.
- **Shared supply:** all driven motors share one supply resistance (battery box, receiver and leads: 0.394 of a motor's winding resistance), so the supply voltage drops with their total current. Near no-load speed this costs little; motors held near stall together lose a large part of their torque.
- **Leads:** each motor and the receiver hang on flexible cables to their plugs. A cable pulled taut pulls its plug off (above 12 N) and that motor stops.
- **Tyres:** rubber tyres grip with a soft contact, μ = 0.82 on the boards, 0.738 on the sloped ramp board and 0.57 on the printed bump rods, for the 32020c01 tyre; other tyres scale by (their measured friction in `parts.md` / 1.38)^0.109. Hard parts (ABS) slide with μ = 0.42 on the boards (measured) and 0.4 on each other.

## The courses

- The benches are rigid and static at the real builds' dimensions (`benches.md`), except two parts that move: the seesaw plank turns on its axle, and the ramp board (0.15 kg) hangs on a hinge at the plateau edge with its foot resting on the floor, so it can lift and swing. The bump rods are the printed plates' rods (lengths and positions as printed).
- Every bench starts with a flat approach board, and the whole vehicle starts on it (its length: `design_format.md`, `task.json` `start.approach_board_mm`).

## What it does not model

- the battery running down over a run;
- flexing of long beams and plates (joints flex, parts do not);
- wear, dust and the variation between two builds of the same design beyond the stud spread.

## Parameters

| parameter | value | meaning |
|---|---|---|
| `m_stall_nm` | 0.0972 | M motor stall torque [N·m] |
| `l_stall_nm` | 0.158 | L motor stall torque [N·m] |
| `m_no_load_rad_s` | 50 | M no-load speed [rad/s] |
| `level_exp` / `pwm_beta` | 0.874 / 0.394 | level → torque and back-EMF scaling |
| `motor_static` / `motor_friction` | 0.253 / 0.14 | gearbox friction, fraction of stall |
| `supply_r` | 0.394 | shared battery-box resistance / one motor's winding resistance |
| `stud_pull_n` / `stud_pull_brick_n` | 1.2 / 1.32 | stud clutch [N] |
| `stud_peel_k` / `stud_rock_nmm` | 1.83 / 42.3 | levered-open factor; rocking limit [N·mm] |
| `mesh_cap_n` / `mesh_mixed_k` / `mesh_axial_k` | 120 / 0.576 / 0.352 | gear mesh limits |
| `mu_tyre_floor` / `mu_tyre_ramp` / `mu_tyre_rod` | 0.82 / 0.738 / 0.57 | tyre friction (32020c01) on the boards, the ramp board, the bump rods |
| `tyre_mu_exp` | 0.109 | per-tyre friction exponent (reference 1.38) |
| `mu_abs` / `mu_board` | 0.4 / 0.42 | hard-part friction |
| `axle_slide_fric_n` | 1.13 | axial friction holding a sliding axle [N] |
| `axle_load_fric_m` | 4.8e-4 | free wheel axle: bearing friction torque per newton of wheel load [m] (0.2 × 2.4 mm) |
| `plug_pull_n` | 12 | lead plug pull-off [N] |
| `chain_cap_n_per_tooth` | 0.625 | chain skip tension per tooth of the smaller sprocket [N] |
| `chain_link_mass_g` | 0.09 | chain link mass [g] |
| `worm_lock_k` | 1.25 | worm shaft friction / tooth torque on it (≥ 1: self-locking) |
| `knob_r_mm` | 9 | knob wheel contact radius [mm] |
| `servo_torque_nm` / `servo_w0_rad_s` / `servo_dead_s` | 0.10 / 13.1 / 0.12 | servo drive torque, speed, dead time |
| `pullback_stall_nm` / `pullback_turns` | 0.05 / 10 | pullback torque fully wound, turns of a full wind |
