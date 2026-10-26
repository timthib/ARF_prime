"""Hold-out room. Loopback only, one session, every board read is logged."""

from __future__ import annotations

import json
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from d0vault.audit import append_look
from d0vault.fixture import hash_password
from d0vault.queries import board

WEB_DIST = Path(__file__).resolve().parent / "web" / "dist"
MAX_BODY = 16_384
ROUTES = ("/api/login", "/api/logout", "/api/board")

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".svg": "image/svg+xml",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _stamp(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class D0Handler(BaseHTTPRequestHandler):
    root: Path
    timeout_s: int = 900
    session: dict | None = None

    def log_message(self, fmt: str, *args) -> None:
        return

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        if path == "/api/board":
            self._board(parse_qs(parsed.query))
            return
        if path.startswith("/api/"):
            self._json(404, {"error": "not found"})
            return
        self._static(path)

    def do_POST(self) -> None:
        path = unquote(urlparse(self.path).path)
        if path == "/api/login":
            self._login()
            return
        if path == "/api/logout":
            self._logout()
            return
        self._json(404, {"error": "not found"})

    def _login(self) -> None:
        payload = self._body()
        if payload is None:
            return
        password = payload.get("password") if isinstance(payload, dict) else None
        auth = json.loads((self.root / "auth.json").read_text(encoding="utf-8"))
        salt = bytes.fromhex(auth["salt"])
        offered = hash_password(password, salt) if isinstance(password, str) else ""
        if not secrets.compare_digest(offered, auth["hash"]):
            self._record("login_failed", "")
            self._json(401, {"ok": False, "reason": "refused"})
            return
        current = self._live_session()
        if current is not None:
            self._record("login_refused", "")
            self._json(403, {"ok": False, "reason": "a session is already open"})
            return
        token = secrets.token_urlsafe(32)
        public_id = secrets.token_hex(8)
        D0Handler.session = {
            "token": token,
            "session_id": public_id,
            "last_seen": _now(),
        }
        self._record("login", "", session_id=public_id)
        body = json.dumps({"ok": True}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header(
            "Set-Cookie",
            f"d0session={token}; HttpOnly; SameSite=Strict; Path=/",
        )
        self.end_headers()
        self.wfile.write(body)

    def _logout(self) -> None:
        current = self._live_session()
        token = self._cookie()
        if current is not None and token == current["token"]:
            D0Handler.session = None
        self._json(200, {"ok": True})

    def _board(self, query: dict) -> None:
        current = self._live_session()
        if current is None or self._cookie() != current["token"]:
            self._json(401, {"ok": False, "reason": "sign in"})
            return
        current["last_seen"] = _now()
        raw_k = (query.get("k") or [None])[0]
        try:
            k = None if raw_k is None else int(raw_k)
        except ValueError:
            self._json(400, {"error": "k must be an integer"})
            return
        self._record("board", "" if k is None else f"k={k}", session_id=current["session_id"])
        self._json(200, board(self.root, k))

    def _record(self, page: str, params: str, session_id: str = "none") -> None:
        design = ""
        last_event = ""
        database = self.root / "d0_results.sqlite"
        if database.exists():
            connection = sqlite3.connect(database)
            try:
                row = connection.execute(
                    "SELECT value FROM d0_meta WHERE key = 'design_hash'"
                ).fetchone()
                design = "" if row is None else row[0]
                last_event = f"k-{connection.execute('SELECT MAX(k) FROM d0_gap').fetchone()[0]}"
            finally:
                connection.close()
        stored = append_look(
            self.root / "d0_audit.jsonl",
            {
                "ts": _stamp(_now()),
                "session_id": session_id,
                "page": page,
                "params": params,
                "design_hash": design,
                "last_event_id_seen": last_event,
            },
        )
        if database.exists():
            connection = sqlite3.connect(database)
            try:
                connection.execute(
                    """INSERT INTO d0_view_log (
                        ts, session_id, user_id, page, params, design_hash,
                        last_event_id_seen, prev_hash, row_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        stored["ts"], stored["session_id"], stored["user_id"], stored["page"],
                        stored["params"], stored["design_hash"], stored["last_event_id_seen"],
                        stored["prev_hash"], stored["row_hash"],
                    ),
                )
                connection.commit()
            finally:
                connection.close()

    def _live_session(self) -> dict | None:
        current = D0Handler.session
        if current is None:
            return None
        if _now() - current["last_seen"] > timedelta(seconds=self.timeout_s):
            D0Handler.session = None
            return None
        return current

    def _cookie(self) -> str | None:
        raw = self.headers.get("Cookie")
        if not raw:
            return None
        jar = SimpleCookie()
        jar.load(raw)
        morsel = jar.get("d0session")
        return None if morsel is None else morsel.value

    def _body(self) -> dict | None:
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length > MAX_BODY:
            self._json(400, {"error": "body too large"})
            return None
        raw = self.rfile.read(length) if length else b""
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._json(400, {"error": "body must be JSON"})
            return None
        if not isinstance(payload, dict):
            self._json(400, {"error": "body must be a JSON object"})
            return None
        return payload

    def _static(self, path: str) -> None:
        if not WEB_DIST.exists():
            message = "D0 room UI is not built. From d0vault/web run: npm install && npm run build"
            body = message.encode("utf-8")
            self.send_response(200 if path == "/" else 404)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        relative = "index.html" if path == "/" else path.lstrip("/")
        candidate = (WEB_DIST / relative).resolve()
        root = WEB_DIST.resolve()
        if root not in candidate.parents and candidate != root:
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


def make_server(host: str, port: int, root: Path, timeout_s: int = 900) -> ThreadingHTTPServer:
    if host not in ("127.0.0.1", "localhost"):
        raise SystemExit("the D0 room binds to 127.0.0.1 only")
    D0Handler.root = root
    D0Handler.timeout_s = timeout_s
    D0Handler.session = None
    return ThreadingHTTPServer(("127.0.0.1", port), D0Handler)
