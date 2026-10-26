"""Append-only public log and the monitor database rebuilt from it.

The database accepts selection scores only. A vault field cannot be stored.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

FORBIDDEN_KEYS = frozenset({"s0", "j0", "j_0", "e_mae_d0", "canary"})


def append_event(path: Path, event: dict) -> None:
    if FORBIDDEN_KEYS & event.keys():
        raise ValueError("public event carries a vault field")
    if event.get("phase", "smoke") != "smoke":
        raise ValueError("this log accepts phase=smoke only")
    if event["type"] == "eval_event" and event.get("split") != "sel":
        raise ValueError("eval events must be split=sel")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")


def read_events(path: Path) -> list[dict]:
    events = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                events.append(json.loads(line))
    return events


def rebuild_monitor(events_path: Path, db_path: Path) -> None:
    events = read_events(events_path)
    if db_path.exists():
        db_path.unlink()
    connection = sqlite3.connect(db_path)
    try:
        connection.executescript(
            """
            CREATE TABLE meta_step (
              id INTEGER PRIMARY KEY,
              ts TEXT NOT NULL,
              design_hash TEXT NOT NULL,
              k INTEGER NOT NULL,
              status TEXT NOT NULL,
              phase TEXT NOT NULL CHECK (phase = 'smoke'),
              budget_gpu_h REAL,
              budget_tokens INTEGER
            );
            CREATE TABLE eval_event (
              id INTEGER PRIMARY KEY,
              ts TEXT NOT NULL,
              design_hash TEXT NOT NULL,
              run_id TEXT NOT NULL,
              k INTEGER NOT NULL,
              seed INTEGER NOT NULL,
              b REAL NOT NULL,
              split TEXT NOT NULL CHECK (split = 'sel'),
              s REAL NOT NULL
            );
            CREATE TABLE log_line (
              id INTEGER PRIMARY KEY,
              ts TEXT NOT NULL,
              design_hash TEXT NOT NULL,
              message TEXT NOT NULL
            );
            """
        )
        for event in events:
            if FORBIDDEN_KEYS & event.keys():
                raise ValueError("refusing to store a vault field")
            kind = event["type"]
            if kind == "meta_step":
                connection.execute(
                    """INSERT INTO meta_step
                       (ts, design_hash, k, status, phase, budget_gpu_h, budget_tokens)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        event["ts"],
                        event["design_hash"],
                        event["k"],
                        event["status"],
                        event["phase"],
                        event.get("budget_gpu_h"),
                        event.get("budget_tokens"),
                    ),
                )
            elif kind == "eval_event":
                connection.execute(
                    """INSERT INTO eval_event
                       (ts, design_hash, run_id, k, seed, b, split, s)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        event["ts"],
                        event["design_hash"],
                        event["run_id"],
                        event["k"],
                        event["seed"],
                        event["b"],
                        event["split"],
                        event["s"],
                    ),
                )
            elif kind == "log_line":
                connection.execute(
                    "INSERT INTO log_line (ts, design_hash, message) VALUES (?, ?, ?)",
                    (event["ts"], event["design_hash"], event["message"]),
                )
            else:
                raise ValueError(f"unknown public event type: {kind}")
        connection.commit()
    finally:
        connection.close()
