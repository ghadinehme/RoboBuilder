"""bubblewrap sandboxes: what an agent (and the printed-part build) can see.

The agent sees the system directories, its own CLI, Python with the design library (robobuilder/core and
robobuilder/agent_lib: `import bricks`), its task workspace (/work, writable) and the `brick-bench` command. It does not
see the simulator source, the harness, the reference results or the rest of the repository. Its home is a fresh
per-task directory; only its CLI's login files are mapped in. The network stays on (the CLI must reach its model API);
the CLIs' web tools are switched off and the rules forbid web access."""
from __future__ import annotations

import os
import shutil
import sys

PKG = os.path.dirname(os.path.abspath(__file__))  # robobuilder/
AGENT_LIB = os.path.join(PKG, "agent_lib")
AGENT_WS = "/work"  # the workspace's path inside the sandbox
AGENT_HOME = "/home/agent"
AGENT_SOCK_DIR = "/run/brick-bench"  # the broker socket's directory inside the sandbox
AGENT_BIN = "/bricks/bin"


def have_bwrap() -> bool:
    return bool(shutil.which("bwrap")) and os.environ.get("RB_NO_SANDBOX") != "1"


def system_binds() -> list[str]:
    out = []
    for p in ("/usr", "/etc", "/bin", "/lib", "/lib64", "/sbin"):
        if os.path.exists(p):
            out += ["--ro-bind", p, p]
    resolv = os.path.dirname(os.path.realpath("/etc/resolv.conf"))  # e.g. /run/systemd/resolve (DNS)
    if os.path.isdir(resolv) and not resolv.startswith(("/etc", "/usr")):
        out += ["--ro-bind", resolv, resolv]
    return out


def python_binds() -> list[str]:
    """the Python environment (venv and its base install) and the parts of the robobuilder package an agent may see"""
    out = system_binds()
    seen = set()
    for p in {sys.prefix, sys.base_prefix, os.path.dirname(os.path.dirname(os.path.realpath(sys.executable)))}:
        if p and os.path.isdir(p) and p not in seen and not p.startswith(("/usr", "/bin", "/lib")):
            seen.add(p)
            out += ["--ro-bind", p, p]
    for sub in ("__init__.py", "core", "agent_lib"):
        p = os.path.join(PKG, sub)
        out += ["--ro-bind", p, p]
    return out


def python_path() -> str:
    """PYTHONPATH inside a sandbox: the agents' `bricks` package and the robobuilder package"""
    return os.pathsep.join([AGENT_LIB, os.path.dirname(PKG)])
