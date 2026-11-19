"""The All-in-one task: one robot for the ten level-1 courses.

- One assembly, one motor program per course (design field ``motor_programs``: {"ramp": [...], ...}).
- The structure is printed: no bricks, beam bricks or plates from the inventory (part kinds ``plate`` and
  ``beam_brick``); gears, axles, pins, connectors, bushes, wheels, chains / treads, racks, shocks, motors, battery boxes
  and IR receivers are allowed. Any number of printed part types (8 copies each), each fitting 250 mm per side.
- Up to two IR receivers, any number of motors they can drive (stacked plugs allowed).
- 300 simulations (each on one named course) and 72 h.
- Score: the number of courses the handed-in robot passes, each with its plain run and nudged runs (free, after the
  hand-in) and no critical design-review finding. The hand-in is refused while simulations are left unless the file
  already passed all ten courses in this task.
"""
from __future__ import annotations

import json
import os
import shutil
import threading
import time

from .. import courses, printed, simulate
from ..validate import validate as _validate
from . import config as C
from .task import GIVE_UP, PHASE_GOAL, Task, sha

PHASE_GOAL["all_in_one"] = "one robot that passes as many of the 10 level-1 courses as possible"


def _kind(pid: str) -> str | None:
    from ..core import parts as P  # noqa: PLC0415

    try:
        return getattr(P.get_part(pid), "kind", None)
    except KeyError:
        return None


