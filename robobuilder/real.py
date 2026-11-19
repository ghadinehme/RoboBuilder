"""Run a design on the real course: its wiring and its open-loop program as IR commands, sent through the USB-serial IR
bridge (real_world/firmware/ir_bridge) to the robot's IR receivers.

    python -m robobuilder.real <design.json> <bench> <level> [--port /dev/ttyACM0] [--dry-run] [--speed-scale 1.0]
                                [--printed spec.json ...]

The program is executed exactly as the simulator executes it: evaluated at the start signal (t = 0) and then every
10 ms; a command fires the first time its trigger holds; a command waits while it is less than 0.1 s after the
previous one; ``"motor": "all"`` sets every motor; ``"brake"`` brakes and level 0 floats. Each motor's level is turned
into the receiver output's sign with the motor's mounting (counter-clockwise, seen looking at the output face, is
positive). Motors that always run together share an output (stacked plugs); a motor that runs at full speed for the
whole run may plug straight into a battery box (switched on at GO). Combo commands are refreshed every 0.3 s (a receiver
drops a combo command after about 1.2 s) and every output floats at the end of the run window.

Serial protocol of the bridge (115200 baud, one line per command): ``?`` ping, ``C <ch 1-4> <A> <B>`` both outputs of a
receiver channel (each -7..7, 0 float, or brake), ``P <ch> <A|B> <level>`` one output (latched), ``N <1-10>`` repeats."""
from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass, field

SIM_DT = 1.0e-3
CHECK_EVERY = 10
MIN_DT = 0.1
STEPS = 7
TOL = 1e-9
KEEPALIVE_S = 0.3
OUT_COLOUR = {"A": "red", "B": "blue"}
MOTOR_NAMES = {"58120c01": "M motor", "99499c01": "L motor", "58121c01": "XL motor", "99498c01": "servo motor",
               "87513c01": "AAA battery box", "59510c01": "AA battery box", "58123c01": "IR receiver"}


class NotOpenLoop(ValueError):
    pass


def open_loop_problems(prog: list[dict]) -> list[str]:
    errs = []
    for i, c in enumerate(prog):
        bad = [k for k in ("x", "sensor", "angle") if k in c]
        if bad:
            errs.append(f"command {i}: '{bad[0]}' trigger")
        if "level" not in c:
            errs.append(f"command {i}: no 'level'")
    return errs


def run_program(prog: list[dict], t_end: float, dt: float = SIM_DT, check_every: int = CHECK_EVERY) -> list[dict]:
    """fired commands [{'i', 't', 'motor', 'level'}] of an open-loop program, as the simulator fires them"""
    errs = open_loop_problems(prog)
    if errs:
        raise NotOpenLoop("; ".join(errs))
    fired: dict[int, float] = {}
    state = {"last_t": -1e9, "pending": list(enumerate(prog))}
    log = []

    def holds(c, t):
        if "t" in c and t < c["t"] - TOL:
            return False
        if "after" in c and (c["after"] not in fired or t - fired[c["after"]] < c.get("delay", 0.0) - TOL):
            return False
        return True

    def update(t):
        for i, c in list(state["pending"]):
            if not holds(c, t) or t - state["last_t"] < MIN_DT - TOL:
                continue
            state["pending"] = [pc for pc in state["pending"] if pc[0] != i]
            fired[i] = state["last_t"] = t
            log.append({"i": i, "t": round(t, 3), "motor": c["motor"], "level": c["level"]})
            return

    update(0.0)
    n = check_every
    while state["pending"] and n * dt <= t_end + TOL:
        update(n * dt)
        n += check_every
    return log


@dataclass
class Analysis:
    design: object
    P: dict
    motors: list
    labels: dict
    driving: set
    direction: int
    rel: dict
    ccw: dict
    program: list
    battery: str | None
    notes: list = field(default_factory=list)


