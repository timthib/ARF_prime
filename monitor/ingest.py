"""Rebuild monitor.db from an append-only JSONL event log."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

SCHEMA = (Path(__file__).with_name("schema.sql")).read_text(encoding="utf-8")

TABLES: dict[str, list[str]] = {
    "run_header": [
        "meta_run_id", "arm", "arm_name", "replicate", "phase", "topology",
        "k_horizon", "b_gpu", "b_step_gpu", "b_step_tokens", "design_hash",
        "design_version", "design_ok", "changed_after_d0_view", "last_d0_look_ts",
        "as_of", "scorer_state", "kappa", "ts",
    ],
    "meta_step": [
        "meta_run_id", "ts", "design_hash", "k", "t_start", "t_end",
        "budget_gpu_h", "budget_tokens", "spent_gpu_h", "spent_tokens",
        "l0_s", "l1_s", "hypothesis_id", "hypothesis_text", "status", "phase",
        "tamper_reason", "parent_framework_id", "edit_json", "l0_thinking",
    ],
    "l1_run": [
        "meta_run_id", "ts", "design_hash", "run_id", "k", "framework_id",
        "parent_framework_id", "seed", "alloc_gpu_h", "alloc_tokens", "status",
        "kill_reason", "phase", "kappa", "gpu_h_used", "tokens_used",
    ],
    "framework": [
        "meta_run_id", "ts", "design_hash", "framework_id", "k_first",
        "parent_framework_id", "level1_snapshot", "rules_json", "edit_json",
        "n_seeds", "j_sel_median", "j_sel_seed1", "j_sel_seed2", "j_sel_seed3",
        "ci_lo", "ci_hi", "n_killed", "elected", "hypothesis_text",
    ],
    "model": [
        "model_id", "meta_run_id", "ts", "design_hash", "run_id", "framework_id",
        "branch_id", "parent_model_id", "operator", "family", "seed", "b_created", "u",
        "status", "artifact_path", "artifact_sha256", "is_ideal_model", "seq",
        "thinking",
    ],
    "eval_event": [
        "meta_run_id", "ts", "design_hash", "run_id", "model_id", "b", "split",
        "s", "e_mae", "trigger",
    ],
    "ledger": [
        "meta_run_id", "ts", "design_hash", "role", "run_id", "k", "gpu_h",
        "tokens_in", "tokens_out", "cum_gpu_h", "cum_tokens",
    ],
    "gpu_sample": [
        "meta_run_id", "ts", "design_hash", "run_id", "k", "model_id", "b",
        "gpu_busy",
    ],
    "log_line": [
        "meta_run_id", "ts", "design_hash", "run_id", "k", "role", "model_id",
        "message",
    ],
    "kill_event": [
        "meta_run_id", "ts", "design_hash", "run_id", "framework_id", "k", "reason",
    ],
    "d0_outbox": [
        "event_id", "meta_run_id", "ts", "design_hash", "type", "k", "run_id",
        "model_id", "artifact_path", "artifact_sha256", "hmac",
    ],
}


def load_events(path: Path) -> list[dict]:
    events: list[dict] = []
    text = path.read_text(encoding="utf-8")
    for line_no, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_no} is not JSON") from exc
        if "type" not in event:
            raise ValueError(f"{path}:{line_no} has no type")
        events.append(event)
    return events


def ingest(jsonl_path: Path, db_path: Path) -> None:
    """Replace ``db_path`` with the contents of the JSONL log."""
    events = load_events(jsonl_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    connection = sqlite3.connect(db_path)
    try:
        connection.executescript(SCHEMA)
        for event in events:
            kind = event["type"]
            columns = TABLES.get(kind)
            if columns is None:
                raise ValueError(f"unknown event type: {kind}")
            if kind == "d0_outbox":
                event = dict(event)
                event["type"] = event.get("outbox_type")
            values = [event.get(column) for column in columns]
            placeholders = ", ".join("?" for _ in columns)
            names = ", ".join(columns)
            connection.execute(
                f"INSERT INTO {kind} ({names}) VALUES ({placeholders})",
                values,
            )
        connection.commit()
    finally:
        connection.close()