class AllInOneTask(Task):
    def __init__(self, task_dir: str, log):
        super().__init__("all_in_one", 1, task_dir, log)
        self.custom_allowed = True
        self.max_mm, self.copies = C.ALL_IN_ONE["max_mm"], C.ALL_IN_ONE["copies"]
        self.bench_pass: dict[str, set] = {b: set() for b in courses.BENCHES}  # bench -> passing derived shas
        self.bench_best: dict[str, dict] = {}
        self._pass_files: dict = {}
        self.final = None
        self._derive_lock = threading.Lock()

    def public_task(self) -> dict:
        return courses.all_in_one_task()

    def budget_report(self) -> dict:
        out = super().budget_report()
        out["printed_part"] = (f"allowed: any number of part types, up to {self.copies} copies each, each fitting "
                               f"{self.max_mm:g} mm per side (brick-bench part)")
        out["benches_passed_by_file"] = {
            b: {"passed_files": sorted({os.path.basename(x) for x in self._pass_files.get(b, [])})[-5:],
                "best_progress": (self.bench_best.get(b) or {}).get("max_progress")} for b in self.bench_pass}
        return out

    def derive(self, path: str, bench: str) -> str:
        """the single-course design file: the assembly with motor_program = motor_programs[bench]"""
        d = json.load(open(path))
        progs = d.get("motor_programs")
        if not isinstance(progs, dict) or bench not in progs:
            raise ValueError(f"the design has no motor program for '{bench}' (motor_programs.{bench})")
        d["motor_program"] = progs[bench]
        d.pop("motor_programs", None)
        out = os.path.join(self.ws, "_derived", f"{sha(path)[:10]}_{bench}.json")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        tmp = f"{out}.{threading.get_ident()}.tmp"
        with open(tmp, "w") as fh:
            json.dump(d, fh, indent=1)
        os.replace(tmp, out)
        return out

    def specs_of(self, path: str) -> list[str]:
        return [self.custom[i] for i in printed.ids_in(path) if i in self.custom]

    def validate(self, path: str, bench: str | None = None) -> dict:
        d = json.load(open(path))
        errs = []
        bad = sorted({p.get("part") for p in d.get("parts", []) if _kind(p.get("part", "")) in C.BANNED_ALL_IN_ONE})
        if bad:
            errs.append(f"structure must be printed: no bricks, beam bricks, liftarms, frames or plates ({', '.join(bad)})")
        errs += [f"part '{i}': not a printed part of this task (register yours with brick-bench part)"
                 for i in printed.ids_in(path) if i not in self.custom]
        if errs:
            return {"ok": False, "errors": errs, "warnings": [], "stats": {}}
        if bench is not None:  # one course: the derived single-course file
            if "motor_programs" in d:
                path = self.derive(path, bench)
            return _validate(path, bench, 1)
        if "motor_programs" not in d:
            return {"ok": False, "errors": ["the design needs motor_programs: {bench: program} for each bench you "
                                            "attempt (every bench of the 10 for the hand-in)"], "warnings": [], "stats": {}}
        out = {"ok": True, "errors": [], "warnings": [], "stats": {}, "benches": {}}
        for b in courses.BENCHES:  # the assembly with each course's program, on each course's rules
            try:
                v = _validate(self.derive(path, b), b, 1)
            except ValueError as e:
                v = {"ok": False, "errors": [str(e)], "warnings": [], "stats": {}}
            out["benches"][b] = "ok" if v["ok"] else "errors"
            out["ok"] &= v["ok"]
            out["errors"] += [f"{b}: {e}" for e in v["errors"] if f"{b}: {e}" not in out["errors"]]
            out["warnings"] += [w for w in v["warnings"] if w not in out["warnings"]]
            out["stats"] = out["stats"] or v.get("stats", {})
            if v.get("review") is not None:
                rv = out.setdefault("review", {"critical": [], "warnings": []})
                rv["critical"] += [c for c in v["review"]["critical"] if c not in rv["critical"]]
                rv["warnings"] += [w for w in v["review"]["warnings"] if w not in rv["warnings"]]
        out["errors"], out["warnings"] = out["errors"][:60], out["warnings"][:20]
        if "review" in out:
            out["review"]["critical"], out["review"]["warnings"] = out["review"]["critical"][:20], out["review"]["warnings"][:20]
            out["review"]["verdict"] = ("buildable" if not out["review"]["critical"] else
                                        "NOT buildable as designed: fix the critical findings before you submit")
        ids = printed.ids_in(path)
        if ids:
            out["printed_parts"] = [{"id": i, **{k: json.load(open(self.custom[i]))[k] for k in ("mass_g", "size_mm")}}
                                    for i in ids]
        return out

    def call(self, name: str, args: dict) -> tuple[str, list]:
        if name == "submit" and args.get("best_attempt"):
            return json.dumps({"submitted": False, "reason": "no best attempt here: hand in your robot with "
                                                             "brick-bench submit <file>"}), []
        return super().call(name, args)

    def simulate(self, path: str, bench: str | None = None) -> tuple[str, list]:
        if not bench:
            return json.dumps({"error": "name the bench: brick-bench simulate <design.json> --bench <" +
                                        "|".join(courses.BENCHES) + "> (no simulation used)"}), []
        try:
            courses.check(bench, 1)
            derived = self.derive(path, bench)
        except ValueError as e:
            return json.dumps({"error": f"{e} (no simulation used)"}), []
        snap = os.path.join(self.ws, "_simulated", f"{self.used['sims'] + 1:03d}_{bench}_{os.path.basename(path)}")
        os.makedirs(os.path.dirname(snap), exist_ok=True)
        shutil.copy(path, snap)
        with self.lock:
            if self.used["sims"] >= self.budget["sims"]:
                return json.dumps({"error": "no simulations left: hand in your robot (brick-bench submit <file>)"}), []
            if self.hours_left() <= 0:
                return json.dumps({"error": "no time left"}), []
            v = self.validate(derived, bench)
            if not v["ok"]:
                return json.dumps({"error": "the design does not validate on this bench (no simulation used)", **v},
                                  indent=1), []
            self.used["sims"] += 1
        self.log({"event": "sim_start", "phase": self.phase, "bench": bench, "path": os.path.relpath(path, self.ws)})
        r = simulate.run(derived, bench, 1, video=True, printed_specs=self.specs_of(derived), tag=f"{bench}_L1_all")
        s = simulate.summary(r)
        if "error" in r and "no result" in str(r.get("error")):
            with self.lock:
                self.used["sims"] -= 1
            s["note"] = "the simulator failed to produce a result (not counted against your budget); run it again"
        if s.get("passed"):
            self.bench_pass[bench].add(sha(derived))
            self._pass_files.setdefault(bench, []).append(snap)
        if "error" not in s:
            self.sim_info[sha(path) + bench] = {"snap": snap, "bench": bench,
                                                **{k: s.get(k) for k in ("passed", "failure", "max_progress", "time_s")}}
            b0 = self.bench_best.get(bench)
            if b0 is None or (bool(s.get("passed")), s.get("max_progress") or 0) >= (bool(b0.get("passed")),
                                                                                      b0.get("max_progress") or 0):
                self.bench_best[bench] = {k: s.get(k) for k in ("passed", "failure", "max_progress", "time_s")}
        self.log({"event": "sim_done", "phase": self.phase, "bench": bench, "path": os.path.relpath(path, self.ws),
                  "summary": s, "dir": r.get("_dir")})
        s["bench"] = bench
        s["this_file_passes"] = self.passes_of(path)
        s["budget"] = self.remaining()
        return json.dumps(s, indent=1), self._out_imgs(r.get("_contact_sheets") or [])

    def passes_of(self, path: str) -> list:
        """the courses this exact assembly + its program for that course passed in this task"""
        out = []
        for b in self.bench_pass:
            try:
                if sha(self.derive(path, b)) in self.bench_pass[b]:
                    out.append(b)
            except ValueError:
                pass
        return out

    def submit(self, p: str, notes: str = "") -> str:
        rec = self.phases[self.phase]
        rec["submits"] += 1
        v = self.validate(p)
        # a robot that does not fit one course (e.g. too long for its start board) just fails that course in the
        # scoring: the hand-in is refused only for errors that are not course-specific, or when it fits no course
        bad_b = {e.split(":", 1)[0] for e in v.get("errors") or [] if e.split(":", 1)[0] in courses.BENCHES}
        general = [e for e in v.get("errors") or [] if e.split(":", 1)[0] not in courses.BENCHES]
        if not v["ok"] and (general or len(bad_b) == len(courses.BENCHES)):
            return json.dumps({"submitted": False, "reason": "the design does not validate", **v}, indent=1)
        crit = (v.get("review") or {}).get("critical") or []
        warned = self.__dict__.setdefault("_review_warned", set())
        if crit and sha(p) not in warned:  # a critical review finding fails every course: warn once
            warned.add(sha(p))
            return json.dumps({"submitted": False, "reason": (
                "the design review found critical problems: the robot would not survive being built and run for real, "
                "so EVERY bench fails in the scoring. Fix them (brick-bench validate shows them; it is free) and hand in "
                "the fixed file. Handing in this same file again is accepted, and scores 0."),
                "critical": crit, "budget": self.remaining()}, indent=1)
        passes = self.passes_of(p)
        rem = self.remaining()
        if (len(passes) < len(self.bench_pass) and rem["sims_left"] > 0 and rem["hours_left"] > C.BEST_ATTEMPT_MIN_H
                and self.used["sims"] < C.ALL_IN_ONE["min_sims"]):
            return json.dumps({"submitted": False, "reason": (
                f"refused: this file passes {len(passes)} of 10 benches ({', '.join(passes) or 'none'}) and you still "
                f"have {rem['sims_left']} simulations and {rem['hours_left']} h. " + GIVE_UP +
                f" Hand it in when it passes all 10 or once you have used {C.ALL_IN_ONE['min_sims']} simulations."),
                "budget": rem}, indent=1)
        acc_dir = os.path.join(self.ws, "accepted")
        os.makedirs(acc_dir, exist_ok=True)
        dst = os.path.join(acc_dir, "all_in_one.json")
        shutil.copy(p, dst)
        self.log({"event": "final_scoring_start", "file": os.path.relpath(p, self.ws)})
        res = score_robot(dst, self.custom, self.derive)
        n = sum(r["passed"] for r in res.values())
        st = v.get("stats") or {}
        acc = {"file": os.path.relpath(dst, self.ws), "submitted_file": os.path.relpath(p, self.ws), "sha": sha(p),
               "notes": notes, "benches_passed": n, "benches": res, "mass_g": st.get("mass_g"),
               "n_parts": st.get("n_parts"), "printed_parts": printed.ids_in(p), "sims_used": self.used["sims"],
               "hours": round((time.time() - self.t0) / 3600, 3), "at": time.time()}
        with self.lock:
            rec["accepted"] = acc
            self.final = self.goal = acc
            self.state = "accepted"
        self.log({"event": "accepted", "phase": self.phase, **{k: v_ for k, v_ in acc.items() if k != "benches"}})
        return json.dumps({"submitted": True, "benches_passed": n, "per_bench": {b: r["passed"] for b, r in res.items()},
                           "note": "scored. End your turn now."}, indent=1)

    def auto_final(self) -> None:
        """no hand-in: the simulated file that passed the most courses (ties: the latest) is scored for the agent"""
        if self.final is not None:
            return
        snaps = sorted({x["snap"] for x in self.sim_info.values()})
        if not snaps:
            return
        best = max(snaps, key=lambda f: (len(self.passes_of(f)), f))
        self.state = "open"
        self.used["sims"] = self.budget["sims"]  # (so the hand-in is not refused)
        self.submit(best, "auto: no hand-in; the simulated file that passed the most benches")
        if self.final:
            self.final["auto"] = True