def analyse(path: str) -> Analysis:
    import numpy as np  # noqa: PLC0415

    from .core import design as D  # noqa: PLC0415

    raw = json.load(open(path))
    d = D.Design.load(path)
    P = D.place(d)
    st = D.compute_stats(d, P)
    direction = st.get("motor_direction", 1) or 1
    driving = D.wheel_motors(d)
    _, rel, _ = D.motor_trains(d, P)
    mconns = [c for c in d.connections if c.kind == "motor"]
    motors = [c.parent for c in mconns]
    shaft = {c.parent: c.child for c in mconns}
    ccw = {}
    for m in motors:
        out_dir = -P[m].R[:, 1]  # motor body along local +y from the output face: the shaft leaves along -y
        ccw[m] = 1 if float(np.dot(P[shaft[m]].axis(), out_dir)) >= 0 else -1
    prog = list(raw.get("motor_program") or d.motor_program or [])
    order = [d.motor] if d.motor in motors else []
    for c in prog:
        if c.get("motor") in motors and c["motor"] not in order:
            order.append(c["motor"])
    order += sorted(m for m in motors if m not in order)
    labels = {m: f"M{i + 1}" for i, m in enumerate(order)}
    bat = d.battery if d.battery in P else next((n for n in P if P[n].bp.kind == "battery"), None)
    return Analysis(design=d, P=P, motors=motors, labels=labels, driving=set(driving), direction=int(direction),
                    rel=dict(rel), ccw=ccw, program=prog, battery=bat)


def motor_events(a: Analysis, t_end: float) -> list[dict]:
    """per-motor level changes [{'t', 'i', 'motor', 'label', 'level', 'ccw'}] (ccw: + = counter-clockwise looking at
    the output face)"""
    out = []
    if not a.program:  # no program: every motor at +7 from the start
        for m in a.motors:
            j = STEPS * a.direction * a.rel.get(m, 1)
            out.append(dict(t=0.0, i=None, motor=m, label=a.labels[m], level=STEPS, ccw=j * a.ccw[m]))
        return out
    for ev in run_program(a.program, t_end):
        for m in (a.motors if ev["motor"] == "all" else [ev["motor"]]):
            sign = (a.direction if m in a.driving else 1) * a.rel.get(m, 1)
            brake = ev["level"] == "brake"
            j = 0 if brake else sign * ev["level"]
            out.append(dict(t=ev["t"], i=ev["i"], motor=m, label=a.labels[m], level=ev["level"], ccw=j * a.ccw[m],
                            **({"brake": True} if brake else {})))
    return out


def mapping(a: Analysis) -> dict:
    """{motor: {"channel", "output"} | {"box": True} | {"unused": True}} from the design library's IR wiring rule"""
    from .core.design import ir_mapping  # noqa: PLC0415

    m = ir_mapping(a.design)
    out = {mot: {"channel": o["channel"], "output": o["output"]} for mot, o in m["outputs"].items()}
    out.update({mot: {"box": True} for mot in m.get("box_direct", {})})
    for mot in a.motors:
        out.setdefault(mot, {"unused": True})
    return out


def split_stacked(a: Analysis, events: list[dict], mp: dict) -> tuple[dict, list[str]]:
    """motors stacked on one output must turn the same way at the same speed the whole run; another one moves to a
    free output (stacked plugs cannot be put on reversed)"""
    series = {}
    for ev in events:
        series.setdefault(ev["motor"], []).append((round(ev["t"], 3), "brake" if ev.get("brake") else ev["ccw"]))
    order = sorted(a.motors, key=lambda m: int(a.labels[m][1:]))
    out = {m: dict(v) for m, v in mp.items()}
    used = {(v["channel"], v["output"]) for v in out.values() if "channel" in v}
    notes = []
    for key in sorted(used):
        on = [m for m in order if out.get(m, {}).get("channel") == key[0] and out[m]["output"] == key[1]]
        ref = on[0]
        for m in on[1:]:
            sm, sr = series.get(m, []), series.get(ref, [])
            if len(sm) == len(sr) and all(lm == lr and abs(tm - tr) <= 0.1 + TOL for (tm, lm), (tr, lr) in zip(sm, sr)):
                continue
            free = [(key[0], o) for o in "AB" if (key[0], o) not in used] + \
                   [(c, o) for c in range(1, 5) for o in "AB" if c != key[0] and (c, o) not in used]
            if not free:
                notes.append(f"{a.labels[m]} must turn unlike {a.labels[ref]} but no receiver output is free")
                continue
            c, o = free[0]
            used.add((c, o))
            out[m] = {"channel": c, "output": o}
            notes.append(f"{a.labels[m]} moved from {key[0]}{key[1]} to {c}{o} (stacked plugs cannot be reversed)")
    return out, notes


