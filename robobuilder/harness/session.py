"""The request flow of each task, as messages to one agent session.

Cross task: the Cross prompt (30 simulations); if no design was accepted, the Cross+Print extension in the same
session (30 more simulations, one printed part type); then the closing turn that asks for lessons.md. An agent that
stops early while budget is left is reminded (at most MAX_NUDGES times).
Light / Fast: a fresh session with the Cross prompt turned into "the lightest / fastest robot that passes"
(50 simulations): every accepted design is kept, the best counts, the whole budget is used.
All-in-one: one session, 300 simulations, one robot for the ten level-1 courses."""
from __future__ import annotations

import os
import shutil

from .. import courses
from . import config as C
from .broker import Broker
from .task import GIVE_UP

NUDGE = {
    "cross": ("You stopped before a design was accepted. You still have budget left (`brick-bench budget`). " + GIVE_UP +
              " Keep iterating until a design passes in simulation, then submit it with `brick-bench submit <file>`. "
              "Only when your simulations are used up with nothing passed, submit your furthest-progress design with "
              "`brick-bench submit --best-attempt <file>`."),
    "print": ("You stopped before a design was accepted. You still have budget left (`brick-bench budget`). " + GIVE_UP +
              " Keep iterating (with your printed part if it helps) until a design passes, then submit it with "
              "`brick-bench submit <file>`. Only when your simulations are used up with nothing passed, submit your "
              "furthest-progress design with `brick-bench submit --best-attempt <file>`."),
    "light": ("You still have budget left (`brick-bench budget`). " + GIVE_UP + " Keep looking for a lighter passing "
              "design (refine your lightest one or try a quite different concept) and submit every lighter design that "
              "passes with `brick-bench submit <file>`; your lightest accepted design counts. Continue until your "
              "simulations are used up."),
    "fast": ("You still have budget left (`brick-bench budget`). " + GIVE_UP + " Keep looking for a faster passing "
             "design (refine your fastest one or try a quite different concept) and submit every faster design that "
             "passes with `brick-bench submit <file>`; your fastest accepted design counts. Continue until your "
             "simulations are used up."),
    "all_in_one": ("You stopped while you still have budget (`brick-bench budget`). " + GIVE_UP + " Keep improving the "
                   "one robot so it passes more benches (each bench can have its own motor program), re-checking the "
                   "benches it already passes when you change the hardware. When your simulations are used up (or the "
                   "robot passes all 10), hand it in with `brick-bench submit <file>`."),
}
DOC_FILES = ("rules.md", "benches.md", "parts.md", "design_format.md", "manufacturing_constraints.md",
             "motor_program.md", "simulator.md", "example_design.json")


def doc(name: str) -> str:
    return open(os.path.join(C.DOCS, name)).read()


def fill(text: str, **kw) -> str:
    for k, v in kw.items():
        text = text.replace("{" + k + "}", str(v))
    return text


def prepare(task) -> None:
    """the documents and the task file in /work/docs"""
    import json  # noqa: PLC0415

    d = os.path.join(task.ws, "docs")
    os.makedirs(d, exist_ok=True)
    for f in DOC_FILES:
        shutil.copy(os.path.join(C.DOCS, f), d)
    json.dump(task.public_task(), open(os.path.join(d, "task.json"), "w"), indent=1)


def prompt_cross(task, sims=None, hours=None) -> str:
    mem = doc("memory_section.md") if task.memory_dir and os.path.isdir(task.memory_dir) else ""
    text = doc("cli_prompt.md").replace("{memory}\n", mem)
    return fill(text, bench=task.bench, level=task.level, description=courses.description(task.bench, task.level),
                sims=sims or C.PHASES["cross"]["sims"], hours=f"{hours or C.PHASES['cross']['hours']:g}")


def prompt_extension(task) -> str:
    return fill(doc("extension_custom.md"), sims=C.PHASES["print"]["sims"], hours=f"{C.PHASES['print']['hours']:g}",
                copies=C.PRINT_COPIES, max_mm=f"{C.PRINT_MAX_MM:g}", wall=f"{C.PRINT_MIN_WALL_MM:g}")


