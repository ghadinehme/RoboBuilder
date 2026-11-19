#!/usr/bin/env python3
"""A scripted stand-in for an agent CLI, to test the harness end to end without a model (generic adapter):

    robobuilder run --agent generic --model scripted --run-dir runs/harness_test --levels 1 --benches ramp \
        --tasks cross,light --bind "$PWD/tests" --bind "$PWD/reference_results/designs/opus-5.5/ramp_L1" \
        --command "python3 $PWD/tests/fake_agent.py {prompt_file} $PWD/reference_results/designs/opus-5.5/ramp_L1/cross.json" \
        --resume "python3 $PWD/tests/fake_agent.py {prompt_file} $PWD/reference_results/designs/opus-5.5/ramp_L1/cross.json {session}" \
        --session-regex 'session=(\\w+)'

It reads the request; on a task prompt it copies the given design into /work, validates, simulates and submits it
through `brick-bench`; on the closing turn it writes /work/lessons.md; on a reminder it stops."""
import json
import shutil
import subprocess
import sys


def bb(*args):
    out = subprocess.run(["brick-bench", *args], capture_output=True, text=True).stdout
    print(json.dumps({"tool": args[0], "out": out[:300]}), flush=True)
    return out


def main():
    prompt = open(sys.argv[1]).read()
    design = sys.argv[2]
    print(json.dumps({"type": "start", "info": "session=fake01"}), flush=True)
    if "Write **`/work/lessons.md`**" in prompt:
        open("/work/lessons.md", "w").write("# Lessons\n\n- scripted test agent: the reference design passed.\n")
        return 0
    if prompt.startswith(("You still have budget", "You stopped")):
        bb("budget")
        return 0
    shutil.copy(design, "/work/design.json")
    bb("task")
    bb("validate", "design.json")
    bb("simulate", "design.json")
    bb("submit", "design.json", "--notes", "scripted")
    bb("budget")
    return 0


if __name__ == "__main__":
    sys.exit(main())
