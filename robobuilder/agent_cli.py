#!/usr/bin/env python3
"""brick-bench: the benchmark's tools from a shell, inside the agent's sandbox (standard library only; it talks to the
task's broker over a Unix socket).

    brick-bench task                      this level (obstacle geometry, start, goal, limits) as JSON
    brick-bench doc <name>                rules | benches | parts | design_format | manufacturing_constraints | motor_program | simulator | example_design
                                         (also in /work/docs)
    brick-bench validate <design.json>    static check against this level's rules and the design review (free)
    brick-bench simulate <design.json>    physics simulation on this level (limited; a few minutes); it also writes
                                         two contact sheet images of the run (follow and overview cameras)
                                         (All-in-one task: --bench <name> names the course)
    brick-bench submit <design.json> [--notes "..."]
                                         hand in a design that passed a simulation; it is checked with the nudged
                                         runs (free; rules.md) and the design review
    brick-bench submit --best-attempt <design.json> [--notes "..."]
                                         nothing passed: hand in the simulated design that got furthest (its
                                         progress is recorded; not a pass)
    brick-bench part <script.py>          (when a printed part is allowed: custom_part.md) build and check your
                                         custom printed part, export its STL and get its part id
    brick-bench budget                    the current request, simulations and time left
"""
import argparse
import json
import os
import socket
import sys

SOCK = os.environ.get("BENCH_SOCK", "/run/brick-bench/s.sock")


def call(tool, args):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(SOCK)
    s.sendall((json.dumps({"tool": tool, "args": args}) + "\n").encode())
    buf = b""
    while not buf.endswith(b"\n"):
        chunk = s.recv(1 << 16)
        if not chunk:
            break
        buf += chunk
    return json.loads(buf.decode())


def main(argv):
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    cmd, rest = argv[0], argv[1:]
    if cmd == "task":
        out = call("read_doc", {"name": "task"})
    elif cmd == "doc" and rest:
        out = call("read_doc", {"name": rest[0]})
    elif cmd in ("validate", "simulate", "submit") and rest:
        ap = argparse.ArgumentParser(prog=f"brick-bench {cmd}")
        ap.add_argument("path")
        if cmd == "simulate":
            ap.add_argument("--video", action="store_true", help=argparse.SUPPRESS)  # (every run records one)
        if cmd in ("simulate", "validate"):
            ap.add_argument("--bench", default=None, help="All-in-one task: the course to run it on")
        if cmd == "submit":
            ap.add_argument("--notes", nargs="*", default=[])
            ap.add_argument("--best-attempt", dest="best_attempt", action="store_true")
        a = ap.parse_args(rest)
        args = {"path": a.path}
        if getattr(a, "bench", None):
            args["bench"] = a.bench
        if cmd == "submit":
            args["notes"] = " ".join(a.notes)
            if a.best_attempt:
                args["best_attempt"] = True
        out = call(cmd, args)
    elif cmd == "budget":
        out = call("budget", {})
    elif cmd == "part" and rest:
        out = call("part", {"path": rest[0]})
    else:
        print(__doc__)
        return 2
    print(out["text"])
    for p in out.get("images", []):
        cam = "overview camera" if "overview" in os.path.basename(p) else "follow camera"
        print(f"[contact sheet image ({cam}): {p}]")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