def prompt_fresh(task, phase: str, sims: int, hours: float) -> str:
    """Light / Fast: the Cross prompt with the goal 'the lightest / fastest robot that passes'"""
    t = prompt_cross(task)
    what, key, unit = (("lightest", "the lowest total mass (`mass_g` from `brick-bench validate`)", "Every gram counts.")
                       if phase == "light" else
                       ("fastest", "the earliest time at which it reaches the goal (`time_s` of its passing simulation)",
                        "Mass and pieces do not matter for this task."))
    ln = "lighter" if phase == "light" else "faster"
    reps = [
        ("**Your goal: pass this level in the simulator.** Think about the obstacle and come up with a smart, innovative "
         "robot that solves it:",
         f"**Your goal: the {what} robot that passes this level.** A design counts only if it is accepted (a simulator "
         "pass, the nudged runs and no critical design-review finding, as `rules.md` explains); among your accepted "
         f"designs, the one with {key} is your result. {unit} Think about the obstacle and come up with a smart, "
         f"innovative robot that crosses it {'with as little mass as possible' if phase == 'light' else 'as fast as possible'}:"),
        ('  - `submit <file> --notes "..."`: hand in a design that passed a simulation, for the acceptance check.\n'
         '  - `submit --best-attempt <file>`: nothing passed: hand in your furthest-progress design.\n',
         '  - `submit <file> --notes "..."`: hand in a design that passed a simulation, for the acceptance check. Submit '
         f'as often as you like: every accepted design is kept and the {what} one counts.\n'),
        ("5. Iterate until it passes (use more pieces if needed), then submit.",
         f"5. Iterate until it passes and get it accepted early, so that you have a result. Then keep making it {ln} (or "
         f"try a quite different concept that could be much {ln}) and submit every {ln} design that passes."),
        ("Do not stop until a design is accepted or your simulations are used up: stopping early is not allowed, and "
         "unused simulations and time earn nothing. **Always end with a submission:** if nothing has passed once your "
         "simulations are used up, submit your furthest-progress design with `--best-attempt`. Further requests may "
         "follow in this session.",
         f"**Use your whole budget:** after an acceptance, do not end your turn (this replaces the rule in `rules.md` to "
         f"end your turn after an acceptance); keep looking for a {ln} design until your simulations are used up. "
         "Stopping early is not allowed, and unused simulations and time earn nothing."),
    ]
    for a_, b_ in reps:
        if a_ not in t:
            raise SystemExit(f"prompt_fresh: the Cross prompt changed ({a_[:50]}...)")
        t = t.replace(a_, b_)
    t = t.replace(f"at most {C.PHASES['cross']['sims']} simulations and {C.PHASES['cross']['hours']:g} h",
                  f"at most {sims} simulations and {hours:g} h")
    if task.custom_allowed:
        t += ("\n\n**You may design one custom 3D-printed part** for this task: one part type, up to "
              f"{C.PRINT_COPIES} copies, PLA, at most {C.PRINT_MAX_MM:g} mm, walls of at least {C.PRINT_MIN_WALL_MM:g} mm. "
              "`/work/docs/custom_part.md` explains how; `brick-bench part <script.py>` builds and checks it and gives its part id.")
    return t


def _usage_delta(u1: dict, u0: dict) -> dict:
    return {k: (round(u1.get(k, 0) - u0.get(k, 0), 4) if isinstance(u1.get(k, 0), float) else u1.get(k, 0) - u0.get(k, 0))
            for k in u1}


class Session:
    """one agent session on one task: requests, reminders, usage per request"""

    def __init__(self, agent, task, log):
        self.agent, self.task, self.log = agent, task, log
        self.home = os.path.join(task.task_dir, "agent_home")
        os.makedirs(self.home, exist_ok=True)
        agent.setup_home(self.home)
        self.phase_usage = {}

    def request(self, broker, text: str, phase: str, wrapup: bool = False) -> str:
        agent, task = self.agent, self.task
        u0 = dict(agent.usage)
        stop = "end"
        for k in range(1 if wrapup else C.MAX_NUDGES + 1):
            left_h = C.WRAPUP_MIN / 60 if wrapup else task.hours_left()
            if left_h <= 0:
                stop = "time"
                break
            self.log({"event": "cli_start", "agent": agent.name, "phase": phase, "attempt": k, "prompt": text})
            rc = agent.turn(task, self.home, broker.dir, text, self.log, timeout=left_h * 3600)
            self.log({"event": "cli_exit", "phase": phase, "returncode": rc})
            if rc == "timeout":
                if task.fresh and task.hours_left() > C.FRESH_MIN_H and k < C.MAX_NUDGES:  # the clock was paused
                    text = NUDGE[phase]
                    continue
                stop = "time"
                break
            if agent.quota:
                stop = "quota: " + agent.quota
                self.log({"event": "quota", "text": agent.quota})
                break
            if wrapup:
                stop = "done"
                break
            if task.fresh:  # the whole budget is used: remind while simulations and time are left
                rem = task.remaining()
                if rem["sims_left"] <= 0 or rem["hours_left"] < C.FRESH_MIN_H or k == C.MAX_NUDGES:
                    stop = ("budget used" if (task.phases.get(phase) or {}).get("accepted") else "no acceptance") \
                        if rc == 0 else f"cli exit {rc}"
                    break
                text = NUDGE[phase]
                self.log({"event": "nudge", "phase": phase, "text": text})
                continue
            if task.state == "accepted":
                stop = "accepted"
                break
            if task.remaining()["sims_left"] <= 0 or k == C.MAX_NUDGES:
                stop = "no submission" if rc == 0 else f"cli exit {rc}"
                break
            text = NUDGE[phase]
            self.log({"event": "nudge", "phase": phase, "text": text})
        self.phase_usage[phase] = _usage_delta(agent.usage, u0)
        return stop


