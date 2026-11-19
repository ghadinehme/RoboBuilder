# The All-in-one task: details

## The design file
As in `design_format.md`, with `motor_programs` (a dict: bench name -> program, same format as `motor_program`) in place of `motor_program`. A bench without an entry cannot be simulated or scored. `start_gap_mm` is shared: choose one that is valid on every bench you attempt (`brick-bench validate` checks each bench).

## Tools
- `brick-bench validate <file>`: checks the assembly with each bench's program on each bench's rules, plus the design review. Free.
- `brick-bench simulate <file> --bench <name>`: one simulation on that bench (counts against the budget). The result says which benches this exact file has passed so far (`this_file_passes`).
- `brick-bench budget`: simulations and time left, and per bench the simulated files that passed it.
- `brick-bench part <script.py>`: a printed part (any number of types).
- `brick-bench submit <file> --notes "..."`: the hand-in (see the prompt).

## Allowed parts
From the inventory: kinds gear, axle, pin, connector, bush, wheel, rack, shock, differential, chain and tread links, motor, battery, receiver. Not allowed: everything in the `parts.md` sections "beam bricks, liftarms and frames" and "Bricks and plates" (`brick-bench validate` names any such part). Printed parts: any number of types, up to the stated copies each, each fitting the stated size per side.

## Passing a bench
As in `rules.md` for that bench at level 1, on the robot's program for that bench: a plain run and the bench's nudged runs must all pass, and the design review must find nothing critical.
