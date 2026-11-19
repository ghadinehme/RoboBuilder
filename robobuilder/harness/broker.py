"""Tool broker: serves one task's tools on a Unix socket outside the agent's sandbox. Inside the sandbox the
`brick-bench` command (robobuilder/agent_cli.py) is the only way to validate, simulate, submit and build a printed
part; the broker holds the budget, the simulator access and the log.

Protocol: one JSON line per connection, {"tool": name, "args": {...}} -> {"text": str, "images": [paths]}. Paths are
relative to the workspace (the agent sees it as /work)."""
from __future__ import annotations

import json
import os
import shutil
import socketserver
import tempfile
import threading

from ..sandbox import AGENT_WS


class Broker:
    def __init__(self, task, log):
        self.task, self.log = task, log
        self.dir = tempfile.mkdtemp(prefix="rb-")  # a Unix socket path must be short (<= 107 bytes)
        self.path = os.path.join(self.dir, "s.sock")
        broker = self

        class H(socketserver.StreamRequestHandler):
            def handle(self):
                try:
                    req = json.loads(self.rfile.readline().decode() or "{}")
                    out = broker.handle(req.get("tool", ""), req.get("args") or {})
                except Exception as e:  # noqa: BLE001
                    out = {"text": json.dumps({"error": f"{type(e).__name__}: {e}"}), "images": []}
                self.wfile.write((json.dumps(out) + "\n").encode())

        self.server = socketserver.ThreadingUnixStreamServer(self.path, H)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def handle(self, tool: str, args: dict) -> dict:
        t = self.task
        self.log({"event": "tool_call", "name": tool, "args": args})
        text, imgs = t.call(tool, args)
        out_imgs = []
        for p in imgs:  # contact sheets are in the workspace (_sims/<run>/contact_*.jpg)
            rp = os.path.realpath(p)
            if not rp.startswith(os.path.realpath(t.ws) + os.sep):
                dst = os.path.join(t.ws, "_sims", os.path.basename(p))
                shutil.copy(p, dst)
                rp = dst
            out_imgs.append(os.path.join(AGENT_WS, os.path.relpath(rp, t.ws)))
        self.log({"event": "tool_result", "name": tool, "text": text[:20000], "images": out_imgs})
        return {"text": text, "images": out_imgs}

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *a):
        self.server.shutdown()
        self.server.server_close()
        shutil.rmtree(self.dir, ignore_errors=True)
