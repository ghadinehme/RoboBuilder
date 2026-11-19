"""robobuilder: the benchmark from the command line.

    robobuilder courses                                   the ten obstacles and their three levels
    robobuilder task <bench> <level>                      a level as the agent sees it (JSON)
    robobuilder validate <design.json> <bench> <level>    static check and design review (fast)
    robobuilder simulate <design.json> <bench> <level> [--video] [--printed spec.json ...]
                                                          one plain simulation run
    robobuilder check <design.json> <bench> <level> [--printed spec.json ...]
                                                          the official verdict: validation, review, plain + nudged runs
    robobuilder run --agent <claude-code|codex|gemini-cli|generic> --model <model> --run-dir <dir> [options]
                                                          run the benchmark for one model (see README)
    robobuilder score [<run dir> ...] [--name NAME ...] [--json out.json]
                                                          the leaderboard: the reference entrants (the paper's table)
                                                          plus each run given
"""
from __future__ import annotations

import argparse
import json
import os
import sys


def _printed(specs):
    from .printed import register  # noqa: PLC0415

    for s in specs or []:
        register(s)
    return list(specs or [])


def _rules(a) -> dict:
    """courses.rules arguments from the --as-built / --no-chain-limit / --no-cross-index flags"""
    return {"start_boards": not a.as_built, "max_chains": None if a.no_chain_limit else 2,
            "cross_index": not a.no_cross_index}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="robobuilder", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("courses")
    p = sub.add_parser("task")
    p.add_argument("bench")
    p.add_argument("level", type=int)
    for name in ("validate", "simulate", "check"):
        p = sub.add_parser(name)
        p.add_argument("design")
        p.add_argument("bench")
        p.add_argument("level", type=int)
        p.add_argument("--printed", nargs="*", default=[], help="spec.json of each printed part the design uses")
        p.add_argument("--as-built", action="store_true", help="the courses without the benchmark's start boards")
        p.add_argument("--no-chain-limit", action="store_true", help="no limit on chain loops (default: 2)")
        p.add_argument("--no-cross-index", action="store_true", help="no 90-deg rule for parts on a cross axle")
        if name == "simulate":
            p.add_argument("--video", action="store_true")
            p.add_argument("--out", default=None, help="output folder (default: <design dir>/_sims/...)")
        if name in ("simulate", "check"):
            p.add_argument("--params", default=None, help="simulator parameters (default: the learned simulator)")
    p = sub.add_parser("run")
    p.add_argument("--agent", required=True, help="claude-code | codex | gemini-cli | generic")
    p.add_argument("--model", required=True)
    p.add_argument("--effort", default="medium", help="reasoning effort passed to the CLI (paper: medium)")
    p.add_argument("--run-dir", required=True)
    p.add_argument("--levels", default="1,2,3")
    p.add_argument("--benches", default=",".join(__import__("robobuilder.courses", fromlist=["x"]).BENCHES))
    p.add_argument("--tasks", default="cross,light,fast,all_in_one")
    p.add_argument("--parallel", type=int, default=10, help="tasks at a time")
    p.add_argument("--force", action="store_true", help="rerun tasks that already have an outcome")
    g = p.add_argument_group("generic adapter")
    g.add_argument("--command", help='command template, e.g. "mycli --model {model} --prompt-file {prompt_file}"')
    g.add_argument("--resume", help="command template to continue the session ({session})")
    g.add_argument("--session-regex", help="regex with one group: the session id in the CLI's output")
    g.add_argument("--token-parser", help="module:function mapping a JSON event to token increments")
    g.add_argument("--bind", action="append", default=[], help="extra read-only path in the sandbox (its install)")
    g.add_argument("--path", action="append", default=[], help="extra PATH entry in the sandbox")
    g.add_argument("--login", action="append", default=[], help="login file under ~ mapped into the sandbox home")
    g.add_argument("--env", action="append", default=[], help="KEY=VALUE set in the sandbox")
    g.add_argument("--name", default="generic", help="the adapter's name in the results")
    p = sub.add_parser("score")
    p.add_argument("runs", nargs="*")
    p.add_argument("--name", nargs="*", default=[], help="a name per run (default: the folder name)")
    p.add_argument("--json", default=None)
    p.add_argument("--no-reference", action="store_true", help="only the runs given")
    a = ap.parse_args(argv)

    if a.cmd == "courses":
        from . import courses  # noqa: PLC0415

        for b in courses.BENCHES:
            print(b)
            for lv in courses.LEVELS:
                print(f"  L{lv}: {courses.description(b, lv)}")
        return 0
    if a.cmd == "task":
        from . import courses  # noqa: PLC0415

        print(json.dumps(courses.task(a.bench, a.level), indent=1))
        return 0
    if a.cmd == "validate":
        from .validate import validate  # noqa: PLC0415

        from . import courses  # noqa: PLC0415

        _printed(a.printed)
        with courses.rules(**_rules(a)):
            print(json.dumps(validate(a.design, a.bench, a.level), indent=1))
        return 0
    if a.cmd == "simulate":
        from . import simulate  # noqa: PLC0415
        from .validate import validate  # noqa: PLC0415

        from . import courses  # noqa: PLC0415

        specs = _printed(a.printed)
        with courses.rules(**_rules(a)):
            v = validate(a.design, a.bench, a.level)
        if not v["ok"]:
            print(json.dumps({"error": "the design does not validate", **v}, indent=1))
            return 1
        r = simulate.run(a.design, a.bench, a.level, env=courses.rules_env(not a.as_built, None if a.no_chain_limit else 2), video=a.video,
                         printed_specs=specs, out_dir=a.out, params=a.params)
        out = simulate.summary(r)
        out["dir"] = r.get("_dir")
        if r.get("_contact_sheets"):
            out["contact_sheets"] = r["_contact_sheets"]
        print(json.dumps(out, indent=1))
        return 0
    if a.cmd == "check":
        from . import simulate  # noqa: PLC0415

        print(json.dumps(simulate.verdict(a.design, a.bench, a.level, printed_specs=a.printed, params=a.params,
                                          rules=_rules(a)), indent=1))
        return 0
    if a.cmd == "run":
        from .harness import runner  # noqa: PLC0415

        spec = {"kind": a.agent, "model": a.model, "effort": a.effort or None}
        if a.agent == "generic":
            spec.update(command=a.command, resume=a.resume, session_regex=a.session_regex, token_parser=a.token_parser,
                        binds=a.bind, path=a.path, login=a.login, env=a.env, name=a.name)
        runner.run(spec, os.path.abspath(a.run_dir), levels=[int(x) for x in a.levels.split(",")],
                   benches=a.benches.split(","), tasks=a.tasks.split(","), parallel=a.parallel, force=a.force)
        return 0
    if a.cmd == "score":
        from . import scoring  # noqa: PLC0415

        ent = {} if a.no_reference else scoring.load_reference()
        for i, rd in enumerate(a.runs):
            name = a.name[i] if i < len(a.name) else os.path.basename(os.path.normpath(rd))
            ent[name] = scoring.load_run(rd)
        if not ent:
            print("nothing to score")
            return 1
        rows = scoring.leaderboard(ent)
        print(scoring.markdown(rows))
        if a.json:
            json.dump(rows, open(a.json, "w"), indent=1)
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
