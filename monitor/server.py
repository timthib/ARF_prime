"""HTTP server for the control room. It serves the public read model and the command gateway."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from monitor.gateway import execute, list_commands
from monitor.queries import find_run, load_runs, pilot_report_payload, shape_framework, shape_run, shape_step, shape_study

WEB_DIST = Path(__file__).resolve().parent / "web" / "dist"
MAX_BODY = 65_536

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".svg": "image/svg+xml",
    ".json": "application/json; charset=utf-8",
    ".woff2": "font/woff2",
}


class ControlHandler(BaseHTTPRequestHandler):
    root: Path
    repo: Path

    def log_message(self, fmt: str, *args) -> None:
        return

    def do_GET(self) -> None:
        path = unquote(urlparse(self.path).path)
        if path.startswith("/api/"):
            self._api_get(path)
            return
        self._static(path)

    def do_POST(self) -> None:
        path = unquote(urlparse(self.path).path)
        if path != "/api/commands":
            self._json(404, {"error": "not found"})
            return
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length > MAX_BODY:
            self._json(400, {"error": "body too large"})
            return
        raw = self.rfile.read(length) if length else b""
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._json(400, {"error": "body must be JSON"})
            return
        if not isinstance(payload, dict):
            self._json(400, {"error": "body must be a JSON object"})
            return
        verb = payload.get("verb")
        fields = {key: value for key, value in payload.items() if key != "verb"}
        result = execute(self.root, verb if isinstance(verb, str) else "", fields)
        self._json(200, result)

    def _api_get(self, path: str) -> None:
        if path == "/api/study":
            self._json(200, shape_study(load_runs(self.root), self.repo))
            return
        if path == "/api/commands":
            self._json(200, {"commands": list_commands()})
            return
        if path == "/api/pilot-report":
            self._json(200, pilot_report_payload(self.root, self.repo))
            return
        parts = [part for part in path.split("/") if part]
        # /api/runs/{id}[/steps/{k}|/frameworks/{fid}]
        if len(parts) >= 3 and parts[0] == "api" and parts[1] == "runs":
            data = find_run(self.root, parts[2])
            if data is None:
                self._json(404, {"error": "run not found"})
                return
            if len(parts) == 3:
                self._json(200, shape_run(data))
                return
            if len(parts) == 5 and parts[3] == "steps":
                try:
                    k = int(parts[4])
                except ValueError:
                    self._json(404, {"error": "step not found"})
                    return
                detail = shape_step(data, k)
                if detail is None:
                    self._json(404, {"error": "step not found"})
                    return
                self._json(200, detail)
                return
            if len(parts) == 5 and parts[3] == "frameworks":
                detail = shape_framework(data, parts[4])
                if detail is None:
                    self._json(404, {"error": "framework not found"})
                    return
                self._json(200, detail)
                return
        self._json(404, {"error": "not found"})

    def _static(self, path: str) -> None:
        if not WEB_DIST.exists():
            message = (
                "Control room UI is not built. From monitor/web run: "
                "npm install && npm run build"
            )
            body = message.encode("utf-8")
            self.send_response(200 if path == "/" else 404)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        relative = "index.html" if path == "/" else path.lstrip("/")
        candidate = (WEB_DIST / relative).resolve()
        if WEB_DIST.resolve() not in candidate.parents and candidate != WEB_DIST.resolve():
            self._json(404, {"error": "not found"})
            return
        if not candidate.is_file():
            candidate = WEB_DIST / "index.html"
        content = candidate.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", CONTENT_TYPES.get(candidate.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def make_server(host: str, port: int, root: Path, repo: Path) -> ThreadingHTTPServer:
    ControlHandler.root = root
    ControlHandler.repo = repo
    return ThreadingHTTPServer((host, port), ControlHandler)
