"""Run a design in the simulator (a subprocess per run), make the contact sheets, and summarise the verdict.

The verdict of a design on a level: the plain run and the two nudged runs (the robot 1 mm off the centreline; every
motor command after the first 50 ms late) must reach the goal and stay there upright and intact for 5 s, and the
design review must have no critical finding (robobuilder.validate)."""
from __future__ import annotations

import contextlib
import json
import os
import subprocess
import sys
import threading
import time
import uuid

from . import courses

NUDGES = [("offset_1mm", {"RB_START_DY": "0.001"}), ("commands_50ms_late", {"RB_SETTLE_DELTA": "0.05"})]
"""the two nudged runs of the acceptance check"""
CAMERAS = ("follow", "overview")
SUMMARY_KEYS = ["crossed", "failure", "max_progress", "max_progress_m", "time_s", "broken_joints", "mean_speed_m_s",
                "expected_speed_m_s", "valid", "motor_program_log", "gear_meshes", "leads", "diverged"]
WALL_S = os.environ.get("CSIM_WALL_S", "900")  # a run's own wall-time limit inside the simulator [s]
TIMEOUT_S = float(os.environ.get("RB_SIM_TIMEOUT_S", "1800"))  # the subprocess is killed after this [s] (no result)

_SEM = threading.BoundedSemaphore(int(os.environ.get("RB_MAX_PARALLEL_SIMS", str(max(1, (os.cpu_count() or 2) // 2)))))
_SLOTS_DIR = os.environ.get("RB_SIM_SLOTS_DIR")  # optional machine-wide slots shared by several harness processes
_NSLOTS = int(os.environ.get("RB_SIM_SLOTS", "0") or 0)


class _Slot:
    """a machine-wide simulator slot (flock on a slot file) when RB_SIM_SLOTS_DIR and RB_SIM_SLOTS are set"""

    def __enter__(self):
        self.f = None
        if not _SLOTS_DIR or _NSLOTS <= 0:
            return self
        import fcntl  # noqa: PLC0415
        import random  # noqa: PLC0415

        os.makedirs(_SLOTS_DIR, exist_ok=True)
        while True:
            for i in random.sample(range(_NSLOTS), _NSLOTS):
                f = open(os.path.join(_SLOTS_DIR, f"slot{i:02d}"), "a")
                try:
                    fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    f.close()
                    continue
                self.f = f
                return self
            time.sleep(3 + random.random() * 3)

    def __exit__(self, *a):
        if self.f is not None:
            import fcntl  # noqa: PLC0415

            fcntl.flock(self.f, fcntl.LOCK_UN)
            self.f.close()
        return False


def contact_sheet(video: str, out: str) -> str | None:
    """12 frames of a video tiled 4 x 3 (ffmpeg)"""
    if not os.path.exists(video):
        return None
    import re  # noqa: PLC0415

    from .sim.csim import ffmpeg_exe  # noqa: PLC0415

    info = subprocess.run([ffmpeg_exe(), "-i", video], capture_output=True, text=True).stderr
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", info)
    dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 10.0
    subprocess.run([ffmpeg_exe(), "-y", "-loglevel", "error", "-i", video, "-vf",
                    f"fps={12 / max(float(dur), 0.1):.5f},scale=400:-1,tile=4x3", "-frames:v", "1", out])
    return out if os.path.exists(out) else None


def run(design_path: str, bench: str, level: int, env: dict | None = None, video: bool = True,
        printed_specs: list[str] | tuple = (), out_dir: str | None = None, tag: str = "sim",
        params: str | None = None) -> dict:
    """simulate one design on one level -> the simulator's result JSON plus ``_dir``, ``_wall_s``, ``_queue_s`` and
    ``_contact_sheets``. ``printed_specs``: spec.json files of the printed parts the design uses. ``out_dir``: default
    <design dir>/_sims/<tag>_<id>."""
    courses.check(bench, level)
    design_path = os.path.abspath(design_path)
    d = out_dir or os.path.join(os.path.dirname(design_path), "_sims", f"{tag}_{uuid.uuid4().hex[:8]}")
    os.makedirs(d, exist_ok=True)
    mod = "robobuilder.printed.sim" if printed_specs else "robobuilder.sim.run"
    cmd = [sys.executable, "-m", mod, "--design", design_path, "--obstacle", bench,
           "--level", str(level), "--out", os.path.join(d, "result.json")]
    if params:
        cmd += ["--params", os.path.abspath(params)]
    if video:
        cmd += ["--video", "--video_dir", os.path.join(d, "video")]
    from . import BENCHMARK_ENV  # noqa: PLC0415

    e = dict(os.environ)
    e.update(BENCHMARK_ENV)
    e.update(env or {})
    e.setdefault("CSIM_WALL_S", WALL_S)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    e["PYTHONPATH"] = root + (os.pathsep + e["PYTHONPATH"] if e.get("PYTHONPATH") else "")
    if printed_specs:
        from .printed import ENV_VAR, geom_dirs  # noqa: PLC0415

        e[ENV_VAR] = os.pathsep.join(os.path.abspath(p) for p in printed_specs)
        e["RB_GEOM_DIRS"] = os.pathsep.join(geom_dirs(printed_specs))
    tq = time.time()
    with _SEM, _Slot():
        t0 = time.time()
        with open(os.path.join(d, "sim.log"), "w") as f:
            with contextlib.suppress(subprocess.TimeoutExpired):
                subprocess.run(cmd, env=e, stdout=f, stderr=subprocess.STDOUT, timeout=TIMEOUT_S)
        if video:
            for cam in CAMERAS:
                contact_sheet(os.path.join(d, "video", f"{cam}.mp4"), os.path.join(d, f"contact_{cam}.jpg"))
        wall = time.time() - t0
    rp = os.path.join(d, "result.json")
    if not os.path.exists(rp):
        tail = open(os.path.join(d, "sim.log")).read()[-3000:] if os.path.exists(os.path.join(d, "sim.log")) else ""
        return {"error": "the simulator produced no result", "log_tail": tail, "_dir": d, "_wall_s": round(wall, 1),
                "_queue_s": round(t0 - tq, 1)}
    r = json.load(open(rp))
    r.update(_dir=d, _wall_s=round(wall, 1), _queue_s=round(t0 - tq, 1))
    r["_contact_sheets"] = [p for p in (os.path.join(d, f"contact_{c}.jpg") for c in CAMERAS) if video and os.path.exists(p)]
    return r


def run_retry(*a, **kw) -> dict:
    """run(); a simulator crash or hang (no result) is retried once"""
    r = run(*a, **kw)
    if "error" in r and "no result" in str(r.get("error")):
        r = run(*a, **kw)
    return r


def summary(r: dict) -> dict:
    """what an agent sees of a result: the judge's verdict and the numbers that explain it"""
    if "error" in r:
        return {"error": r["error"], "log_tail": r.get("log_tail", "")[-1500:]}
    out = {k: r[k] for k in SUMMARY_KEYS if k in r}
    if isinstance(out.get("motor_program_log"), list):
        out["motor_program_log"] = out["motor_program_log"][:40]
    out["passed"] = bool(r.get("crossed"))
    return out


def nudged(design_path: str, bench: str, level: int, printed_specs=(), video: bool = True, out_root=None,
           params: str | None = None, extra_env: dict | None = None) -> list[dict]:
    """the two nudged runs (in parallel) -> [{"nudge", "passed", "failure", "max_progress", "time_s", "error"}]"""
    from concurrent.futures import ThreadPoolExecutor  # noqa: PLC0415

    def one(nv):
        name, env = nv
        od = os.path.join(out_root, name) if out_root else None
        s = summary(run_retry(design_path, bench, level, env={**(extra_env or {}), **env}, video=video,
                              printed_specs=printed_specs,
                              out_dir=od, tag=f"{bench}_L{level}_{name}", params=params))
        return {"nudge": name, **{k: s.get(k) for k in ("passed", "failure", "max_progress", "time_s", "error")}}
    with ThreadPoolExecutor(len(NUDGES)) as ex:
        return list(ex.map(one, NUDGES))


def verdict(design_path: str, bench: str, level: int, printed_specs=(), video: bool = False, out_root=None,
            params: str | None = None, rules: dict | None = None) -> dict:
    """the official verdict of a design on a level: validation + review, the plain run and the two nudged runs (all
    three run in parallel) -> {"passed", "validate", "plain", "nudges", "reason"}. ``rules``: courses.rules arguments
    (default: the benchmark's rules; reference designs record the rules they were accepted under)"""
    from concurrent.futures import ThreadPoolExecutor  # noqa: PLC0415

    from .printed import register  # noqa: PLC0415
    from .validate import validate  # noqa: PLC0415

    for sp in printed_specs:
        register(sp)
    rules = dict(rules or {})
    with courses.rules(**rules):
        v = validate(design_path, bench, level)
    benv = courses.rules_env(**{k: v_ for k, v_ in rules.items() if k in ("start_boards", "max_chains")})
    out = {"passed": False, "validate": {k: v.get(k) for k in ("ok", "errors", "stats")},
           "review_critical": (v.get("review") or {}).get("critical") or []}
    if not v["ok"]:
        out["reason"] = "does not validate"
        return out
    with ThreadPoolExecutor(2) as ex:
        fp = ex.submit(lambda: summary(run_retry(design_path, bench, level, env=benv, video=video,
                                                 printed_specs=printed_specs,
                                                 out_dir=os.path.join(out_root, "plain") if out_root else None,
                                                 tag=f"{bench}_L{level}_plain", params=params)))
        fn = ex.submit(nudged, design_path, bench, level, printed_specs, video, out_root, params, benv)
        plain, nud = fp.result(), fn.result()
    out["plain"] = {k: plain.get(k) for k in ("passed", "failure", "max_progress", "time_s", "error")}
    out["nudges"] = nud
    ok = bool(plain.get("passed")) and all(x.get("passed") for x in nud)
    out["passed"] = ok and not out["review_critical"]
    if not out["passed"]:
        bad = ("plain run" if not plain.get("passed") else
               next((x["nudge"] for x in nud if not x.get("passed")), None))
        out["reason"] = (f"fails the {bad} ({(plain if bad == 'plain run' else next(x for x in nud if x['nudge'] == bad)).get('failure')})"
                         if bad else "design review: critical finding")
    return out
