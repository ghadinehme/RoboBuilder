You are a robot design engineer: you design both the hardware and its control. Your task: **one robot that crosses as many as possible of the 10 level-1 obstacles** of the brick obstacle benchmark (ramp, gap, bridge, rope, steps, bumps, seesaw, gap-drop, wall, U-turn), the same physical robot on every one. Your score is the number of benches the robot you hand in passes.

## What is different in this task (read `/work/docs/all_in_one.md` for the details)

- **One assembly, one motor program per bench.** The design file has `motor_programs`: `{"ramp": [...], "gap": [...], ...}` instead of one `motor_program`. The hardware is shared; each bench can have its own commands (timing, speeds, which motors run).
- **The structure is 3D printed.** No bricks, beam bricks, beams or plates from the inventory. You may use the inventory's mechanical and electrical parts: gears, axles, pins, connectors, bushes, wheels and tyres, chains and treads, racks, shock absorbers, motors, battery boxes and IR receivers. Everything else (chassis, frames, brackets, arms, wedges, mounts) you design as printed parts: **any number of part types**, up to {copies} copies of each, each fitting the printer's build plate: at most **{max_mm} mm** in every direction, walls of at least {wall} mm (`custom_part.md` explains how; `brick-bench part <script.py>` builds and checks a part and gives you its id).
- **Electrics:** up to two IR receivers and as many motors as they can control: each receiver output drives one motor, or several motors whose plugs stack because they always turn together; a motor that runs at full power the whole run can plug straight into a battery box (`motor_program.md`).
- **Budget:** {sims} simulations and {hours} h for the whole task. Each simulation runs the robot on **one** bench: `brick-bench simulate <file> --bench <name>`.

## How to work: be smart about the order

Do not design 10 robots. Read all 10 benches first (`/work/docs/task.json` has every bench's geometry, start and goal; `benches.md` describes them) and think about what they ask of a robot: traction and torque (ramp, steps, wall, rope), length and support over gaps (gap, gap-drop, bridge), narrow and straight (bridge), turning (U-turn), ground clearance (bumps), and what they forbid. Every bench's start board is 500 mm long (the gap's is 1000 mm): start gap + robot length must fit on it. Pick a concept that could cover many of them, then:

1. Start with one bench (one your concept should pass) and get the robot to pass it.
2. Take the next bench. Before changing anything, write down which features the benches already passed rely on (`/work/notes.md` is a good place) and decide: can the new bench be passed with only a new motor program? With a change that keeps those features? Or does it need a different concept that handles the previous benches and the new one, with some changes or a full redesign?
3. After any hardware change, re-check the benches that passed before (a simulation each): `brick-bench budget` shows which of your simulated files passed which bench. A change that gains one bench and loses two is a loss.
4. Spend simulations where they gain benches. If one bench would need a robot unlike the others, it may be better to skip it and secure the rest.

## Hand-in and scoring

`brick-bench submit <file>` hands in the robot. It is then run on all 10 benches, a plain run plus that bench's nudged runs (1 mm off centre, commands 50 ms late), free; it passes a bench only if all of those pass and the design review finds nothing critical. The hand-in is accepted when your file has passed all 10 benches in your own simulations, or once you have used {min_sims} simulations; the rest of the budget is there if you need it, and you hand in once. A robot that does not fit a bench (for example longer than that bench's start board) fails that bench only; the hand-in itself is not refused for it. Work autonomously; nobody will answer questions. Unused simulations earn nothing: use them while they can still gain benches.

The robot will be built from the real parts and printed parts and run open loop on the real courses, so prefer designs and programs that would repeat reliably.

The rest of `/work/docs/` is as in the single-bench tasks: `rules.md`, `parts.md`, `design_format.md`, `manufacturing_constraints.md`, `motor_program.md`, `simulator.md`, `example_design.json`. Where they speak of one bench, one `motor_program`, bricks for the structure or one printed part type, this task's rules above replace them.