def score_robot(path: str, specs: dict, derive=None, out_root: str | None = None) -> dict:
    """the All-in-one score of a robot file: per course, the plain run + its nudged runs and no critical review
    finding -> {bench: {"passed", "plain", "nudges", "review_critical"}}. ``specs``: printed part id -> spec.json."""
    from concurrent.futures import ThreadPoolExecutor  # noqa: PLC0415

    for sp in specs.values():
        printed.register(sp)

    def _derive(b):
        if derive:
            return derive(path, b)
        d = json.load(open(path))
        d["motor_program"] = (d.get("motor_programs") or {})[b]
        d.pop("motor_programs", None)
        od = out_root or os.path.dirname(os.path.abspath(path))
        f = os.path.join(od, "_derived", f"{b}.json")
        os.makedirs(os.path.dirname(f), exist_ok=True)
        json.dump(d, open(f, "w"), indent=1)
        return f

    def one(b):
        try:
            der = _derive(b)
        except (KeyError, ValueError, TypeError):
            return b, {"passed": False, "reason": f"no motor program for {b}"}
        ps = [specs[i] for i in printed.ids_in(der) if i in specs]
        vb = _validate(der, b, 1)
        if not vb["ok"]:
            return b, {"passed": False, "reason": "does not validate", "errors": vb["errors"][:5]}
        crit = (vb.get("review") or {}).get("critical") or []
        r = simulate.run_retry(der, b, 1, video=True, printed_specs=ps, tag=f"final_{b}")
        s = simulate.summary(r)
        nud = simulate.nudged(der, b, 1, printed_specs=ps, video=True) if s.get("passed") else []
        ok = bool(s.get("passed")) and all(x.get("passed") for x in nud) and not crit
        return b, {"passed": ok, "plain": {k: s.get(k) for k in ("passed", "failure", "max_progress", "time_s")},
                   "nudges": nud, "review_critical": crit[:5], "dir": r.get("_dir")}
    with ThreadPoolExecutor(5) as ex:
        return dict(ex.map(one, courses.BENCHES))