def run_cross(agent, task, log, phases: str = "cross,print") -> dict:
    """Cross, then (if not accepted) Cross+Print, then the lessons turn -> {"stop", "phase_usage"}"""
    prepare(task)
    s = Session(agent, task, log)
    with Broker(task, log) as broker:
        task.start_phase("cross", **C.PHASES["cross"])
        stop = s.request(broker, prompt_cross(task), "cross")
        task.end_phase(stop)
        quota = stop.startswith("quota")
        if not quota and task.goal is None and "print" in phases:
            task.start_phase("print", **C.PHASES["print"])
            shutil.copy(os.path.join(C.DOCS, "custom_part.md"), os.path.join(task.ws, "docs", "custom_part.md"))
            stop = s.request(broker, prompt_extension(task), "print")
            task.end_phase(stop)
            quota = stop.startswith("quota")
        if not quota:
            task.phase, task.state = "wrap-up", "closed"
            w = s.request(broker, doc("wrapup.md"), "wrap-up", wrapup=True)
            if w.startswith("quota"):
                quota, stop = True, w
    if not quota:
        stop = "passed" if task.goal else "not passed"
    return {"stop": stop, "phase_usage": s.phase_usage}


def run_fresh(agent, task, log, phase: str, printed_allowed: bool) -> dict:
    """a Light / Fast session -> {"stop", "phase_usage"}"""
    prepare(task)
    task.fresh = True
    sims, hours = C.PHASES[phase]["sims"], C.LIGHT_FAST_HOURS[task.level]
    if printed_allowed:  # the rules the pass was judged on: a printed part allowed
        task.custom_allowed = True
        shutil.copy(os.path.join(C.DOCS, "custom_part.md"), os.path.join(task.ws, "docs", "custom_part.md"))
    s = Session(agent, task, log)
    with Broker(task, log) as broker:
        task.start_phase(phase, sims, hours)
        stop = s.request(broker, prompt_fresh(task, phase, sims, hours), phase)
        task.end_phase(stop)
    a_ = task.phases[phase].get("accepted")
    return {"stop": stop if stop.startswith("quota") else ("passed" if a_ else "not passed"), "phase_usage": s.phase_usage}


def run_all_in_one(agent, task, log) -> dict:
    prepare(task)
    shutil.copy(os.path.join(C.DOCS, "custom_part.md"), os.path.join(task.ws, "docs", "custom_part.md"))
    shutil.copy(os.path.join(C.DOCS, "all_in_one", "all_in_one.md"), os.path.join(task.ws, "docs", "all_in_one.md"))
    A = C.ALL_IN_ONE
    text = fill(doc(os.path.join("all_in_one", "prompt.md")), sims=A["sims"], min_sims=A["min_sims"],
                hours=f"{A['hours']:g}", max_mm=f"{A['max_mm']:g}", copies=A["copies"], wall=f"{C.PRINT_MIN_WALL_MM:g}")
    s = Session(agent, task, log)
    stop = "end"
    with Broker(task, log) as broker:
        task.start_phase("all_in_one", A["sims"], A["hours"])
        u0 = dict(agent.usage)
        for k in range(C.MAX_NUDGES + 1):
            left_h = task.hours_left()
            if left_h <= 0:
                stop = "time"
                break
            log({"event": "cli_start", "agent": agent.name, "phase": "all_in_one", "attempt": k})
            rc = agent.turn(task, s.home, broker.dir, text, log, timeout=left_h * 3600)
            log({"event": "cli_exit", "phase": "all_in_one", "returncode": rc})
            if rc == "timeout":
                stop = "time"
                break
            if agent.quota:
                stop = "quota: " + agent.quota
                break
            if task.state == "accepted":
                stop = "submitted"
                break
            if k == C.MAX_NUDGES:
                stop = "no submission"
                break
            text = NUDGE["all_in_one"]
            log({"event": "nudge", "phase": "all_in_one", "text": text})
        if task.final is None and not stop.startswith("quota"):
            task.auto_final()
        task.end_phase(stop)
        s.phase_usage["all_in_one"] = _usage_delta(agent.usage, u0)
    return {"stop": stop, "phase_usage": s.phase_usage}
