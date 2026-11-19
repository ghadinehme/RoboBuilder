"""A coding-agent CLI as a benchmark entrant: run headless on one task inside a bubblewrap sandbox, resumed in the
same session for follow-up requests (Cross+Print, the closing lessons turn).

An adapter says how to start the CLI (``command``), how to resume its session, how to read its JSON event stream
(session id, token usage) and which login files and install directories it needs inside the sandbox. Every adapter
gets the same prompt, documents, tools and budgets."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time

from .. import sandbox as SB

HOME = os.path.expanduser("~")
QUOTA_WORDS = ("usage limit", "rate limit", "rate_limit", "quota", "resource_exhausted", "resource exhausted",
               "too many requests", "429", "limit reached", "hit your limit")


def which(name: str) -> str:
    p = shutil.which(name) or shutil.which(name, path=os.path.join(HOME, ".local/bin"))
    if not p:
        raise SystemExit(f"{name} is not installed or not on PATH")
    return os.path.realpath(p)


def node_root(exe: str) -> str:
    """the Node install a global npm package lives in (.../node/vX/lib/node_modules/... -> .../node/vX)"""
    return exe.split("/lib/node_modules/")[0] if "/lib/node_modules/" in exe else os.path.dirname(os.path.dirname(exe))


class CLIAgent:
    name = "cli"
    login_files: tuple = ()  # files under ~ the CLI needs to be logged in (mapped read-write: token refresh)
    cache_in_input = False  # the CLI's input_tokens include its cached input (Codex), else they exclude it

    def __init__(self, model: str, effort: str | None = None, **kw):
        self.model, self.effort, self.kw = model, effort, kw
        self.usage = {"input_tokens": 0, "output_tokens": 0, "cache_read_tokens": 0, "cache_write_tokens": 0,
                      "thinking_tokens": 0, "requests": 0, "cost_usd": 0.0}
        self.session = None
        self.quota = None  # the CLI's usage-limit message, if it hit one (the task is then unfinished, not failed)

    @property
    def label(self) -> str:
        return f"{self.name}__{self.model}"

    # ------------------------------------------------------------------ per CLI
    def command(self, prompt: str, resume: bool) -> list[str]:
        raise NotImplementedError

    def parse(self, ev: dict) -> None:
        """account one JSON event of the CLI's stream (usage, session id)"""

    def runtime_binds(self) -> list[str]:
        """extra read-only paths the CLI needs (its install)"""
        return []

    def path_dirs(self) -> list[str]:
        return []

    def extra_env(self) -> dict:
        return {}

    def setup_home(self, home: str) -> None:
        """per-CLI settings written into the fresh agent home"""

    def login_source(self, f: str) -> str:
        return os.path.join(HOME, f)

    # ------------------------------------------------------------------ sandbox
    def sandbox(self, task, home: str, sock_dir: str) -> list[str]:
        if not SB.have_bwrap():
            raise SystemExit("bubblewrap (bwrap) is required to sandbox the agents (RB_NO_SANDBOX=1 only on a "
                             "throwaway machine)")
        cmd = ["bwrap", "--die-with-parent", "--unshare-pid", "--new-session", "--proc", "/proc", "--dev", "/dev",
               "--tmpfs", "/tmp"] + SB.python_binds()
        for p in self.runtime_binds():
            cmd += ["--ro-bind", p, p]
        cmd += ["--bind", home, SB.AGENT_HOME, "--bind", task.ws, SB.AGENT_WS, "--bind", sock_dir, SB.AGENT_SOCK_DIR,
                "--ro-bind", os.path.join(SB.PKG, "agent_cli.py"), f"{SB.AGENT_BIN}/brick-bench"]
        cmd += task.extra_binds()
        for f in self.login_files:
            src = self.login_source(f)
            if os.path.exists(src):
                dst = os.path.join(home, f)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                open(dst, "a").close()
                cmd += ["--bind", src, os.path.join(SB.AGENT_HOME, f)]
        import sys  # noqa: PLC0415

        path = ":".join([SB.AGENT_BIN, os.path.dirname(sys.executable)] + self.path_dirs() + ["/usr/bin", "/bin"])
        env = {"HOME": SB.AGENT_HOME, "PATH": path, "PYTHONPATH": SB.python_path(), "LANG": "C.UTF-8",
               "TERM": "dumb", "MPLBACKEND": "Agg", "BENCH_SOCK": f"{SB.AGENT_SOCK_DIR}/s.sock",
               "VIRTUAL_ENV": sys.prefix, **self.extra_env()}
        cmd += ["--chdir", SB.AGENT_WS, "--clearenv"] + sum((["--setenv", k, v] for k, v in env.items()), [])
        return cmd

    # ------------------------------------------------------------------ run one turn
    def check_quota(self, ev: dict) -> None:
        typ = str(ev.get("type") or ev.get("event") or "")
        err = ev.get("error") if isinstance(ev.get("error"), (dict, str)) else None
        txt = ""
        if typ in ("error", "turn.failed") or err:
            txt = json.dumps(ev)
        elif typ == "result" and ev.get("is_error"):
            txt = str(ev.get("result", "")) + str(ev.get("api_error_status", ""))
        if txt and any(w in txt.lower() for w in QUOTA_WORDS):
            self.quota = txt[:500]

    def stream(self, cmd: list[str], log, timeout: float):
        """run one CLI invocation, logging its JSON events -> return code or "timeout" """
        t_end = time.time() + timeout
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        try:
            for line in p.stdout:
                line = line.rstrip("\n")
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    log({"event": "cli_text", "text": line[:4000]})
                    self.parse_text(line)
                    continue
                if not isinstance(ev, dict):
                    continue
                log({"event": "cli", "data": ev})
                self.parse(ev)
                self.check_quota(ev)
                if time.time() > t_end:
                    p.kill()
                    return "timeout"
            return p.wait(timeout=60)
        except subprocess.TimeoutExpired:
            p.kill()
            return "timeout"

    def parse_text(self, line: str) -> None:
        """a non-JSON output line (generic adapters may read a session id from it)"""

    def turn(self, task, home: str, sock_dir: str, prompt: str, log, timeout: float):
        cmd = self.sandbox(task, home, sock_dir) + self.command(prompt, resume=self.session is not None)
        return self.stream(cmd, log, timeout)


def tokens(u: dict, cache_in_input: bool) -> dict:
    """tokens without cache reads: input = new input tokens (cache writes included, re-reads of cached context left
    out), output = output tokens including reasoning. Some CLIs (Codex) report input_tokens with their cached part
    included and output_tokens with reasoning included."""
    if cache_in_input:
        return {"input_tokens": u.get("input_tokens", 0) - u.get("cache_read_tokens", 0),
                "output_tokens": u.get("output_tokens", 0), "cached_input_tokens": u.get("cache_read_tokens", 0)}
    return {"input_tokens": u.get("input_tokens", 0) + u.get("cache_write_tokens", 0),
            "output_tokens": u.get("output_tokens", 0) + u.get("thinking_tokens", 0),
            "cached_input_tokens": u.get("cache_read_tokens", 0)}
