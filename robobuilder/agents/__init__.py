"""Agent adapters: Claude Code, Codex, Gemini CLI and a generic adapter for any CLI given a command template."""
from __future__ import annotations

import json
import os
import re
import shlex

from .base import CLIAgent, node_root, tokens, which

__all__ = ["CLIAgent", "ClaudeCode", "Codex", "GeminiCLI", "Generic", "make_agent", "tokens"]


class ClaudeCode(CLIAgent):
    """Claude Code (`claude -p`), stream-json output, resumed with --resume <session id>"""
    name = "claude-code"
    login_files = (".claude/.credentials.json",)

    def runtime_binds(self):
        return [node_root(which("claude"))]

    def path_dirs(self):
        return [os.path.join(node_root(which("claude")), "bin")]

    def command(self, prompt, resume):
        cmd = [which("claude"), "-p", prompt, "--model", self.model, "--output-format", "stream-json", "--verbose",
               "--permission-mode", "bypassPermissions", "--disallowedTools", "WebFetch", "WebSearch",
               "--strict-mcp-config", "--setting-sources", "project"]
        if self.effort:
            cmd += ["--effort", self.effort]
        if resume and self.session:
            cmd += ["--resume", self.session]
        return cmd

    def parse(self, ev):
        if ev.get("session_id"):
            self.session = ev["session_id"]
        if ev.get("type") == "assistant":
            self.usage["requests"] += 1
        if ev.get("type") == "result":
            u = ev.get("usage") or {}
            self.usage["input_tokens"] += u.get("input_tokens", 0)
            self.usage["output_tokens"] += u.get("output_tokens", 0)
            self.usage["cache_read_tokens"] += u.get("cache_read_input_tokens", 0)
            self.usage["cache_write_tokens"] += u.get("cache_creation_input_tokens", 0)
            # total_cost_usd is the session's running total, carried over when the session is resumed: add only the
            # increase since the last result of the same session
            tot = ev.get("total_cost_usd") or 0.0
            sid = ev.get("session_id") or self.session
            last = self._session_cost.get(sid, 0.0)
            self.usage["cost_usd"] += max(0.0, tot - last) if tot >= last else tot
            self._session_cost[sid] = tot

    @property
    def _session_cost(self) -> dict:
        if not hasattr(self, "_cost_by_session"):
            self._cost_by_session = {}
        return self._cost_by_session


class Codex(CLIAgent):
    """OpenAI Codex CLI (`codex exec --json`), resumed with `exec resume <thread id>`"""
    name = "codex"
    login_files = (".codex/auth.json",)
    cache_in_input = True

    def runtime_binds(self):
        return [node_root(which("codex"))]

    def path_dirs(self):
        return [os.path.join(node_root(which("codex")), "bin")]

    def command(self, prompt, resume):
        cmd = [which("codex"), "exec"]
        if resume and self.session:
            cmd += ["resume", self.session]
        cmd += ["--json", "-m", self.model, "--dangerously-bypass-approvals-and-sandbox", "--skip-git-repo-check",
                "-c", 'web_search="disabled"']
        if self.effort:
            cmd += ["-c", f'model_reasoning_effort="{self.effort}"']
        if not resume:
            cmd += ["-C", "/work"]
        return cmd + [prompt]

    def parse(self, ev):
        if ev.get("type") == "thread.started":
            self.session = ev.get("thread_id")
        if ev.get("type") == "turn.completed":
            u = ev.get("usage") or {}
            self.usage["requests"] += 1
            self.usage["input_tokens"] += u.get("input_tokens", 0)
            self.usage["cache_read_tokens"] += u.get("cached_input_tokens", 0)
            self.usage["output_tokens"] += u.get("output_tokens", 0)
            self.usage["thinking_tokens"] += u.get("reasoning_output_tokens", 0)


class GeminiCLI(CLIAgent):
    """Google Gemini CLI (`gemini -p ... --output-format stream-json`), all tools auto-approved inside the sandbox,
    web tools excluded; resumed with --resume <session id>. Not used for the paper's runs."""
    name = "gemini-cli"
    login_files = (".gemini/oauth_creds.json", ".gemini/google_accounts.json")

    def runtime_binds(self):
        return [node_root(which("gemini"))]

    def path_dirs(self):
        return [os.path.join(node_root(which("gemini")), "bin")]

    def setup_home(self, home):
        d = os.path.join(home, ".gemini")
        os.makedirs(d, exist_ok=True)
        json.dump({"tools": {"exclude": ["google_web_search", "web_fetch"]}, "security": {"folderTrust": {"enabled": False}}},
                  open(os.path.join(d, "settings.json"), "w"), indent=1)

    def extra_env(self):
        key = os.environ.get("GEMINI_API_KEY")
        return {"GEMINI_API_KEY": key} if key else {}

    def command(self, prompt, resume):
        cmd = [which("gemini"), "-p", prompt, "--model", self.model, "--output-format", "stream-json", "--yolo"]
        if resume and self.session:
            cmd += ["--resume", self.session]
        return cmd

    cache_in_input = True  # the stream's input_tokens (prompt tokens) include the cached part

    def parse(self, ev):
        if ev.get("type") == "init" and ev.get("session_id"):
            self.session = ev["session_id"]
        if ev.get("type") == "result" and isinstance(ev.get("stats"), dict):  # one per CLI run: that run's totals
            st = ev["stats"]
            inp, out = st.get("input_tokens", 0) or 0, st.get("output_tokens", 0) or 0
            self.usage["requests"] += 1
            self.usage["input_tokens"] += inp
            # output with reasoning: output_tokens counts the candidates only, the thoughts are in total_tokens
            self.usage["output_tokens"] += max(out, (st.get("total_tokens", 0) or 0) - inp)
            self.usage["cache_read_tokens"] += st.get("cached", 0) or 0


