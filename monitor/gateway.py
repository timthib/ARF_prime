"""Allow-listed commands. The core still accepts or refuses each one.

The HTTP body is four fields. Nothing read from a payload is copied back,
and a core return value is not copied back either.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

ALLOWED: tuple[str, ...] = (
    "materialise_split",
    "run_baselines",
    "start_pilot",
    "freeze",
    "bump",
    "start_meta_run",
    "kill_framework",
    "start_phase2",
    "restart_meta_run",
)

FORBIDDEN: frozenset[str] = frozenset(
    {"stop", "extend", "set_K", "set_k", "set_budget"}
)

FIELDS: dict[str, tuple[str, ...]] = {
    "materialise_split": (),
    "run_baselines": (),
    "start_pilot": ("replicate",),
    "freeze": (),
    "bump": ("reason",),
    "start_meta_run": ("arm", "replicate"),
    "kill_framework": ("meta_run_id", "framework_id", "reason"),
    "start_phase2": ("meta_run_id",),
    "restart_meta_run": ("meta_run_id",),
}

PUBLIC_KEYS: tuple[str, ...] = ("status", "event_id", "reason", "verb")

NOT_INSTALLED = "core command is not installed"
NOT_API = "this command is not part of the core API"


def public_result(status: str, verb: str, reason: str = "", event_id: str | None = None) -> dict:
    return {
        "status": status,
        "event_id": event_id,
        "reason": reason,
        "verb": verb,
    }


def resolve_command(verb: str):
    """Return the core callable, or None when that command is not installed."""
    try:
        import core.commands as commands
    except ImportError:
        return None
    function = getattr(commands, verb, None)
    if not callable(function):
        return None
    return function


def list_commands() -> list[dict]:
    listed = []
    for verb in ALLOWED:
        if resolve_command(verb) is None:
            listed.append({"verb": verb, "available": False, "reason": NOT_INSTALLED})
        else:
            listed.append({"verb": verb, "available": True, "reason": ""})
    return listed


def _clean_payload(verb: str, payload: dict) -> tuple[dict | None, str]:
    clean = {key: payload[key] for key in FIELDS[verb] if key in payload}
    if verb in ("bump", "kill_framework"):
        reason = clean.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            if verb == "kill_framework":
                return None, "a kill needs a reason"
            return None, "a bump needs a reason"
    if verb in ("kill_framework", "start_phase2", "restart_meta_run"):
        meta_run_id = clean.get("meta_run_id")
        if not isinstance(meta_run_id, str) or not meta_run_id.strip():
            return None, "the command needs a meta run id"
    if verb == "kill_framework":
        framework_id = clean.get("framework_id")
        if not isinstance(framework_id, str) or not framework_id.strip():
            return None, "a kill needs a framework id"
    if verb == "start_meta_run":
        arm = clean.get("arm")
        if type(arm) is not int or arm not in range(1, 7):
            return None, "arm must be an integer from 1 to 6"
    if "replicate" in clean and clean["replicate"] is not None:
        replicate = clean["replicate"]
        if type(replicate) is not int or replicate < 1:
            return None, "replicate must be a positive integer"
    return clean, ""


def _append_command(root: Path, verb: str, event_id: str, payload: dict) -> None:
    root.mkdir(parents=True, exist_ok=True)
    row = {
        "type": "command",
        "verb": verb,
        "event_id": event_id,
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": "accepted",
        "args": payload,
    }
    with (root / "commands.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def execute(root: Path, verb: str, payload: dict | None = None) -> dict:
    """Accept or refuse one command. The return value has only public keys."""
    if not isinstance(verb, str) or verb in FORBIDDEN or verb not in ALLOWED:
        name = verb if isinstance(verb, str) else ""
        return public_result("refused", name, NOT_API)
    body = payload or {}
    if not isinstance(body, dict):
        return public_result("refused", verb, "the command payload must be an object")
    clean, problem = _clean_payload(verb, body)
    if clean is None:
        return public_result("refused", verb, problem)
    function = resolve_command(verb)
    if function is None:
        return public_result("refused", verb, NOT_INSTALLED)
    try:
        function(clean)
    except Exception:
        return public_result("refused", verb, "the core refused the command")
    event_id = uuid.uuid4().hex
    _append_command(root, verb, event_id, clean)
    return public_result("accepted", verb, "", event_id)
