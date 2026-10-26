"""Hash-chained look log. One user id. No metric values."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

GENESIS = "0" * 64


def _canonical(row: dict) -> str:
    return json.dumps(row, sort_keys=True, separators=(",", ":"))


def append_look(path: Path, row: dict) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    prev = GENESIS
    if path.exists():
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if lines:
            prev = json.loads(lines[-1])["row_hash"]
    body = {
        "ts": row["ts"],
        "session_id": row["session_id"],
        "user_id": "user",
        "page": row["page"],
        "params": row.get("params") or "",
        "design_hash": row.get("design_hash") or "",
        "last_event_id_seen": row.get("last_event_id_seen") or "",
        "prev_hash": prev,
    }
    digest = hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()
    body["row_hash"] = digest
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(body, sort_keys=True) + "\n")
    return body


def verify(path: Path) -> bool:
    if not path.exists():
        return True
    prev = GENESIS
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        stored = json.loads(line)
        row_hash = stored.get("row_hash")
        body = {key: value for key, value in stored.items() if key != "row_hash"}
        if body.get("prev_hash") != prev:
            return False
        if hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest() != row_hash:
            return False
        if body.get("user_id") != "user":
            return False
        prev = row_hash
    return True


def read_looks(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
