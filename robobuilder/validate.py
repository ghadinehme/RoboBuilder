"""The validator: the static design check of a level (owned parts and counts, real joints, gears, chains, electrics,
open-loop program, start, piece cap) and the design review (critical findings block acceptance)."""
from __future__ import annotations

import json

from . import courses

RECEIVER = "58123c01"
"""the IR receiver every design carries"""
STATS = ("n_parts", "mass_g", "length_mm", "width_mm", "height_mm", "ground_clearance_mm", "wheel_radius_mm",
         "expected_speed_m_s", "drive", "n_motors")


def printed_ids(design_path: str) -> list[str]:
    """the printed part types (ids p3d_...) a design file uses"""
    try:
        d = json.load(open(design_path))
    except Exception:  # noqa: BLE001
        return []
    return sorted({str(p.get("part", "")) for p in d.get("parts", []) if str(p.get("part", "")).startswith("p3d_")})


def validate(design_path: str, bench: str, level: int, review: bool = True) -> dict:
    """-> {"ok", "errors", "warnings", "stats", "review": {"critical", "warnings", "verdict"}}. Printed parts used by
    the design must be registered in this process first (robobuilder.printed.register)."""
    from .core import dfm  # noqa: PLC0415
    from .core.design import Budget, Design, place  # noqa: PLC0415
    from .core.design import validate as _validate  # noqa: PLC0415
    from .core.obstacles import check_constraints, task_constraints, start_gap_issue  # noqa: PLC0415

    courses.check(bench, level)
    try:
        d = Design.load(design_path)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "errors": [f"cannot load the design: {type(e).__name__}: {e}"], "warnings": [], "stats": {}}
    rep = _validate(d, Budget.for_part_set("inventory"))
    errs = list(rep.errors)
    ob = courses.obstacle(bench, level)
    if rep.ok:
        errs += check_constraints(ob, d, rep.stats, task_constraints(courses.MAX_PARTS))
    gi = start_gap_issue(ob, d, float((rep.stats or {}).get("length_mm") or 0.0))
    if gi:
        errs.append(f"start: {gi}")
    if not any(p.part == RECEIVER for p in d.parts):
        errs.append(f"rule: the IR receiver {RECEIVER} must be on board")
    if not any(p.bp.kind == "motor" for p in place(d).values()):
        errs.append("rule: the design needs at least one motor")
    st = rep.stats or {}
    out = {"ok": not errs, "errors": errs[:40], "warnings": list(rep.warnings)[:20],
           "stats": {k: st[k] for k in STATS if k in st}}
    if review:
        rv = dfm.review(d)
        out["review"] = {"critical": [f["message"] for f in rv["critical"]][:20],
                         "warnings": [f["message"] for f in rv["warnings"]][:20],
                         "verdict": "buildable" if not rv["critical"] else
                         "NOT buildable as designed: fix the critical findings before you submit"}
    return out
