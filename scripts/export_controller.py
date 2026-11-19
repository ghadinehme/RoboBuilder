"""Export designs for the real-world controller (real_world/controller/index.html): one experiment file per call, with
each design's wiring, start position, notes and timed IR program, built with the same runner as
``python -m robobuilder.real`` (robobuilder.real.schedule), so the controller sends exactly what the CLI player sends.

    python scripts/export_controller.py reference [--levels 1] [--agents opus-5.5 ...] [--no-all-in-one] [--name NAME]
    python scripts/export_controller.py run <run dir> [--levels 1,2,3] [--name NAME] [--label LABEL]
    python scripts/export_controller.py design <design.json> <bench> <level> [--printed spec.json ...] [--name NAME]

``reference``: the reference agents' passing designs (Cross, or Cross+Print) of the chosen levels and their All-in-one
robots (one program per course). ``run``: the passing designs and the All-in-one robot of your own run
(``robobuilder run --run-dir``). ``design``: a single design file (an All-in-one design with ``motor_programs`` gives
one program per course; pass ``all`` as the bench).

The file goes to real_world/controller/experiments/<name>.js (``--out`` for another folder) and is added to the
folder's index.js, so the controller lists it on the next reload. A single file can also be added from the page
(Add an experiment file)."""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF = os.path.join(REPO, "reference_results")
OUT = os.path.join(REPO, "real_world", "controller", "experiments")
sys.path.insert(0, REPO)  # also without `pip install -e .`


def _specs_under(d: str) -> list[str]:
    return sorted(glob.glob(os.path.join(d, "**", "spec.json"), recursive=True))


def _register(specs) -> None:
    from robobuilder import printed  # noqa: PLC0415

    for sp in specs:
        if sp and os.path.exists(sp):
            printed.register(sp)


def program(design_path: str, bench: str, level: int, agent: str, label: str, model: str = "", multi: str | None = None,
            solved: bool | None = None, sim_time: float | None = None, phase: str = "") -> dict:
    """one controller entry: the schedule of ``design_path`` on (bench, level)"""
    from robobuilder import courses, real  # noqa: PLC0415
    from robobuilder.core import design as D  # noqa: PLC0415
    from robobuilder.core import obstacles as OB  # noqa: PLC0415

    raw = json.load(open(design_path))
    tmp = None
    if multi:  # All-in-one: the assembly with this course's program
        raw = dict(raw, motor_program=(raw.get("motor_programs") or {}).get(bench, []))
        raw.pop("motor_programs", None)
        fd, tmp = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w") as f:
            json.dump(raw, f)
        design_path = tmp
    try:
        s = real.schedule(design_path, bench, level)
        d = D.Design.load(design_path)
        fx = OB.with_start_gap(courses.obstacle(bench, level), d).start.front_x
    finally:
        if tmp:
            os.remove(tmp)
    motors = [{"label": m["label"], "part": m["part"], "role": m["role"], "channel": m.get("channel"),
               "output": m.get("output"), "box": bool(m.get("box")), "stacked_on": m.get("stacked_on")}
              for m in s["motors"]]
    return {"agent": agent, "agent_label": label, "model": model,
            "task": f"{multi}/{bench}" if multi else f"{bench}_L{level}", "multi": multi, "bench": bench,
            "level": level, "phase": phase, "design": s["design"], "solved_in_sim": solved, "sim_time_s": sim_time,
            "run_s": s["run_s"], "time_limit_s": s["time_limit_s"], "receivers": s["receivers"], "ir": s["ir"],
            "box_direct": s["box_direct"], "motors": motors, "battery": s.get("battery") or "",
            "start": {"front_x_m": fx, "start_gap_mm": s["start_gap_mm"], "description": courses.description(bench, level)},
            "agent_notes": raw.get("description", ""), "wiring_notes": s["notes"]}


def _all_in_one(path: str, agent: str, label: str, model: str, benches: dict | None) -> list[dict]:
    from robobuilder import courses  # noqa: PLC0415

    progs = json.load(open(path)).get("motor_programs") or {}
    out = []
    for b in courses.BENCHES:
        if b not in progs:
            continue
        ok = None if benches is None else bool(benches.get(b))
        out.append(program(path, b, 1, agent, label, model, multi="all_L1", solved=ok, phase="all_in_one"))
    return out


def from_reference(levels, agents, all_in_one: bool) -> tuple[list[dict], str]:
    r = json.load(open(os.path.join(REF, "results.json")))
    progs = []
    for name, a in r["agents"].items():
        if agents and name not in agents:
            continue
        for tid, t in sorted(a["tasks"].items()):
            bench, lv = tid.rsplit("_L", 1)
            pw = t.get("passed_with")
            if int(lv) not in levels or not pw:
                continue
            rec = t[pw]
            _register(os.path.join(REF, p) for p in rec.get("printed_parts", []))
            progs.append(program(os.path.join(REF, rec["design"]), bench, int(lv), name, a["label"], a.get("model", ""),
                                 solved=True, sim_time=rec.get("time_s"), phase=pw))
        ai = a.get("all_in_one")
        if all_in_one and ai:
            _register(os.path.join(REF, p) for p in ai.get("printed_parts", []))
            progs += _all_in_one(os.path.join(REF, ai["design"]), name, a["label"], a.get("model", ""), ai.get("benches"))
    lv = ",".join(f"L{v}" for v in sorted(levels))
    return progs, f"Reference agents: passing designs ({lv})" + (" and All-in-one robots" if all_in_one else "")