class Generic(CLIAgent):
    """Any CLI coding agent, from command templates (see README, "Adding a model"):

    command   e.g. "mycli --model {model} --cwd {workdir} --prompt-file {prompt_file}"
    resume    optional, e.g. "mycli --model {model} --resume {session} --prompt-file {prompt_file}": used for the
              follow-up requests (Cross+Print, the lessons turn); without it each request starts a new session that
              is told to continue from the files in /work
    session_regex  optional regex with one group: the session id in the CLI's output (JSON lines are searched as text)
    token_parser   optional "module:function": f(event: dict) -> {"input_tokens", "output_tokens",
                   "cache_read_tokens", "cache_write_tokens", "thinking_tokens"} increments (None to skip)
    binds     optional extra read-only paths (its install), path  optional extra PATH entries,
    login     optional login files under ~ (mapped into the sandbox home), env  optional KEY=VALUE pairs

    Placeholders: {model}, {effort}, {workdir} (/work), {prompt_file} (/work/.prompt.md, the request text),
    {prompt} (the text itself, shell-quoted), {session}."""
    name = "generic"

    def __init__(self, model, effort=None, command=None, resume=None, session_regex=None, token_parser=None,
                 binds=(), path=(), login=(), env=(), name="generic", **kw):
        super().__init__(model, effort, **kw)
        if not command:
            raise SystemExit("the generic adapter needs --command (a command template)")
        self.tpl, self.tpl_resume, self.name = command, resume, name
        self.rx = re.compile(session_regex) if session_regex else None
        self.binds, self.paths, self.login_files = list(binds), list(path), tuple(login)
        self.env = dict(e.split("=", 1) for e in env)
        self.tok = None
        if token_parser:
            import importlib  # noqa: PLC0415

            mod, fn = token_parser.split(":")
            self.tok = getattr(importlib.import_module(mod), fn)
        self._task_ws = None

    def runtime_binds(self):
        return self.binds

    def path_dirs(self):
        return self.paths

    def extra_env(self):
        return self.env

    def turn(self, task, home, sock_dir, prompt, log, timeout):
        open(os.path.join(task.ws, ".prompt.md"), "w").write(prompt)
        if self.session is None and not self.tpl_resume and getattr(self, "_turns", 0) > 0:
            prompt = ("This request continues your earlier work on this task: /work holds your files from it.\n\n"
                      + prompt)
            open(os.path.join(task.ws, ".prompt.md"), "w").write(prompt)
        self._turns = getattr(self, "_turns", 0) + 1
        return super().turn(task, home, sock_dir, prompt, log, timeout)

    def command(self, prompt, resume):
        tpl = self.tpl_resume if (resume and self.session and self.tpl_resume) else self.tpl
        s = tpl.format(model=self.model, effort=self.effort or "", workdir="/work", prompt_file="/work/.prompt.md",
                       prompt=shlex.quote(prompt), session=self.session or "")
        argv = shlex.split(s)
        argv[0] = which(argv[0]) if not os.path.isabs(argv[0]) else argv[0]
        return argv

    def parse(self, ev):
        if self.rx and self.session is None:
            m = self.rx.search(json.dumps(ev))
            if m:
                self.session = m.group(1)
        if self.tok:
            d = self.tok(ev) or {}
            for k, v in d.items():
                if k in self.usage:
                    self.usage[k] += v
            if d:
                self.usage["requests"] += 1

    def parse_text(self, line):
        if self.rx and self.session is None:
            m = self.rx.search(line)
            if m:
                self.session = m.group(1)


AGENTS = {"claude-code": ClaudeCode, "codex": Codex, "gemini-cli": GeminiCLI, "generic": Generic}


def make_agent(kind: str, model: str, effort: str | None = None, **kw) -> CLIAgent:
    if kind not in AGENTS:
        raise SystemExit(f"unknown agent '{kind}' (one of: {', '.join(AGENTS)})")
    return AGENTS[kind](model, effort, **kw)
