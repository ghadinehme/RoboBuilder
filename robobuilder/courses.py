"""The ten obstacles at three levels: names, levels and the task file an agent receives (robobuilder.core.obstacles
builds each course and judges a run)."""
from __future__ import annotations

import contextlib
import dataclasses
import re

BENCHES = ["ramp", "gap", "bridge", "rope", "steps", "bumps", "seesaw", "gap_drop", "wall", "u_turn"]
LEVELS = (1, 2, 3)
MAX_PARTS = 400
"""piece cap of every task"""


@contextlib.contextmanager
def rules(start_boards: bool = True, max_chains: int | None = 2, cross_index: bool = True):
    """the benchmark's rules (default), or those a reference design was accepted under, in this thread: start boards
    (500 mm, gap 1000 mm) or the courses as built; at most ``max_chains`` chain loops (None: no limit); parts on a
    cross axle at multiples of 90 deg"""
    from . import BENCHMARK_ENV  # noqa: PLC0415
    from .core import rules as R  # noqa: PLC0415

    old = dict(R.LOCAL.__dict__)
    R.LOCAL.start_board_raw = BENCHMARK_ENV["RB_START_BOARD_MM"] if start_boards else ""
    R.LOCAL.max_chains = "" if max_chains is None else str(max_chains)
    R.LOCAL.cross_index = cross_index
    try:
        yield
    finally:
        R.LOCAL.__dict__.clear()
        R.LOCAL.__dict__.update(old)


def rules_env(start_boards: bool = True, max_chains: int | None = 2) -> dict:
    """the same settings for a simulator subprocess"""
    from . import BENCHMARK_ENV  # noqa: PLC0415

    return {"RB_START_BOARD_MM": BENCHMARK_ENV["RB_START_BOARD_MM"] if start_boards else "",
            "RB_MAX_CHAINS": "" if max_chains is None else str(max_chains)}


def check(bench: str, level: int) -> None:
    if bench not in BENCHES:
        raise ValueError(f"unknown obstacle '{bench}' (one of: {', '.join(BENCHES)})")
    if level not in LEVELS:
        raise ValueError(f"level must be 1, 2 or 3 (got {level})")


def task_id(bench: str, level: int) -> str:
    return f"{bench}_L{level}"


def parse_task_id(tid: str) -> tuple[str, int]:
    m = re.fullmatch(r"([a-z_]+)_L([123])", tid)
    if not m:
        raise ValueError(f"bad task id '{tid}' (e.g. ramp_L1)")
    check(m.group(1), int(m.group(2)))
    return m.group(1), int(m.group(2))


def obstacle(bench: str, level: int):
    """the course (core.obstacles.Obstacle) of an obstacle at a benchmark level"""
    from .core import obstacles as OB  # noqa: PLC0415

    check(bench, level)
    return OB.generate(bench, level)


def description(bench: str, level: int) -> str:
    return obstacle(bench, level).description


def task(bench: str, level: int) -> dict:
    """the level as the agent sees it (``/work/docs/task.json``): geometry, start, goal and limits"""
    from .core import obstacles as OB  # noqa: PLC0415

    ob = obstacle(bench, level)
    out = {"id": task_id(bench, level), "bench": bench, "level": level, "cap": MAX_PARTS,
           "description": description(bench, level), "params": dict(ob.params),
           "start": {**dataclasses.asdict(ob.start), "approach_board_mm": OB.approach_mm(ob)},
           "goal": dataclasses.asdict(ob.goal), "time_limit_s": ob.time_limit_s,
           "lane_half_width_m": ob.lane_half_width, "fail_z_m": ob.fail_z, "floor_z_m": ob.floor_z,
           "stuck_window_s": ob.stuck_window_s, "shapes": [dataclasses.asdict(s) for s in ob.shapes]}
    if ob.centreline:
        out["centreline"] = [list(p) for p in ob.centreline]
    for sh in out["shapes"]:  # the ramp board is the same foam board as the floor (the simulator's label differs)
        if sh.get("surface") == "rubber_mat":
            sh["surface"] = "foam_board"
    if out["params"].get("surface") == "rubber_mat":
        out["params"]["surface"] = "foam_board"
    return out


def all_in_one_task() -> dict:
    """the All-in-one task: one robot for the ten level-1 courses"""
    return {"id": "all_in_one", "level": 1, "task": "one robot that passes as many of the 10 level-1 obstacles as possible",
            "benches": {b: task(b, 1) for b in BENCHES}}