def from_run(run_dir: str, levels, label: str | None) -> tuple[list[dict], str]:
    from robobuilder import courses  # noqa: PLC0415

    name = os.path.basename(os.path.normpath(run_dir))
    label = label or name
    progs = []
    for b in courses.BENCHES:
        for lv in levels:
            d = os.path.join(run_dir, "cross", courses.task_id(b, lv))
            p = os.path.join(d, "outcome.json")
            if not os.path.exists(p):
                continue
            o = json.load(open(p))
            pw = o.get("passed_with") if o.get("passed") else None
            f = os.path.join(d, f"accepted_{pw}.json") if pw else None
            if not f or not os.path.exists(f):
                continue
            _register(_specs_under(d))
            acc = (o.get("phases", {}).get(pw) or {}).get("accepted") or {}
            progs.append(program(f, b, lv, name, label, o.get("model", ""), solved=True, sim_time=acc.get("time_s"),
                                 phase=pw))
    d = os.path.join(run_dir, "all_in_one")
    acc = sorted(glob.glob(os.path.join(d, "accepted_*.json")))
    if acc:
        o = json.load(open(os.path.join(d, "outcome.json"))) if os.path.exists(os.path.join(d, "outcome.json")) else {}
        _register(_specs_under(d))
        progs += _all_in_one(acc[0], name, label, o.get("model", ""), o.get("benches"))
    return progs, f"{label}: passing designs and the All-in-one robot"


def from_design(path: str, bench: str, level: int, specs, label: str | None) -> tuple[list[dict], str]:
    _register(specs)
    name = os.path.splitext(os.path.basename(path))[0]
    label = label or name
    if bench == "all":
        return _all_in_one(path, "design", label, "", None), f"{label}: one program per course"
    return [program(path, bench, level, "design", label)], f"{label} on {bench} L{level}"


def write(progs: list[dict], name: str, title: str, out_dir: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    exp = {"name": name, "title": title, "keepalive_s": 0.3, "programs": progs}
    path = os.path.join(out_dir, f"{name}.js")
    with open(path, "w") as f:
        f.write("// generated by scripts/export_controller.py\n")
        f.write("window.RB_EXPERIMENTS = window.RB_EXPERIMENTS || {};\n")
        f.write(f"window.RB_EXPERIMENTS[{json.dumps(name)}] = {json.dumps(exp, indent=1)};\n")
    idx = os.path.join(out_dir, "index.js")
    files = []
    if os.path.exists(idx):
        m = re.search(r"RB_EXPERIMENT_FILES\s*=\s*(\[.*?\])", open(idx).read(), re.S)
        files = json.loads(m.group(1)) if m else []
    files = sorted(set(files) | {f"{name}.js"})
    with open(idx, "w") as f:
        f.write("// the experiment files the controller loads (updated by scripts/export_controller.py)\n")
        f.write(f"window.RB_EXPERIMENT_FILES = {json.dumps(files)};\n")
    return path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="src", required=True)
    p = sub.add_parser("reference")
    p.add_argument("--levels", default="1")
    p.add_argument("--agents", nargs="*", default=[])
    p.add_argument("--no-all-in-one", action="store_true")
    p = sub.add_parser("run")
    p.add_argument("run_dir")
    p.add_argument("--levels", default="1,2,3")
    p.add_argument("--label", default=None, help="the agent's name on the page (default: the folder name)")
    p = sub.add_parser("design")
    p.add_argument("design")
    p.add_argument("bench", help="a course, or 'all' for an All-in-one design (motor_programs)")
    p.add_argument("level", type=int, nargs="?", default=1)
    p.add_argument("--printed", nargs="*", default=[], help="spec.json of each printed part the design uses")
    p.add_argument("--label", default=None)
    for p in sub.choices.values():
        p.add_argument("--name", default=None, help="the experiment's name (file name and label on the page)")
        p.add_argument("--out", default=OUT, help="output folder (default: real_world/controller/experiments)")
    a = ap.parse_args(argv)
    if a.src == "reference":
        lv = [int(x) for x in a.levels.split(",")]
        progs, title = from_reference(lv, set(a.agents), not a.no_all_in_one)
        name = a.name or "reference-" + "".join(f"L{x}" for x in lv)
    elif a.src == "run":
        progs, title = from_run(a.run_dir, [int(x) for x in a.levels.split(",")], a.label)
        name = a.name or os.path.basename(os.path.normpath(a.run_dir))
    else:
        progs, title = from_design(a.design, a.bench, a.level, a.printed, a.label)
        name = a.name or os.path.splitext(os.path.basename(a.design))[0]
    if not progs:
        print("no design to export", file=sys.stderr)
        return 1
    print(f"wrote {write(progs, name, title, a.out)} ({len(progs)} programs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
