# Rules

## The task

Cross your level (`task.json`; all benches: `benches.md`) with the owner's inventory (`parts.md`). You design the **assembly** (parts, poses and connections: a vehicle, with any mechanisms or tools it needs) and its **motor program** (timed motor commands), in one JSON file (`design_format.md`). It is checked by a static validator, run in a physics simulator (`simulator.md`), then built from the real parts and run on the real course with the same commands, open loop, with no sensors (weigh real-world repeatability as the task prompt says).

## What counts as a pass

A run passes when the vehicle reaches the goal region in `task.json` (every part past the obstacle; on the bumps, see below) and then, for the next 5 s, stays upright and in one piece while it is still in it. The goal region is everything past the obstacle (on the U-turn: the second lane), and reaching it is what counts: driving on, or leaving the region afterwards, does not fail the run. The run's time is the moment it reached the goal; the 5 s are not counted, and the time limit does not cut them short.

A run fails when the vehicle:
- **falls** below the fail height (`task.json`);
- **touches the floor below the course** (gap, bridge, rope, gap-drop, U-turn, seesaw): legs or skids on that floor are no crossing, and the seesaw must be crossed on the plank;
- **flips** more than 75° (for 0.5 s), or, after reaching the goal, tilts more than 30° from its start attitude for more than 0.3 s;
- **breaks:** any stud joint comes apart (a stud pulled out of its tube: the run fails at once), or a part moves more than 15 mm from its place on the chassis. Mechanisms may move: a rigid group turning on an axle or pivot pin (a leg, an arm, a bogie) is checked against its pivot, and fails if a member leaves it or it slides more than 15 mm off its axle;
- **gets stuck:** no forward progress for the level's stuck window (`task.json`);
- **leaves the lane:** on every bench the chassis must stay within `lane_half_width_m` of the course centreline (`task.json`);
- **on the wall or the bumps, also** which must be crossed over the top, not around. Wall: any part leaving the lane fails. Bumps: while over the bump field every wheel must stay within the span of the rods across the lane, ±5 mm (`task.json`: `params.rods_y_span_m`, and each rod in `shapes`), other parts may step up to 20 mm outside the plates, no further, and the chassis must stay over them; the bumps are crossed when half the vehicle (the middle of its length) is past the end of the bump line; the lane rules end once the vehicle has crossed, and driving on afterwards is fine;
- **runs out of time:** it has not reached the goal within the level's run time limit (`task.json`, `benches.md`; e.g. 30 s). This is the simulated run's clock, not your working time.

## When a design is accepted

`brick-bench submit <file> --notes "..."` accepts a design when:
1. that exact file passed a `brick-bench simulate` run;
2. it passes the **nudged runs** (free): the vehicle **1 mm off the centreline**, and every motor command after the first one firing **50 ms later**. The simulator is deterministic: these catch a design that passes only by a hair, so give it margin;
3. the design review finds nothing critical (`manufacturing_constraints.md`).

Otherwise submit says why; keep iterating. Accepted designs are copied to `/work/accepted/`. After an acceptance, end your turn; further requests may follow.

**Do not give up early; always end with a submission.** The task ends when a design is accepted or your budget is used up: stopping early counts as failing, and unused simulations earn nothing. A best attempt is refused while you still have simulations left (unless less than 30 min remain). If nothing has passed once your simulations are used up, run `brick-bench submit --best-attempt <file>` on the simulated file with the highest `max_progress`. It is recorded with its progress (no nudged runs), not as a pass; a design accepted later replaces it. If you never submit, the harness records your furthest simulated design.

## Hard constraints (the validator enforces them; details in `manufacturing_constraints.md`)

- **Inventory:** only parts in `parts.md`, at most the owned count of each.
- **A real assembly:** every part joins the rest through a real connection (studs, a pin, an axle in a hole, a cross fit); no part passes through another; studs land on anti-studs; other parts clear the studs.
- **Start:** you choose `start_gap_mm` (vehicle front to the obstacle's start line); the whole vehicle must stand on the approach board (`design_format.md`).
- **Chains:** at most 2 chain loops (3711 chain drives and chain tracks together) per design.
- **Electrics:** an IR receiver (58123c01) on board; at least one motor (how many, and which drive, is up to you); every lead reaches its plug; every battery box connector stays uncovered, with room for its plugs (`motor_program.md`).
- **Open loop:** timed commands only; no sensor, position or angle triggers.
- **Buildable as designed:** no simulator artefacts (parts passing through each other, exploding joints), nothing launched faster than its drive could move it.

## Tools

- Run `validate` on every candidate; any `studs:` or `overlap:` error is a broken build.
- A simulation result gives the failure, `max_progress`, the time, released studs, gear meshes, leads and the executed commands (`motor_program_log`). Run files are kept in `_sims/`, simulated designs in `_simulated/`.

## What is recorded; memory

Passing first; then each accepted design's mass, pieces and crossing time, and the simulations, time and tokens you used. At the end you write `/work/lessons.md` (what failed and why, what worked, the design rules you learned). Your tasks at the next levels start with it, your accepted designs and their results in `/work/memory/` (read-only).