def ir_value(ccw_level, out_key: str, flip: dict) -> str:
    if ccw_level is None or ccw_level == 0:
        return "0"
    return str(int(ccw_level * (-1 if flip.get(out_key) else 1)))


def turn_words(ccw_level: int) -> str:
    if ccw_level == 0:
        return "stop"
    return ("counter-clockwise" if ccw_level > 0 else "clockwise") + f" at {abs(ccw_level)}/7 (looking at the output face)"


def schedule(design_path: str, bench: str, level: int, flip: dict | None = None) -> dict:
    """the IR schedule of a design on a level: wiring, battery-box motors, timed combo commands, run window"""
    from . import courses  # noqa: PLC0415

    flip = flip or {}
    t_limit = courses.obstacle(bench, level).time_limit_s
    a = analyse(design_path)
    events = motor_events(a, t_limit)
    mp, notes = split_stacked(a, events, mapping(a))
    motors = []
    seen = {}
    for m in sorted(a.motors, key=lambda m: int(a.labels[m][1:])):
        md = dict(motor=m, label=a.labels[m], part=MOTOR_NAMES.get(a.P[m].inst.part, a.P[m].inst.part),
                  role="wheels" if m in a.driving else "mechanism", **mp.get(m, {"unused": True}))
        if md.get("channel"):
            k = (md["channel"], md["output"])
            if k in seen:
                md["stacked_on"] = seen[k]
            else:
                seen[k] = md["label"]
        motors.append(md)
    ir, box, state = [], [], {}
    for ev in events:
        m = mp.get(ev["motor"], {})
        if m.get("box"):
            box.append(dict(t=ev["t"], label=ev["label"], note=f"switch the battery box feeding {ev['label']} ON at GO, "
                                                                 f"so the motor turns {turn_words(ev['ccw'])}"))
            continue
        if "channel" not in m:
            continue
        ch, o = m["channel"], m["output"]
        used = {mm["output"] for mm in mp.values() if mm.get("channel") == ch}
        st = state.setdefault(ch, {oo: (0 if oo in used else None) for oo in "AB"})
        st[o] = "brake" if ev.get("brake") else ev["ccw"]
        tok = {oo: ("brake" if st[oo] == "brake" else ir_value(st[oo], f"{ch}{oo}", flip)) for oo in "AB"}
        cmd = dict(t=ev["t"], ch=ch, A=tok["A"], B=tok["B"], why=[f"{ev['label']} level {ev['level']} -> {ch}{o}"])
        if ir and abs(ir[-1]["t"] - cmd["t"]) < TOL and ir[-1]["ch"] == ch:  # one instant: one combo message
            ir[-1].update(A=cmd["A"], B=cmd["B"])
            ir[-1]["why"] += cmd["why"]
        else:
            ir.append(cmd)
    last = max([c["t"] for c in ir] + [b["t"] for b in box] + [0.0])
    bat = a.P[a.battery].inst.part if a.battery else None
    return {"bench": bench, "level": level, "design": a.design.name, "time_limit_s": t_limit,
            "battery": MOTOR_NAMES.get(bat, bat) if bat else None,
            "start_gap_mm": getattr(a.design, "start_gap_mm", None), "motors": motors, "notes": notes, "ir": ir,
            "box_direct": box, "receivers": len({m["channel"] for m in motors if m.get("channel")}),
            "run_s": round(max(last + 1.0, t_limit), 2)}


