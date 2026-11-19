"""Memory between levels: after each Cross task the agent writes lessons.md; the harness keeps it with the accepted
designs and their results. A task at level L starts with a read-only /work/memory/ holding that agent's entries from
every task of a lower level (tasks within a level run in parallel and do not share memory)."""
from __future__ import annotations

import glob
import json
import os
import shutil

NAMES = {"cross": "cross_pass", "print": "cross_print_pass_printed_part", "light": "light", "fast": "fast"}


def entry_level(name: str) -> int | None:
    try:
        return int(name.rsplit("_L", 1)[1])
    except (IndexError, ValueError):
        return None


def build(task_dir: str, mem_root: str, level: int) -> str | None:
    """copy every memory entry of a lower level into <task_dir>/memory_in (read-only at /work/memory) -> its path"""
    entries = [e for e in sorted(glob.glob(os.path.join(mem_root, "*_L*")))
               if os.path.isdir(e) and (entry_level(os.path.basename(e)) or 99) < level]
    if not entries:
        return None
    dst = os.path.join(task_dir, "memory_in")
    shutil.rmtree(dst, ignore_errors=True)
    os.makedirs(dst)
    rows = []
    for e in entries:
        name = os.path.basename(e)
        shutil.copytree(e, os.path.join(dst, name))
        try:
            r = json.load(open(os.path.join(e, "result.json")))
        except Exception:  # noqa: BLE001
            r = {}
        ph = r.get("phases", {})

        def cell(p):
            a = ph.get(p) or {}
            if a.get("accepted"):
                return f"{a.get('mass_g')} g, {a.get('time_s')} s"
            if a.get("best_attempt"):
                return f"not passed (best progress {a['best_attempt'].get('max_progress')})"
            return "not accepted" if p in ph else "-"
        rows.append(f"| {name} | {'passed' if r.get('passed') else 'not passed'}"
                    f"{' (printed part)' if r.get('passed_with') == 'print' else ''} | {cell(r.get('passed_with') or 'cross')} |")
    open(os.path.join(dst, "INDEX.md"), "w").write(
        "# Your memory from earlier tasks\n\nOne folder per earlier task (bench_level): `lessons.md` (what you wrote "
        "at the end of that task), `result.json` (what was accepted, masses, crossing times, simulations used) and "
        "`designs/` (each accepted design; the best attempt when none was). Read-only.\n\n"
        "| task | level passed | passing design |\n|---|---|---|\n" + "\n".join(rows) + "\n")
    return dst


def save(task, mem_root: str) -> str:
    """the task's memory entry: lessons.md, result.json, designs/ (+ the printed part's STL and CAD script)"""
    d = os.path.join(mem_root, f"{task.bench}_L{task.level}")
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(os.path.join(d, "designs"))
    les = os.path.join(task.ws, "lessons.md")
    txt = open(les, errors="replace").read()[:20000] if os.path.exists(les) else "(no lessons were written in this task)\n"
    open(os.path.join(d, "lessons.md"), "w").write(txt)
    res = {"bench": task.bench, "level": task.level, "passed": task.goal is not None,
           "passed_with": next((p for p in ("cross", "print") if (task.phases.get(p) or {}).get("accepted")), None),
           "phases": {}}
    for p, r in task.phases.items():
        a = r.get("accepted")
        row = {"goal": r["goal"], "accepted": bool(a), "sims_used": r["used"]["sims"], "hours": r.get("hours")}
        if a:
            shutil.copy(os.path.join(task.ws, a["file"]), os.path.join(d, "designs", f"{NAMES.get(p, p)}.json"))
            row.update({k: a.get(k) for k in ("mass_g", "n_parts", "time_s", "nudges", "printed_part")})
            row["design"] = f"designs/{NAMES.get(p, p)}.json"
        elif r.get("best_attempt"):
            b = r["best_attempt"]
            src = os.path.join(task.ws, b["file"])
            if os.path.exists(src):
                shutil.copy(src, os.path.join(d, "designs", f"{p}_best_attempt.json"))
                row["best_attempt"] = {"design": f"designs/{p}_best_attempt.json",
                                       **{k: b.get(k) for k in ("max_progress", "max_progress_m", "failure", "auto")}}
        res["phases"][p] = row
    for pid, sp in task.custom.items():
        pd = os.path.dirname(sp)
        os.makedirs(os.path.join(d, "printed_part"), exist_ok=True)
        for f in (f"{pid}.stl", "cad_script.py"):
            if os.path.exists(os.path.join(pd, f)):
                shutil.copy(os.path.join(pd, f), os.path.join(d, "printed_part", f if f.endswith(".stl") else f"{pid}_{f}"))
    json.dump(res, open(os.path.join(d, "result.json"), "w"), indent=1, default=str)
    return d
