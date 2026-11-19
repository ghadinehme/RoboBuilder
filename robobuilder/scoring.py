"""The leaderboard (the columns of the paper's main table).

Per entrant:
  Cross L1 / L2 / L3   share of the 10 tasks of a level passed in Cross (%)
  +Print               share of the 30 tasks passed in Cross or Cross+Print (%)
  Sims                 median simulations until the passing design was accepted (Cross passes)
  All-in-one           share of the 10 courses the All-in-one robot passes in simulation (%) (real: reference only)
  Light mass / Fast time   mean mass (g) / crossing time (s) over the level-1 tasks where every listed entrant has one
  Light / Fast score   per task, the best value among the listed entrants divided by the entrant's own (0 without a
                       value), summed over the 30 tasks (of 30). The value is the best accepted Light / Fast design,
                       else the passing design.
  Score                100 x the mean of (Cross+Print passes) / 30, All-in-one / 10, Light / 30, Fast / 30
Light and Fast scores are relative to the entrants listed: adding a model changes the best values and so every
entrant's score. Tokens (cache reads not counted; output includes reasoning) and wall hours are information only."""
from __future__ import annotations

import json
import os
import statistics

from . import courses

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REFERENCE = os.path.join(REPO, "reference_results", "results.json")
TASKS = [courses.task_id(b, lv) for lv in courses.LEVELS for b in courses.BENCHES]


def load_reference(path: str = REFERENCE) -> dict:
    """-> {entrant: {"tasks": {task id: {"passed_with", "sims_to_pass", "light", "fast"}}, "all_in_one",
    "all_in_one_real", "tokens", "wall_h"}}"""
    r = json.load(open(path))
    out = {}
    for name, a in r["agents"].items():
        T = {tid: {"passed_with": t["passed_with"], "sims_to_pass": t["sims_to_pass"],
                   "light": (t.get("light") or {}).get("value"), "fast": (t.get("fast") or {}).get("value")}
             for tid, t in a["tasks"].items()}
        tok_in = sum((t.get("tokens") or {}).get("input") or 0 for t in a["tasks"].values())
        tok_out = sum((t.get("tokens") or {}).get("output") or 0 for t in a["tasks"].values())
        out[name] = {"tasks": T, "all_in_one": a["all_in_one"]["benches_passed"],
                     "all_in_one_real": a["all_in_one"].get("real_benches_passed"),
                     "tokens": {"input": tok_in, "output": tok_out}, "tokens_scope": "Cross and Cross+Print",
                     "wall_h": round(sum(t.get("wall_h") or 0 for t in a["tasks"].values()), 1)}
    return out


def _load(p):
    return json.load(open(p)) if os.path.exists(p) else None


def load_run(run_dir: str) -> dict:
    """one model's run (robobuilder run) -> the same structure as load_reference()[name]"""
    T, tok_in, tok_out, wall = {}, 0, 0, 0.0
    for tid in TASKS:
        c = _load(os.path.join(run_dir, "cross", tid, "outcome.json")) or {}
        pw = c.get("passed_with") if c.get("passed") else None
        sims = None
        if pw:
            acc = c["phases"][pw]["accepted"]
            sims = acc["sims_used"] + (30 if pw == "print" else 0)
        row = {"passed_with": pw, "sims_to_pass": sims}
        for ph in ("light", "fast"):
            o = _load(os.path.join(run_dir, ph, tid, "outcome.json"))
            row[ph] = o.get("value") if o else None
            if o is None and pw:  # Light / Fast not run: the passing design counts
                row[ph] = c["phases"][pw]["accepted"].get("mass_g" if ph == "light" else "time_s")
            for x in (o, c if ph == "light" else None):
                if x:
                    tok_in += (x.get("tokens") or {}).get("input_tokens", 0)
                    tok_out += (x.get("tokens") or {}).get("output_tokens", 0)
                    wall += (x.get("wall_s") or 0) / 3600
        T[tid] = row
    a = _load(os.path.join(run_dir, "all_in_one", "outcome.json")) or {}
    if a:
        tok_in += (a.get("tokens") or {}).get("input_tokens", 0)
        tok_out += (a.get("tokens") or {}).get("output_tokens", 0)
        wall += (a.get("wall_s") or 0) / 3600
    return {"tasks": T, "all_in_one": a.get("benches_passed", 0) if a else 0, "all_in_one_real": None,
            "tokens": {"input": tok_in, "output": tok_out}, "tokens_scope": "all tasks", "wall_h": round(wall, 1)}


