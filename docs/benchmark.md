# The benchmark

## Obstacles, levels and tasks

Ten obstacles, each at three levels that raise the obstacle and tighten the time limit:
`ramp gap bridge rope steps bumps seesaw gap_drop wall u_turn`, levels `1 2 3`. `robobuilder courses` lists them and
`robobuilder task <obstacle> <level>` prints a level as the agent sees it (JSON); `agent_docs/benches.md` lists every
level's dimensions.

| task | goal | budget |
|---|---|---|
| **Cross** | a passing design | 30 simulations, 24 h |
| **Cross+Print** | if Cross failed: a passing design, now with one printed part type (CadQuery, up to 4 copies, 256 mm build volume) | 30 more simulations, 24 h |
| **Light** | the lightest passing design (a fresh session; the passing design counts if nothing lighter is accepted) | 50 simulations |
| **Fast** | the fastest passing design (a fresh session; likewise) | 50 simulations |
| **All-in-one** | one level-1 robot with a printed structure for all ten obstacles, one program per course | 300 simulations, 72 h |

A design is a list of placed parts, connections and a timed, open-loop motor program (`agent_docs/design_format.md`,
`agent_docs/example_design.json`).

## When a design passes

A design **passes** when it validates (owned parts and counts, real joints, gears, chains, electrics, open-loop
program), the design review finds no critical problem, and the plain run and two nudged runs (the robot 1 mm off the
centreline; every motor command after the first 50 ms late) reach the goal within the time limit and stay there
upright and intact for 5 s. `robobuilder check <design> <obstacle> <level>` gives this official verdict.

Rules: every course starts with a start board of 500 mm (1000 mm on the gap), a design has at most two chain loops,
and parts on one cross axle sit at multiples of 90 deg. Some reference designs were accepted before these rules were
final (`reference_results/results.json`, `rules`); `--as-built`, `--no-chain-limit` and `--no-cross-index` on
`validate`, `simulate` and `check` judge a design under those earlier rules.

## Sessions and memory

Cross and Cross+Print run in one agent session; after them the agent writes `lessons.md`, which it receives (read-only,
with its accepted designs) in every task of a higher level. Levels run in order; the ten tasks of a level run in
parallel. Light and Fast run on every task, also where Cross failed (then from scratch). Each agent works in a sandbox
without web access, with `/work/docs/` (the documents in `agent_docs/`) and the `brick-bench` tool; the simulator, the
harness and the reference results are not visible to it.

## Score

```bash
robobuilder score                         # the reference entrants: the paper's main table
robobuilder score runs/my-model --name my-model --json leaderboard.json
```

| column | meaning |
|---|---|
| Cross L1 / L2 / L3 | share of the 10 tasks of a level passed in Cross |
| +Print | share of the 30 tasks passed in Cross or Cross+Print |
| Sims | median simulations until the passing design was accepted (Cross passes) |
| All-in-one sim / real | share of the 10 courses the All-in-one robot passes in simulation / on the real courses (reference entrants) |
| Light mass, Fast time | mean mass (g) / crossing time (s) over the level-1 tasks where every listed entrant has one |
| Light, Fast score | per task, the best value among the listed entrants divided by the entrant's own (0 without a value), summed over the 30 tasks |
| Score | 100 x the mean of (Cross+Print passes) / 30, All-in-one / 10, Light / 30, Fast / 30 |

Light and Fast scores are relative to the entrants listed: adding a model can lower the reference entrants' scores.
Tokens (cache reads not counted; output includes reasoning) and wall hours are printed as information, not ranked.

## Reference results

`reference_results/results.json` holds, for the four reference agents (opus-5.5 and sonnet-5.5 in Claude Code,
gpt-6-astra and gpt-6.1-sol in Codex, all at medium effort), every task's outcome (how it passed, simulations to the
pass, Light mass, Fast time, tokens, wall time) and the All-in-one result; `designs/<agent>/<obstacle>_L<level>/`
holds every accepted design (`cross`, `print`, `light`, `fast`), `printed_parts/` their printed parts (spec,
CadQuery script, visual mesh) and `all_in_one/` the four All-in-one robots.

Re-simulate them and reproduce their verdicts:

```bash
python tests/selftest.py --quick     # one Cross design per obstacle
python tests/selftest.py             # every Cross and Cross+Print design (86)
python tests/selftest.py --all       # also the Light and Fast designs and the All-in-one robots
```

## Simulator

`robobuilder/sim/csim.py` builds each design in MuJoCo: parts are rigid bodies with their own collision geometry and
mass; stud joints are breakable welds that pull out, peel and shear; axles and pins sit in compliant bearings and can
slide; gears mesh through couplings that skip, separate and re-engage; chains skip under load; motors follow a
torque-speed model with IR latency and battery sag; every course has a twin. `params/learned.json` is the learned
simulator used by the benchmark; `params/initial.json` holds the first estimates before fitting (`--params` on
`simulate` and `check`). What the agents are told about the simulator is `agent_docs/simulator.md`.
