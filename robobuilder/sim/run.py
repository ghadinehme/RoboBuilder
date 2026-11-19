"""Run one design on one course in the simulator and write the verdict JSON.

    python -m robobuilder.sim.run --design d.json --obstacle ramp --level 1 --out result.json [--video --video_dir DIR]
                                  [--params params.json] [--start_dy 0.001] [--delay 0.05]

``--level`` is the benchmark level (1, 2 or 3).
The physical parameters default to $CSIM_PARAMS, else the learned simulator (params/learned.json). The result has the
judge's verdict (crossed, failure, time_s, max_progress, ...) and what the simulator observed (studs pulled out, gear
meshes that skipped or separated, leads unplugged, mechanisms)."""
import argparse
import json
import os
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
LEARNED = os.path.join(HERE, "params", "learned.json")


def load_params(path=None):
    """-> (parameter dict, source file); ``path`` or $CSIM_PARAMS or the learned simulator"""
    p = path or os.environ.get("CSIM_PARAMS") or LEARNED
    d = json.load(open(p))
    return dict(d.get("params", d)), p


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--design", required=True)
    ap.add_argument("--obstacle", required=True)
    ap.add_argument("--level", type=int, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--params")
    ap.add_argument("--video", action="store_true")
    ap.add_argument("--video_dir")
    ap.add_argument("--start_dy", type=float, default=float(os.environ.get("RB_START_DY", 0) or 0))
    ap.add_argument("--delay", type=float, default=float(os.environ.get("RB_SETTLE_DELTA", 0) or 0))
    a, _ = ap.parse_known_args(argv)
    from robobuilder.core import obstacles as OB
    from robobuilder.sim.csim import CrossSim, Params

    prm, src = load_params(a.params)
    sup = float(os.environ.get("RB_SUPPLY_SCALE", 0) or 0)
    if sup and sup != 1.0:  # a weaker / stronger battery: motor torque and no-load speed scale
        for k_ in ("m_stall_nm", "l_stall_nm", "m_no_load_rad_s", "servo_torque_nm", "servo_w0_rad_s"):
            prm[k_] = float(prm.get(k_, getattr(Params(), k_))) * sup
    if a.delay:  # nudged run: every motor command after the first fires this much later
        prm["program_late_s"] = float(prm.get("program_late_s", 0.0)) + a.delay
    t0 = time.time()
    s = CrossSim(a.design, a.obstacle, a.level, prm)
    if a.start_dy:  # nudged run: the robot placed off the centreline (every spawn pose moved sideways)
        s.world = {n: (pos + np.array([0.0, a.start_dy, 0.0]), R) for n, (pos, R) in s.world.items()}
        s._build()
    t_max = s.ob.time_limit_s + OB.FINAL_SETTLE_S + 0.5
    vid = None
    if a.video:
        os.makedirs(a.video_dir, exist_ok=True)
        vid = os.path.join(a.video_dir, "run.mp4")
    r = s.run(t_max, vid, fps=20, cams=("follow", "side"), stop_on_result=True)
    if vid:  # follow.mp4 and overview.mp4
        for src_cam, dst in (("follow", "follow"), ("side", "overview")):
            p = vid.replace(".mp4", f"_{src_cam}.mp4")
            if os.path.exists(p):
                os.replace(p, os.path.join(a.video_dir, f"{dst}.mp4"))
    out = {k: r.get(k) for k in ("obstacle", "level", "crossed", "time_s", "reached_goal_s", "max_progress",
                                  "max_progress_m", "failure")}
    out["crossed"] = bool(r.get("crossed") or r.get("passed"))
    if out.get("failure") is None and not out["crossed"]:
        out["failure"] = r.get("failure") or "time limit"
    out["max_progress"] = r.get("max_progress") if r.get("max_progress") is not None else 0.0
    out["simulator"] = "robobuilder-mujoco"
    out["params_file"] = os.path.basename(src)
    out["diverged"] = r.get("diverged")
    out["broken_joints"] = [e for _, e in r.get("events", []) if e.startswith("stud released")][:20]
    out["gear_meshes"] = r.get("mesh")
    out["chains"] = r.get("chains")  # per chain: peak tension, sprocket gap range (vs as built), skips
    out["mesh_events_dropped"] = r.get("mesh_events_dropped")
    out["leads"] = r.get("cables")
    out["mechanisms"] = r.get("mechanisms")  # racks, shocks, treads, differentials
    out["stud_peak_load_ratio"] = r.get("stud_peak_n")
    out["motor_program_log"] = [f"{t:.2f} s {e}" for t, e in r.get("events", [])][:60]
    out["valid"] = True
    out["wall_s"] = round(time.time() - t0, 1)
    json.dump(out, open(a.out, "w"), indent=1, default=str)
    print(json.dumps({k: out[k] for k in ("crossed", "failure", "time_s", "max_progress")}))


if __name__ == "__main__":
    main()
