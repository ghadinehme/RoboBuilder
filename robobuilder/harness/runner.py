"""Run the benchmark for one model: the Cross tasks level by level (memory carries from lower levels; the ten tasks of a
level run in parallel), then Light and Fast on every task (fresh sessions), then the All-in-one task.

    <run dir>/cross/<bench>_L<level>/      outcome.json, transcript.jsonl, workspace/, accepted_<phase>.json, printed/
    <run dir>/light/<bench>_L<level>/      (same)
    <run dir>/fast/<bench>_L<level>/
    <run dir>/all_in_one/                  outcome.json, accepted_all_in_one.json, printed/
    <run dir>/memory/<bench>_L<level>/     lessons.md, result.json, designs/
    <run dir>/run.json                     the agent, model, effort and settings

A task with an outcome.json is not run again (a task cut by a usage limit is: relaunch the same command after the
reset). The score: `robobuilder score <run dir>`."""
from __future__ import annotations

import json
import os
import shutil
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor

from .. import courses, printed
from ..agents import make_agent, tokens
from . import config as C
from . import memory as M
from . import session as S
from .all_in_one import AllInOneTask
from .task import Task

QUOTA_HIT = threading.Event()


def _logger(path: str):
    lock = threading.Lock()
    f = open(path, "a")

    def log(ev):
        with lock:
            f.write(json.dumps({"t": round(time.time(), 1), **ev}, default=str) + "\n")
            f.flush()
    return log, f


def _fresh_dir(d: str, force: bool) -> bool:
    """-> True if the task must run (no finished outcome); clears an unfinished attempt"""
    p = os.path.join(d, "outcome.json")
    if os.path.exists(p) and not force:
        prev = json.load(open(p))
        if not str(prev.get("stop", "")).startswith(("quota", "crash")):
            return False
    if os.path.isdir(d):
        shutil.rmtree(d)
    os.makedirs(d)
    return True


def _phase_records(task, phase_usage) -> dict:
    out = {}
    for p, r in task.phases.items():
        out[p] = {k: r.get(k) for k in ("goal", "budget", "accepted", "best_attempt", "submits", "stop", "hours",
                                         "accepted_all")}
        out[p]["used"] = dict(r["used"])
        out[p]["usage"] = phase_usage.get(p)
    return out


def _copy_accepted(task, d):
    for p, r in task.phases.items():
        if r.get("accepted"):
            shutil.copy(os.path.join(task.ws, r["accepted"]["file"]), os.path.join(d, f"accepted_{p}.json"))
        elif r.get("best_attempt") and os.path.exists(os.path.join(task.ws, r["best_attempt"]["file"])):
            shutil.copy(os.path.join(task.ws, r["best_attempt"]["file"]), os.path.join(d, f"best_attempt_{p}.json"))


def run_cross_task(spec: dict, run_dir: str, bench: str, level: int, force: bool) -> dict | None:
    d = os.path.join(run_dir, "cross", courses.task_id(bench, level))
    if QUOTA_HIT.is_set() or not _fresh_dir(d, force):
        p = os.path.join(d, "outcome.json")
        return json.load(open(p)) if os.path.exists(p) else None
    log, fh = _logger(os.path.join(d, "transcript.jsonl"))
    mem_in = M.build(d, os.path.join(run_dir, "memory"), level)
    task = Task(bench, level, d, log, memory_dir=mem_in)
    agent = make_agent(**spec)
    t0 = time.time()
    try:
        res = S.run_cross(agent, task, log)
    except Exception as e:  # noqa: BLE001
        res = {"stop": f"crash: {type(e).__name__}: {e}", "phase_usage": {}}
        log({"event": "crash", "trace": traceback.format_exc()})
    if task.phase in ("cross", "print") and task.phases.get(task.phase, {}).get("ended") is None:
        task.end_phase(res["stop"])
    _copy_accepted(task, d)
    out = {"task": courses.task_id(bench, level), "kind": "cross", "bench": bench, "level": level,
           "agent": agent.name, "model": agent.model, "stop": res["stop"], "passed": task.goal is not None,
           "passed_with": next((p for p in ("cross", "print") if (task.phases.get(p) or {}).get("accepted")), None),
           "phases": _phase_records(task, res["phase_usage"]), "printed_parts": task.custom,
           "memory_in": sorted(os.listdir(mem_in)) if mem_in else [], "usage": agent.usage,
           "tokens": tokens(agent.usage, agent.cache_in_input),
           "sims_total": sum(r["used"]["sims"] for r in task.phases.values()), "wall_s": round(time.time() - t0, 1)}
    json.dump(out, open(os.path.join(d, "outcome.json"), "w"), indent=1, default=str)
    if not str(out["stop"]).startswith("quota") or task.goal is not None:
        M.save(task, os.path.join(run_dir, "memory"))
    if str(out["stop"]).startswith("quota"):
        QUOTA_HIT.set()
    fh.close()
    print(f"[cross {out['task']}] {out['stop']}  sims {out['sims_total']}  {out['wall_s'] / 60:.0f} min", flush=True)
    return out


