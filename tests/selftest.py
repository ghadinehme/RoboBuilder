"""Self-test: re-simulate the reference entrants' accepted designs and reproduce their paper verdicts.

    python tests/selftest.py                 Cross and Cross+Print designs (86 designs, 3 runs each)
    python tests/selftest.py --all           also the Light / Fast designs (111) and the four All-in-one robots
    python tests/selftest.py --quick         one Cross design per obstacle (10 designs)
    options: --workers N (designs at a time; each runs up to 3 simulations), --out DIR (results, default
             selftest_out/), --agent NAME (one entrant)

Each design is judged under the rules it was accepted under for the paper (results.json "rules": the courses with
or without start boards, the chain-loop limit, the cross-axle rule); --final-rules judges every design under the
benchmark's rules. A design reproduces its verdict when it validates, the design review has no critical finding and
the plain run and both nudged runs pass (Light / Fast: also with the recorded mass / crossing time); an All-in-one
robot when it passes the same courses.
Exit code 0 when everything reproduces."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
REF = os.path.join(REPO, "reference_results")
FINAL_RULES = False  # --final-rules: judge every design under the benchmark's rules


def jobs(sel: str, agent: str | None) -> list[dict]:
    r = json.load(open(os.path.join(REF, "results.json")))
    out = []
    seen_bench = set()
    for name, a in r["agents"].items():
        if agent and name != agent:
            continue
        for tid, t in a["tasks"].items():
            bench, lv = tid.rsplit("_L", 1)
            for ph in ("cross", "print", "light_design", "fast_design"):
                rec = t.get(ph)
                if not rec:
                    continue
                if ph.endswith("_design") and sel != "all":
                    continue
                if sel == "quick" and (ph != "cross" or bench in seen_bench):
                    continue
                seen_bench.add(bench)
                out.append({"kind": "task", "agent": name, "task": tid, "bench": bench, "level": int(lv),
                            "phase": ph.replace("_design", ""), "design": os.path.join(REF, rec["design"]),
                            "printed": [os.path.join(REF, p) for p in rec["printed_parts"]],
                            "mass_g": rec.get("mass_g"), "time_s": rec.get("time_s"),
                            "rules": rec.get("rules") or {}})
        if sel == "all":
            ai = a["all_in_one"]
            out.append({"kind": "all_in_one", "agent": name, "task": "all_in_one", "design": os.path.join(REF, ai["design"]),
                        "printed": [os.path.join(REF, p) for p in ai["printed_parts"]], "benches": ai["benches"]})
    return out


def run_job(j: dict, out_root: str) -> dict:
    from robobuilder import printed, simulate

    od = os.path.join(out_root, j["agent"], j["task"], j.get("phase", "all_in_one"))
    os.makedirs(od, exist_ok=True)
    t0 = time.time()
    if j["kind"] == "all_in_one":
        from robobuilder.harness.all_in_one import score_robot

        specs = {json.load(open(p))["part_id"]: p for p in j["printed"]}
        res = score_robot(j["design"], specs, out_root=od)
        got = {b: bool(r["passed"]) for b, r in res.items()}
        ok = got == {b: bool(v) for b, v in j["benches"].items()}
        return {**{k: j[k] for k in ("agent", "task")}, "phase": "all_in_one", "ok": ok,
                "expected": sum(j["benches"].values()), "got": sum(got.values()), "benches": got,
                "wall_s": round(time.time() - t0)}
    for p in j["printed"]:
        printed.register(p)
    v = simulate.verdict(j["design"], j["bench"], j["level"], printed_specs=j["printed"], out_root=od,
                         rules=None if FINAL_RULES else j["rules"])
    mass = (v.get("validate") or {}).get("stats", {}).get("mass_g")
    t = (v.get("plain") or {}).get("time_s")
    ok = bool(v["passed"])
    if j["phase"] == "light" and j.get("mass_g") is not None:
        ok = ok and mass is not None and abs(mass - j["mass_g"]) < 0.05
    if j["phase"] == "fast" and j.get("time_s") is not None:
        ok = ok and t is not None and abs(t - j["time_s"]) < 0.051
    return {**{k: j[k] for k in ("agent", "task", "phase")}, "ok": ok, "passed": v["passed"], "reason": v.get("reason"),
            "mass_g": mass, "mass_ref": j.get("mass_g"), "time_s": t, "time_ref": j.get("time_s"),
            "wall_s": round(time.time() - t0)}


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--quick", action="store_true")
    g.add_argument("--all", action="store_true")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 3) // 3))
    ap.add_argument("--out", default=os.path.join(REPO, "selftest_out"))
    ap.add_argument("--agent", default=None)
    ap.add_argument("--final-rules", action="store_true", help="judge every design under the benchmark's rules "
                    "(default: the rules each design was accepted under, results.json 'rules')")
    a = ap.parse_args()
    global FINAL_RULES
    FINAL_RULES = a.final_rules
    J = jobs("quick" if a.quick else "all" if a.all else "cross", a.agent)
    os.environ.setdefault("RB_MAX_PARALLEL_SIMS", str(3 * a.workers))
    # a run's own wall-time limit: 900 s in the benchmark; the largest designs need ~10 min alone and more on a loaded
    # machine, so the self-test allows 2 h (a run cut by the limit fails, whatever the physics)
    os.environ.setdefault("CSIM_WALL_S", "7200")
    os.environ.setdefault("RB_SIM_TIMEOUT_S", "10800")
    print(f"{len(J)} designs, {a.workers} at a time", flush=True)
    res = []
    with ThreadPoolExecutor(a.workers) as ex:
        for r in ex.map(lambda j: run_job(j, a.out), J):
            res.append(r)
            print(("ok  " if r["ok"] else "FAIL") + f" {r['agent']:12s} {r['task']:12s} {r['phase']:10s} "
                  + json.dumps({k: r.get(k) for k in ("reason", "mass_g", "mass_ref", "time_s", "time_ref", "expected",
                                                       "got") if r.get(k) is not None}), flush=True)
    n_ok = sum(r["ok"] for r in res)
    os.makedirs(a.out, exist_ok=True)
    json.dump(res, open(os.path.join(a.out, "selftest.json"), "w"), indent=1)
    print(f"\n{n_ok} of {len(res)} reproduce their paper verdicts")
    return 0 if n_ok == len(res) else 1


if __name__ == "__main__":
    sys.exit(main())