def play(sched: dict, port: str, speed_scale: float = 1.0, countdown: int = 3) -> None:
    """send the schedule through the IR bridge; every command time is divided by ``speed_scale`` (real / simulated
    motor speed, e.g. 0.9 with weak batteries)"""
    import serial  # noqa: PLC0415  (pip install pyserial)

    s = serial.Serial(port, 115200, timeout=1)
    time.sleep(2.0)  # the board resets when the port opens
    s.write(b"?\n")
    print("bridge:", s.readline().decode(errors="replace").strip())
    for k in range(countdown, 0, -1):
        print(k, flush=True)
        time.sleep(1.0)
    print("GO", flush=True)
    for b in sched["box_direct"]:
        print("  ", b["note"])
    t0, cur, i = time.time(), {}, 0
    cmds = sorted(sched["ir"], key=lambda c: c["t"])
    end = sched["run_s"] / speed_scale
    next_refresh = 0.0
    try:
        while True:
            t = time.time() - t0
            if t > end:
                break
            while i < len(cmds) and cmds[i]["t"] / speed_scale <= t:
                c = cmds[i]
                cur[c["ch"]] = (c["A"], c["B"])
                s.write(f"C {c['ch']} {c['A']} {c['B']}\n".encode())
                print(f"{t:6.2f} s  C {c['ch']} {c['A']} {c['B']}   {'; '.join(c['why'])}", flush=True)
                i += 1
            if t >= next_refresh:  # keep combo commands alive
                for ch, (va, vb) in cur.items():
                    s.write(f"C {ch} {va} {vb}\n".encode())
                next_refresh = t + KEEPALIVE_S
            time.sleep(0.005)
    finally:
        for ch in range(1, 5):
            s.write(f"C {ch} 0 0\n".encode())
        s.close()
        print("stopped: every output floats")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("design")
    ap.add_argument("bench")
    ap.add_argument("level", type=int)
    ap.add_argument("--port", help="the IR bridge's serial port (e.g. /dev/ttyACM0)")
    ap.add_argument("--dry-run", action="store_true", help="print the wiring and the schedule only")
    ap.add_argument("--speed-scale", type=float, default=1.0)
    ap.add_argument("--flip", nargs="*", default=[], help="receiver outputs whose motor turns the wrong way, e.g. 1A")
    ap.add_argument("--printed", nargs="*", default=[], help="spec.json of each printed part the design uses")
    a = ap.parse_args(argv)
    from .printed import register  # noqa: PLC0415

    for sp in a.printed:
        register(sp)
    from collections import Counter  # noqa: PLC0415

    from .core.design import Design, bom_item_counts  # noqa: PLC0415
    from .core.parts import bench_parts, owned_inventory  # noqa: PLC0415

    d = Design.load(a.design)
    names = {pid: bp.title for pid, bp in bench_parts().items()}
    print("parts to build it (part id, count, name):")
    for pid, n in sorted(bom_item_counts(d).items()):
        print(f"  {pid:10s} x{n:<3d} {names.get(pid, pid)}" + ("" if pid.startswith("p3d_") or owned_inventory().get(pid, 0) >= n
                                                             else "  (more than the inventory owns)"))
    print(f"  {sum(Counter(p.part for p in d.parts).values())} placed parts (chain and tread links counted above)")
    s = schedule(a.design, a.bench, a.level, flip={k: True for k in a.flip})
    print(f"{s['design']} on {a.bench} L{a.level}: start gap {s['start_gap_mm']} mm, run window {s['run_s']} s, "
          f"{s['receivers']} IR receiver(s)")
    for m in s["motors"]:
        where = (f"receiver channel {m['channel']} output {m['output']} ({OUT_COLOUR[m['output']]})"
                 + (f", stacked on {m['stacked_on']}" if m.get("stacked_on") else "") if m.get("channel")
                 else "straight into a battery box" if m.get("box") else "not used")
        print(f"  {m['label']} {m['part']} ({m['role']}, part '{m['motor']}'): {where}")
    for n in s["notes"]:
        print("  note:", n)
    for c in s["ir"]:
        print(f"  {c['t']:6.2f} s  C {c['ch']} {c['A']} {c['B']}")
    if a.dry_run or not a.port:
        return 0
    play(s, a.port, a.speed_scale)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
