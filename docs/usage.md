# Usage

## Repository layout

```
robobuilder/            the package
  core/                 design library: parts, inventory, design format, validator rules, design review, courses
  sim/                  the learned simulator (MuJoCo): csim.py, run.py, params/learned.json, params/initial.json,
                        geom/ (visual meshes, drawing only)
  printed/              the custom printed part: CadQuery build (sandboxed), printability checks, physical model
  harness/              tasks, phases and budgets, tool broker, sessions, memory between levels, the run
  agents/               adapters: Claude Code, Codex, Gemini CLI, and a generic adapter for any CLI
  agent_lib/            the design library as agents import it (`import bricks`)
  agent_cli.py          `brick-bench`, the only tool an agent calls (inside its sandbox)
  courses.py validate.py simulate.py scoring.py real.py cli.py
agent_docs/             the prompt texts and documents the agents receive
reference_results/      the four reference agents: per-task results, accepted designs, printed parts, All-in-one robots
real_world/             building the courses, printing, the IR bridge firmware, the controller, running and filming a
                        real crossing; inventory.md lists every part with its catalogue number, to buy the parts
docs/                   this guide and the benchmark's rules and scoring
scripts/                smoke test, printed-part export, controller export
tests/                  fast tests and the self-test that reproduces the reference verdicts
```

## Install

Linux, Python 3.12. Install with `pip install -e .` (editable: the documents and reference results are read from the
repository).

```bash
git clone https://github.com/ghadinehme/RoboBuilder && cd RoboBuilder
python3.12 -m venv .venv && . .venv/bin/activate
pip install -e ".[test]"
```

On Debian / Ubuntu, `python3.12 -m venv` needs the `python3.12-venv` package; without root, `uv venv --seed --python
/usr/bin/python3.12 .venv` makes the same environment (a uv-managed Python is not visible inside the agents' sandbox).

All Python dependencies are pinned in `pyproject.toml` (MuJoCo 3.12.0, NumPy 2.5.3, CadQuery 2.5.2, ...). Videos and
contact sheets use `ffmpeg` from the PATH, else the static binary of `imageio-ffmpeg`. Running agents needs
[bubblewrap](https://github.com/containers/bubblewrap) (`bwrap`) for their sandbox and the agent CLI you evaluate.
The simulator renders offscreen with `MUJOCO_GL=egl` (set by default); use `MUJOCO_GL=osmesa` on a machine without a
GPU.

Check the install (validator, one simulation, the reference leaderboard, fast tests):

```bash
scripts/smoke_test.sh            # builds its own fresh venv
pytest -q tests/test_basic.py    # or just the fast tests in this one
```

## Command line

```bash
robobuilder courses                                   # the 10 obstacles and their 3 levels
robobuilder task gap 2                                # a level as the agent sees it (JSON)
robobuilder validate agent_docs/example_design.json ramp 1
robobuilder simulate reference_results/designs/opus-5.5/ramp_L1/cross.json ramp 1 --video
robobuilder check reference_results/designs/opus-5.5/ramp_L1/cross.json ramp 1   # the official verdict
robobuilder score                                     # the leaderboard
```

`simulate` prints the verdict (`passed`, `failure`, `max_progress`, `time_s`, broken joints, gear meshes, leads) and
writes `_sims/<run>/` next to the design (result.json, the follow and overview videos with `--video` and a 12-frame
contact sheet of each). A design with a printed part needs its spec: `--printed <spec.json>`. `--params` runs another
simulator parameter file (e.g. `robobuilder/sim/params/initial.json`, the estimates before learning).

## Running a model

```bash
robobuilder run --agent claude-code --model claude-opus-5-5 --run-dir runs/opus     # Claude Code
robobuilder run --agent codex --model gpt-6.1-sol --run-dir runs/sol                 # Codex
robobuilder run --agent gemini-cli --model <model> --run-dir runs/gemini             # Gemini CLI
```

Options: `--effort medium` (the paper's setting), `--levels 1,2,3`, `--benches ramp,gap`, `--tasks
cross,light,fast,all_in_one`, `--parallel 10` (tasks at a time), `--force` (rerun tasks that already have an outcome).
Simulations run on the same machine (`RB_MAX_PARALLEL_SIMS`, default half the CPUs per process; `RB_SIM_SLOTS_DIR` +
`RB_SIM_SLOTS` share slots between several runs). Each simulation also has a wall-time limit of 900 s (`CSIM_WALL_S`,
as in the paper): a run cut by it fails, so do not oversubscribe the CPUs. A full run is about 4,000 simulations of one
to several minutes each, so plan a machine with many cores. The CLI must be installed and logged in on the host; its
login file is mapped into the sandbox. A run is resumable: a task with an `outcome.json` is not run again; a task cut
by a usage limit is rerun when you relaunch the same command.

Outputs: `<run dir>/{cross,light,fast}/<obstacle>_L<level>/` (outcome.json, transcript.jsonl, the workspace with every
simulated design, accepted designs, printed parts), `<run dir>/all_in_one/`, `<run dir>/memory/`. Score it with
`robobuilder score <run dir> --name <name>` (see [benchmark.md](benchmark.md#score)).

`tests/fake_agent.py` is a scripted stand-in for an agent CLI that exercises the whole harness (sandbox, broker,
`brick-bench`, phases, memory, Light / Fast sessions, scoring) without a model; its docstring has the command.

## Adding a model

Any coding-agent CLI that runs headless in a shell works through the generic adapter. Give it a command template;
`{prompt_file}` is the request text written to `/work/.prompt.md`:

```bash
robobuilder run --agent generic --model my-model --run-dir runs/my-model \
  --command "mycli --model {model} --cwd {workdir} --prompt-file {prompt_file}" \
  --resume "mycli --model {model} --resume {session} --prompt-file {prompt_file}" \
  --session-regex '"session_id": "([^"]+)"' \
  --token-parser my_module:parse_tokens \
  --bind /opt/mycli --path /opt/mycli/bin --login .mycli/credentials.json --name mycli
```

- `--resume` (optional) continues the session for the follow-up requests (Cross+Print and the lessons turn); without
  it each request starts a new session that is told to continue from its files in `/work`.
- `--session-regex` (optional) finds the session id in the CLI's output.
- `--token-parser` (optional) is `module:function`; the function maps one JSON event of the CLI's output to token
  increments `{"input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens", "thinking_tokens"}`.
- `--bind` / `--path` make the CLI's install visible in the sandbox; `--login` maps login files under `~`; `--env
  KEY=VALUE` sets variables (for example an API key) inside the sandbox.

For a tighter integration, subclass `robobuilder.agents.CLIAgent` (see `ClaudeCode` and `Codex`): `command(prompt,
resume)` returns the argv, `parse(event)` reads the session id and usage from each JSON line, `runtime_binds()` and
`login_files` describe what the sandbox needs; register it in `robobuilder.agents.AGENTS`.

## Real-world tests

[`real_world/README.md`](../real_world/README.md): building the courses, printing the course parts and an agent's
printed part, the IR emitter and bridge, `python -m robobuilder.real` (wiring and the timed program of a design),
the browser [controller](../real_world/controller/README.md), filming and reporting a crossing.