def leaderboard(entrants: dict) -> list[dict]:
    names = list(entrants)
    best = {}
    for ph in ("light", "fast"):
        best[ph] = {t: min((entrants[n]["tasks"][t][ph] for n in names if entrants[n]["tasks"].get(t, {}).get(ph)),
                           default=None) for t in TASKS}
    common = {ph: [t for t in TASKS if t.endswith("_L1") and all(entrants[n]["tasks"].get(t, {}).get(ph) for n in names)]
              for ph in ("light", "fast")}
    rows = []
    for n in names:
        E = entrants[n]["tasks"]
        row = {"entrant": n}
        for lv in courses.LEVELS:
            row[f"cross_L{lv}"] = 100.0 * sum(E[t]["passed_with"] == "cross" for t in TASKS if t.endswith(f"_L{lv}")) / 10
        ax = sum(E[t]["passed_with"] in ("cross", "print") for t in TASKS)
        row["cross_print"] = 100.0 * ax / 30
        sims = [E[t]["sims_to_pass"] for t in TASKS if E[t]["passed_with"] == "cross" and E[t]["sims_to_pass"] is not None]
        row["sims_median"] = statistics.median(sims) if sims else None
        row["all_in_one"] = 10.0 * entrants[n]["all_in_one"]
        real = entrants[n].get("all_in_one_real")
        row["all_in_one_real"] = None if real is None else 10.0 * real
        for ph, key in (("light", "light_mass_g"), ("fast", "fast_time_s")):
            row[key] = statistics.mean(E[t][ph] for t in common[ph]) if common[ph] else None
            row[f"{ph}_score"] = sum((best[ph][t] / E[t][ph]) if E[t][ph] else 0.0 for t in TASKS)
        row["score"] = 100.0 * (ax / 30 + entrants[n]["all_in_one"] / 10 + row["light_score"] / 30
                                + row["fast_score"] / 30) / 4
        row["tokens_in_M"] = round(entrants[n]["tokens"]["input"] / 1e6, 1)
        row["tokens_out_M"] = round(entrants[n]["tokens"]["output"] / 1e6, 1)
        row["tokens_scope"] = entrants[n].get("tokens_scope")
        row["wall_h"] = entrants[n].get("wall_h")
        rows.append(row)
    rows.sort(key=lambda r: -r["score"])
    return rows


def fmt(x, nd=1):
    return "--" if x is None else (f"{x:.{nd}f}" if isinstance(x, float) and x != int(x) or nd > 0 else str(x))


def markdown(rows: list[dict]) -> str:
    h = ("| Entrant | Cross L1 (%) | L2 | L3 | +Print (%) | Sims (med.) | All-in-one sim (%) | real (%) | Light mass (g) "
         "| Light score | Fast time (s) | Fast score | Score (/100) | tokens in/out (M) | wall (h) |")
    lines = [h, "|" + "---|" * 15]
    for r in rows:
        s = r["sims_median"]
        lines.append(" | ".join([
            f"| {r['entrant']}", f"{r['cross_L1']:.0f}", f"{r['cross_L2']:.0f}", f"{r['cross_L3']:.0f}",
            f"{r['cross_print']:.0f}", "--" if s is None else (f"{s:.1f}" if s != int(s) else f"{s:.0f}"),
            f"{r['all_in_one']:.0f}", "--" if r["all_in_one_real"] is None else f"{r['all_in_one_real']:.0f}",
            "--" if r["light_mass_g"] is None else f"{r['light_mass_g']:.0f}", f"{r['light_score']:.1f}",
            "--" if r["fast_time_s"] is None else f"{r['fast_time_s']:.2f}", f"{r['fast_score']:.1f}",
            f"{r['score']:.1f}", f"{r['tokens_in_M']}/{r['tokens_out_M']}", f"{r['wall_h']}"]) + " |")
    lines.append("")
    lines.append("Light / Fast scores are relative to the entrants listed. Tokens: cache reads not counted, output "
                 "includes reasoning (reference entrants: Cross and Cross+Print sessions only); information, not ranked.")
    return "\n".join(lines)