def run_fresh_task(spec: dict, run_dir: str, phase: str, bench: str, level: int, force: bool) -> dict | None:
    tid = courses.task_id(bench, level)
    d = os.path.join(run_dir, phase, tid)
    if QUOTA_HIT.is_set() or not _fresh_dir(d, force):
        p = os.path.join(d, "outcome.json")
        return json.load(open(p)) if os.path.exists(p) else None
    log, fh = _logger(os.path.join(d, "transcript.jsonl"))
    src_p = os.path.join(run_dir, "cross", tid, "outcome.json")
    src = json.load(open(src_p)) if os.path.exists(src_p) else {}
    pw = src.get("passed_with") if src.get("passed") else None
    acc0 = src["phases"][pw]["accepted"] if pw else None
    baseline = {"from": "cross", "phase": pw, **{k: acc0.get(k) for k in ("mass_g", "n_parts", "time_s", "printed_part")}} \
        if acc0 else None
    mem_in = M.build(d, os.path.join(run_dir, "memory"), level)
    task = Task(bench, level, d, log, memory_dir=mem_in)
    agent = make_agent(**spec)
    t0 = time.time()
    try:
        res = S.run_fresh(agent, task, log, phase, printed_allowed=bool(acc0 and (pw == "print" or acc0.get("printed_part"))))
    except Exception as e:  # noqa: BLE001
        res = {"stop": f"crash: {type(e).__name__}: {e}", "phase_usage": {}}
        log({"event": "crash", "trace": traceback.format_exc()})
    if task.phase == phase and task.phases.get(phase, {}).get("ended") is None:
        task.end_phase(res["stop"])
    _copy_accepted(task, d)
    key = "mass_g" if phase == "light" else "time_s"
    acc = (task.phases.get(phase) or {}).get("accepted")
    value = acc.get(key) if acc else (baseline or {}).get(key)  # nothing accepted: the passing design counts
    out = {"task": tid, "kind": phase, "bench": bench, "level": level, "agent": agent.name, "model": agent.model,
           "stop": res["stop"], "value": value, "value_from": phase if acc else ("pass" if baseline else None),
           "baseline": baseline, "phases": _phase_records(task, res["phase_usage"]), "printed_parts": task.custom,
           "usage": agent.usage, "tokens": tokens(agent.usage, agent.cache_in_input),
           "sims_total": sum(r["used"]["sims"] for r in task.phases.values()), "wall_s": round(time.time() - t0, 1)}
    json.dump(out, open(os.path.join(d, "outcome.json"), "w"), indent=1, default=str)
    if str(out["stop"]).startswith("quota"):
        QUOTA_HIT.set()
    fh.close()
    print(f"[{phase} {tid}] {out['stop']}  {key} {value}  sims {out['sims_total']}", flush=True)
    return out


def run_all_in_one_task(spec: dict, run_dir: str, force: bool) -> dict | None:
    d = os.path.join(run_dir, "all_in_one")
    if QUOTA_HIT.is_set() or not _fresh_dir(d, force):
        p = os.path.join(d, "outcome.json")
        return json.load(open(p)) if os.path.exists(p) else None
    log, fh = _logger(os.path.join(d, "transcript.jsonl"))
    task = AllInOneTask(d, log)
    agent = make_agent(**spec)
    t0 = time.time()
    try:
        res = S.run_all_in_one(agent, task, log)
    except Exception as e:  # noqa: BLE001
        res = {"stop": f"crash: {type(e).__name__}: {e}", "phase_usage": {}}
        log({"event": "crash", "trace": traceback.format_exc()})
    _copy_accepted(task, d)
    fin = task.final or {}
    out = {"task": "all_in_one", "kind": "all_in_one", "agent": agent.name, "model": agent.model, "stop": res["stop"],
           "benches_passed": fin.get("benches_passed", 0),
           "benches": {b: r.get("passed") for b, r in (fin.get("benches") or {}).items()}, "final": fin,
           "phases": _phase_records(task, res["phase_usage"]), "printed_parts": task.custom, "usage": agent.usage,
           "tokens": tokens(agent.usage, agent.cache_in_input),
           "sims_total": sum(r["used"]["sims"] for r in task.phases.values()), "wall_s": round(time.time() - t0, 1)}
    json.dump(out, open(os.path.join(d, "outcome.json"), "w"), indent=1, default=str)
    fh.close()
    print(f"[all_in_one] {out['stop']}  courses passed {out['benches_passed']}/10  sims {out['sims_total']}", flush=True)
    return out


def run(spec: dict, run_dir: str, levels=(1, 2, 3), benches=None, tasks=("cross", "light", "fast", "all_in_one"),
        parallel: int = 10, force: bool = False) -> None:
    """``spec``: make_agent arguments (kind, model, effort, adapter options)"""
    benches = list(benches or courses.BENCHES)
    os.makedirs(run_dir, exist_ok=True)
    json.dump({"agent": spec, "levels": list(levels), "benches": benches, "tasks": list(tasks), "phases": C.PHASES,
               "all_in_one": C.ALL_IN_ONE}, open(os.path.join(run_dir, "run.json"), "w"), indent=1)
    if "cross" in tasks:
        for lv in sorted(levels):
            with ThreadPoolExecutor(parallel) as ex:
                list(ex.map(lambda b: run_cross_task(spec, run_dir, b, lv, force), benches))
            if QUOTA_HIT.is_set():
                print("usage limit hit: stopping; relaunch the same command after the reset", flush=True)
                return
    jobs = [(ph, b, lv) for ph in ("light", "fast") if ph in tasks for lv in sorted(levels) for b in benches]
    if jobs:
        with ThreadPoolExecutor(parallel) as ex:
            list(ex.map(lambda j: run_fresh_task(spec, run_dir, j[0], j[1], j[2], force), jobs))
        if QUOTA_HIT.is_set():
            print("usage limit hit: stopping; relaunch the same command after the reset", flush=True)
            return
    if "all_in_one" in tasks:
        run_all_in_one_task(spec, run_dir, force)
    print(f"done: robobuilder score {run_dir}", flush=True)


def register_run_parts(outcome: dict) -> list[str]:
    """register the printed parts recorded in a task outcome (re-checks, scoring)"""
    return [printed.register(sp) for sp in (outcome.get("printed_parts") or {}).values() if os.path.exists(sp)]
