"""One benchmark task (one obstacle level, or the All-in-one task) and the tools an agent calls through `brick-bench`:
budgets per phase, the acceptance check (a simulator pass, the two nudged runs, no critical design-review finding),
best attempts, and the printed part.

Phases: ``cross`` (pass the level), ``print`` (only if Cross was not accepted: 30 more simulations and one printed part
type), then the closing ``wrap-up`` turn (lessons.md). ``light`` / ``fast`` run in their own fresh sessions: every
accepted design is kept, the lightest / fastest counts and the whole budget is used. ``all_in_one``: one robot for the
ten level-1 courses (robobuilder.harness.all_in_one)."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import threading
import time

from .. import courses, printed, simulate
from ..validate import validate as _validate
from . import config as C

PHASE_GOAL = {"cross": "pass the level", "print": "pass the level; one custom printed part allowed",
              "light": "the lightest design that passes", "fast": "the fastest crossing that passes"}
FRESH_KEY = {"light": "mass_g", "fast": "time_s"}
GIVE_UP = ("Stopping early is not allowed: the task is only over when a design is accepted or the budget is used up. "
           "Unused simulations and time are not saved and earn nothing; a task you stop early counts as failed. "
           "Spend them: build and simulate the idea you think could work, even a large build, or a different "
           "mechanism, and learn from each run.")
DOCS = ("rules", "benches", "parts", "design_format", "manufacturing_constraints", "motor_program", "simulator",
        "example_design", "custom_part")


def sha(path: str) -> str:
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


class Task:
    def __init__(self, bench: str, level: int, task_dir: str, log, memory_dir: str | None = None):
        self.bench, self.level = bench, level
        self.task_dir = os.path.abspath(task_dir)
        self.ws = os.path.join(self.task_dir, "workspace")
        os.makedirs(self.ws, exist_ok=True)
        self.log = log
        self.memory_dir = memory_dir
        self.lock = threading.Lock()
        self.phase, self.state = None, "closed"  # state: open | accepted | closed
        self.phases: dict[str, dict] = {}
        self.budget = {"sims": 0, "hours": 0.0}
        self.used = {"sims": 0}
        self.t0 = time.time()
        self.custom_allowed = False
        self.max_mm, self.copies = C.PRINT_MAX_MM, C.PRINT_COPIES
        self.custom: dict[str, str] = {}  # printed part id -> spec.json (registered in this task)
        self.pass_info: dict[str, dict] = {}  # sha of a design file -> its passing plain run
        self.nudge_cache: dict[str, list] = {}
        self.nudge_runs: dict[str, list] = {}
        self.sim_info: dict[str, dict] = {}  # sha -> the latest simulation of that file
        self.best = None  # (rank, snapshot) of the furthest simulated design of the phase
        self._best_summary = None
        self.goal = None  # the accepted record that passed the level (cross or print)
        self.fresh = False  # a Light / Fast session
        self.n_part_builds = 0

    # ------------------------------------------------------------------ phases
    def start_phase(self, name: str, sims: int, hours: float) -> None:
        with self.lock:
            self.phase, self.state = name, "open"
            self.budget = {"sims": sims, "hours": hours}
            self.used = {"sims": 0}
            self.t0 = time.time()
            self.best = None
            if name == "print":
                self.custom_allowed = True
            self.phases[name] = {"phase": name, "goal": PHASE_GOAL.get(name, name), "started": self.t0, "ended": None,
                                 "budget": {"sims": sims, "hours": hours}, "used": self.used, "accepted": None,
                                 "best_attempt": None, "submits": 0, "stop": None}
        self.log({"event": "phase_start", "phase": name, "budget": self.phases[name]["budget"]})

    def end_phase(self, stop: str) -> dict:
        rec = self.phases[self.phase]
        with self.lock:
            self.state = "closed"
        rec["ended"] = time.time()
        rec["stop"] = stop
        rec["hours"] = round((rec["ended"] - rec["started"]) / 3600, 3)
        if rec["accepted"] is None and rec.get("best_attempt") is None and self.best and self.phase in ("cross", "print"):
            # every Cross / Cross+Print phase ends with a submission: without one, the furthest-progress simulated
            # design is recorded for the agent (flagged auto)
            rec["best_attempt"] = self._record_best_attempt(self.best[1], dict(self._best_summary or {}), auto=True)
        self.log({"event": "phase_end", "phase": self.phase, "stop": stop, "accepted": bool(rec["accepted"]),
                  "used": dict(self.used)})
        return rec

    def pause_clock(self, queue_s) -> None:
        """Light / Fast: time spent waiting for a simulator slot is not charged"""
        if self.fresh and queue_s:
            with self.lock:
                self.t0 += float(queue_s)

    def hours_left(self) -> float:
        return self.budget["hours"] - (time.time() - self.t0) / 3600

    def remaining(self) -> dict:
        return {"phase": self.phase, "sims_left": self.budget["sims"] - self.used["sims"],
                "hours_left": round(self.hours_left(), 2)}

    def budget_report(self) -> dict:
        out = {"phase": self.phase, "phase_goal": PHASE_GOAL.get(self.phase or "", ""),
               "status": {"open": "open", "accepted": "accepted: end your turn; the next request follows",
                          "closed": "closed: no simulations or submissions now"}[self.state],
               "sims_left": self.budget["sims"] - self.used["sims"], "sims_used": self.used["sims"],
               "sims_this_phase": self.budget["sims"], "hours_left": round(self.hours_left(), 2),
               "printed_part": (f"allowed: one part type, up to {self.copies} copies (brick-bench part)"
                                if self.custom_allowed else "not allowed")}
        if self.custom:
            out["printed_part_ids"] = sorted(self.custom)
        ba = (self.phases.get(self.phase) or {}).get("best_attempt")
        if ba:
            out["best_attempt_submitted"] = f"{ba['file']} (progress {ba['max_progress']})"
        done = {}
        for n, r in self.phases.items():
            if n == self.phase:
                continue
            a = r.get("accepted")
            done[n] = (f"accepted: {a['file']} ({a['mass_g']} g, {a['time_s']} s, {a['sims_used']} sims)" if a
                       else f"not accepted ({r['used']['sims']} sims)")
        if done:
            out["earlier_phases"] = done
        return out

    # ------------------------------------------------------------------ tools
    def _path(self, p: str) -> str:
        p = p or ""
        if p == "/work" or p.startswith("/work/"):
            p = p[len("/work"):].lstrip("/")
        full = os.path.realpath(os.path.join(self.ws, p))
        if not full.startswith(os.path.realpath(self.ws) + os.sep):
            raise ValueError("paths must stay inside the task workspace")
        if not os.path.exists(full):
            raise FileNotFoundError(f"no such file in the workspace: {p}")
        return full

    def call(self, name: str, args: dict) -> tuple[str, list]:
        """-> (text result, list of image paths)"""
        try:
            if name == "read_doc":
                return self.read_doc(args["name"]), []
            if name == "budget":
                return json.dumps(self.budget_report(), indent=1), []
            if name == "validate":
                return json.dumps(self.validate(self._path(args["path"]), args.get("bench")), indent=1), []
            if name in ("simulate", "submit", "part") and self.state != "open":
                why = ("this phase's design was accepted: end your turn now; the harness sends the next request"
                       if self.state == "accepted" else "simulations, submissions and parts are closed now")
                return json.dumps({"error": why}), []
            if name == "part":
                return self.part(self._path(args["path"])), []
            if name == "submit":
                if args.get("best_attempt"):
                    return self.submit_best_attempt(self._path(args["path"]), args.get("notes", "")), []
                return self.submit(self._path(args["path"]), args.get("notes", "")), []
            if name == "simulate":
                return self.simulate(self._path(args["path"]), bench=args.get("bench"))
            return json.dumps({"error": f"unknown tool {name}"}), []
        except Exception as e:  # noqa: BLE001  (tool errors go back to the agent)
            return json.dumps({"error": f"{type(e).__name__}: {e}"}), []

    def public_task(self) -> dict:
        return courses.task(self.bench, self.level)

    def read_doc(self, name: str) -> str:
        if name == "task":
            return json.dumps(self.public_task(), indent=1)
        if name not in DOCS:
            raise ValueError(f"unknown document {name}")
        return open(os.path.join(C.DOCS, "example_design.json" if name == "example_design" else f"{name}.md")).read()

    def specs_of(self, path: str) -> list[str]:
        return [self.custom[i] for i in printed.ids_in(path) if i in self.custom]

    def validate(self, path: str, bench: str | None = None) -> dict:
        ids = printed.ids_in(path)
        errs = [f"part '{i}': not a printed part of this task (register yours with brick-bench part)"
                for i in ids if i not in self.custom]
        if len(ids) > 1:
            errs.append(f"one printed part type per design ({len(ids)} used: {ids})")
        if errs:
            return {"ok": False, "errors": errs, "warnings": [], "stats": {}}
        out = _validate(path, self.bench, self.level)
        if ids:
            sp = json.load(open(self.custom[ids[0]]))
            out["printed_part"] = {"id": ids[0], "mass_g": sp["mass_g"], "size_mm": sp["size_mm"]}
        return out

    def _out_imgs(self, imgs: list) -> list:
        return [p for p in imgs if os.path.exists(p)]

    def simulate(self, path: str, bench: str | None = None) -> tuple[str, list]:
        snap = os.path.join(self.ws, "_simulated", f"{self.phase}{self.used['sims'] + 1:03d}_{os.path.basename(path)}")
        os.makedirs(os.path.dirname(snap), exist_ok=True)
        shutil.copy(path, snap)  # the exact file simulated (the agent may overwrite it later)
        with self.lock:
            if self.used["sims"] >= self.budget["sims"]:
                return json.dumps({"error": "no simulations left in this phase"}), []
            if self.hours_left() <= 0:
                return json.dumps({"error": "no time left in this phase"}), []
            v = self.validate(path)
            if not v["ok"]:
                return json.dumps({"error": "the design does not validate (no simulation used)", **v}, indent=1), []
            self.used["sims"] += 1
        self.log({"event": "sim_start", "phase": self.phase, "path": os.path.relpath(path, self.ws)})
        r = simulate.run(path, self.bench, self.level, video=True, printed_specs=self.specs_of(path),
                         tag=f"{self.bench}_L{self.level}_{self.phase}")
        self.pause_clock(r.get("_queue_s"))
        s = simulate.summary(r)
        if "error" in r and "no result" in str(r.get("error")):  # simulator crash / hang: not charged
            with self.lock:
                self.used["sims"] -= 1
            s["note"] = "the simulator failed to produce a result (not counted against your budget); run it again"
        h = sha(path)
        if s.get("passed"):
            st = v.get("stats") or {}
            self.pass_info[h] = {**{k: s.get(k) for k in ("time_s", "max_progress", "failure")},
                                 "mass_g": st.get("mass_g"), "n_parts": st.get("n_parts")}
        if "error" not in s:
            self.sim_info[h] = {"snap": snap, "phase": self.phase,
                                **{k: s.get(k) for k in ("passed", "failure", "max_progress", "max_progress_m", "time_s")}}
            rank = (bool(s.get("passed")), float(s.get("max_progress") or 0.0), self.used["sims"])
            if self.best is None or rank >= self.best[0]:
                self.best = (rank, snap)
                self._best_summary = {k: s.get(k) for k in ("passed", "failure", "max_progress", "max_progress_m",
                                                             "time_s")}
        self.log({"event": "sim_done", "phase": self.phase, "path": os.path.relpath(path, self.ws), "bench": self.bench,
                  "summary": s, "dir": r.get("_dir")})
        s["budget"] = self.remaining()
        return json.dumps(s, indent=1), self._out_imgs(r.get("_contact_sheets") or [])

    def nudge_check(self, path: str) -> list:
        h = sha(path)
        if h in self.nudge_cache:  # the simulator is deterministic: a resubmitted file costs nothing
            return self.nudge_cache[h]
        self.log({"event": "nudge_start", "path": os.path.relpath(path, self.ws)})
        runs = simulate.nudged(path, self.bench, self.level, printed_specs=self.specs_of(path), video=True)
        bad = [x for x in runs if not x.get("passed")]
        self.nudge_cache[h], self.nudge_runs[h] = bad, runs
        self.log({"event": "nudge_done", "path": os.path.relpath(path, self.ws), "failed": bad})
        return bad

    def _record_best_attempt(self, src: str, summary: dict, auto: bool, notes: str = "") -> dict:
        acc_dir = os.path.join(self.ws, "accepted")
        os.makedirs(acc_dir, exist_ok=True)
        dst = os.path.join(acc_dir, f"{self.phase}_best_attempt.json")
        shutil.copy(src, dst)
        rec = {"file": os.path.relpath(dst, self.ws), "auto": auto, "notes": notes,
               "max_progress": summary.get("max_progress"), "max_progress_m": summary.get("max_progress_m"),
               "failure": summary.get("failure"), "passed_plain_run": summary.get("passed"),
               "printed_part": (printed.ids_in(src) or [None])[0], "sims_used": self.used["sims"], "at": time.time()}
        self.log({"event": "best_attempt", "phase": self.phase, **rec})
        return rec

    def submit_best_attempt(self, p: str, notes: str = "") -> str:
        """Cross / Cross+Print: hand in the design that got furthest when nothing passed (it must have been simulated
        in this task; no nudged runs). Refused while simulations and time are left."""
        if self.phase not in ("cross", "print"):
            return json.dumps({"submitted": False, "reason": "a best attempt is only for the pass-the-level request"})
        rem0 = self.remaining()
        if rem0["sims_left"] > 0 and rem0["hours_left"] > C.BEST_ATTEMPT_MIN_H:
            self.log({"event": "best_attempt_refused", "phase": self.phase, **rem0})
            return json.dumps({"submitted": False, "reason": (
                f"refused: you still have {rem0['sims_left']} simulations and {rem0['hours_left']} h. A best attempt "
                "is only accepted once your simulations are used up. " + GIVE_UP)})
        info = self.sim_info.get(sha(p))
        if info is None:
            return json.dumps({"submitted": False, "reason": (
                "this exact design file has not been simulated: a best attempt must be a design you simulated "
                "(submit the file of your furthest run; every simulated file is also in /work/_simulated/)")})
        rec = self._record_best_attempt(p, info, auto=False, notes=notes)
        self.phases[self.phase]["best_attempt"] = rec
        best = max((v.get("max_progress") or 0.0 for v in self.sim_info.values()), default=0.0)
        rem = self.remaining()
        msg = {"submitted": True, "accepted": False, "best_attempt": rec["file"], "max_progress": rec["max_progress"],
               "note": ("recorded as your best attempt: it is not a pass. "
                        + (f"You still have {rem['sims_left']} simulations and {rem['hours_left']} h: keep trying to "
                           "pass; a later best attempt replaces this one." if rem["sims_left"] > 0 and
                           rem["hours_left"] > 0 else "Your budget for this request is used up: end your turn."))}
        if (rec["max_progress"] or 0.0) < best - 1e-9:
            msg["warning"] = f"another simulated design got further (progress {best}); submit that one instead?"
        return json.dumps(msg, indent=1)

    def submit(self, p: str, notes: str = "") -> str:
        rec = self.phases[self.phase]
        rec["submits"] += 1
        v = self.validate(p)
        if not v["ok"]:
            return json.dumps({"submitted": False, "reason": "the design does not validate", **v}, indent=1)
        if (v.get("review") or {}).get("critical"):
            return json.dumps({"submitted": False, "reason": (
                "the design review found critical problems: it would not survive being built and run for real. Fix "
                "them (see brick-bench validate) and simulate the fixed design."),
                "critical": v["review"]["critical"], "budget": self.remaining()}, indent=1)
        h = sha(p)
        if h not in self.pass_info:
            return json.dumps({"submitted": False, "reason": (
                "this exact design file has not passed a simulation yet. Keep iterating until a design passes, then "
                "submit that file."), "budget": self.remaining()})
        bad = self.nudge_check(p)
        if bad:
            return json.dumps({"submitted": False, "reason": (
                f"reliability check: this design passes, but {len(bad)} of {len(simulate.NUDGES)} nudged runs failed "
                "(the car 1 mm off centre; every motor command after the first 50 ms later; not charged to your "
                "budget). It passes only by a hair: give it margin and simulate again."), "nudge_failures": bad,
                "budget": self.remaining()}, indent=1)
        acc_dir = os.path.join(self.ws, "accepted")
        os.makedirs(acc_dir, exist_ok=True)
        dst = os.path.join(acc_dir, f"{self.phase}.json")
        info, st, ids = self.pass_info[h], v.get("stats") or {}, printed.ids_in(p)
        acc = {"file": os.path.relpath(dst, self.ws), "submitted_file": os.path.relpath(p, self.ws), "sha": h,
               "notes": notes, "mass_g": st.get("mass_g", info.get("mass_g")),
               "n_parts": st.get("n_parts", info.get("n_parts")), "time_s": info.get("time_s"),
               "nudges": [{k: x.get(k) for k in ("nudge", "passed", "time_s")} for x in self.nudge_runs.get(h, [])],
               "review_warnings": len((v.get("review") or {}).get("warnings") or []),
               "printed_part": ids[0] if ids else None, "printed_part_spec": self.custom.get(ids[0]) if ids else None,
               "sims_used": self.used["sims"], "hours": round((time.time() - self.t0) / 3600, 3), "at": time.time()}
        if self.fresh and self.phase in FRESH_KEY:  # every acceptance kept, the best counts, the phase stays open
            key = FRESH_KEY[self.phase]
            allr = rec.setdefault("accepted_all", [])
            dst2 = os.path.join(acc_dir, f"{self.phase}_{len(allr) + 1:02d}.json")
            shutil.copy(p, dst2)
            acc["file"] = os.path.relpath(dst2, self.ws)
            prev = rec["accepted"]
            better = prev is None or (acc.get(key) is not None and (prev.get(key) is None or acc[key] < prev[key]))
            with self.lock:
                allr.append({k: acc.get(k) for k in ("file", "mass_g", "n_parts", "time_s", "sims_used", "hours",
                                                      "printed_part")})
                if better:
                    rec["accepted"] = acc
                    shutil.copy(p, dst)
            best = rec["accepted"]
            self.log({"event": "accepted", "phase": self.phase, "best": better, **acc})
            unit = "g" if key == "mass_g" else "s"
            rem = self.remaining()
            return json.dumps({"submitted": True, "accepted": True, "phase": self.phase, "file": acc["file"],
                               "mass_g": acc["mass_g"], "time_s": acc["time_s"], "your_best_so_far": better,
                               f"best_accepted_{key}": best.get(key), "best_accepted_file": best["file"],
                               "accepted_so_far": len(allr), "budget": rem,
                               "note": (f"accepted{' and your best so far' if better else f', but not better than your best ({best.get(key)} {unit})'}"
                                        f". Do not end your turn: you have {rem['sims_left']} simulations and "
                                        f"{rem['hours_left']} h left. Keep improving and submit every better passing "
                                        "design; your best accepted design counts.")}, indent=1)
        shutil.copy(p, dst)
        with self.lock:
            rec["accepted"] = acc
            self.state = "accepted"
            if self.phase in ("cross", "print"):
                self.goal = acc
        self.log({"event": "accepted", "phase": self.phase, **acc})
        return json.dumps({"submitted": True, "accepted": True, "phase": self.phase, "file": acc["file"],
                           "mass_g": acc["mass_g"], "time_s": acc["time_s"],
                           "note": "accepted. End your turn now: the harness sends the next request."}, indent=1)

    # ------------------------------------------------------------------ the printed part
    def part(self, script: str) -> str:
        if not self.custom_allowed:
            return json.dumps({"error": "no printed part in this phase"})
        self.n_part_builds += 1
        out_rel = os.path.join("_custom", f"build{self.n_part_builds:02d}")
        ok, logtxt = printed.build(self.ws, script, out_rel)
        self.log({"event": "part_build", "script": os.path.relpath(script, self.ws), "ok": ok, "log": logtxt[-3000:]})
        if not ok:
            return json.dumps({"registered": False, "reason": "the CAD script failed", "log": logtxt[-3000:]}, indent=1)
        stl = os.path.join(self.ws, out_rel, "part.stl")
        itf = json.load(open(os.path.join(self.ws, out_rel, "interfaces.json")))
        rep = printed.analyze_safe(stl, itf, max_mm=self.max_mm)
        pub = {k: v for k, v in rep.items() if not k.startswith("_")}
        if not rep["ok"]:
            self.log({"event": "part_rejected", "report": pub})
            return json.dumps({"registered": False, "reason": "printability / interface check failed", **pub},
                              indent=1, default=str)
        spec_p = printed.make_spec(rep, stl, itf, os.path.join(self.task_dir, "printed"), script, copies=self.copies)
        pid = printed.register(spec_p)
        self.custom[pid] = spec_p
        view = os.path.join(self.ws, "printed_parts")
        os.makedirs(view, exist_ok=True)
        shutil.copy(stl, os.path.join(view, f"{pid}.stl"))
        spec = json.load(open(spec_p))  # the catalogue entry for the agent's own library (bricks.printed.load_part)
        json.dump(spec, open(os.path.join(view, f"{pid}.json"), "w"), indent=1, default=str)
        self.log({"event": "part_registered", "id": pid, "spec": spec_p, "report": pub})
        return json.dumps({"registered": True, "part_id": pid, "copies": self.copies,
                           "stl": f"/work/printed_parts/{pid}.stl",
                           "use": f"a part with \"part\": \"{pid}\" in your design; its frame is your CAD frame. "
                                  f"In Python: from bricks.printed import load_part; "
                                  f"load_part('/work/printed_parts/{pid}.json')",
                           **{k: pub[k] for k in ("size_mm", "mass_g", "com_mm", "volume_cm3", "min_wall_mm",
                                                  "mass_model", "warnings", "notes", "collision")}},
                          indent=1, default=str)

    def register_parts(self, specs: dict) -> None:
        """make earlier printed parts usable again (a continued session): part id -> spec.json"""
        for pid, sp in specs.items():
            if os.path.exists(sp):
                printed.register(sp)
                self.custom[pid] = sp

    # ------------------------------------------------------------------ sandbox hooks
    def extra_binds(self) -> list[str]:
        if self.memory_dir and os.path.isdir(self.memory_dir):
            os.makedirs(os.path.join(self.ws, "memory"), exist_ok=True)
            return ["--ro-bind", self.memory_dir, "/work/memory"]
        return []
