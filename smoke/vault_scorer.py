"""Score a smoke drop against the fake vault.

Separate entry point from the loop. It reads vault/ and drop/, and writes
only under vault/. It never writes a number back to public/.
"""

from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
from pathlib import Path


def _mean_y(path: Path) -> float:
    total = 0.0
    count = 0
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            total += float(row["y"])
            count += 1
    if count == 0:
        raise ValueError("fake D0 series is empty")
    return total / count


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Score a finished smoke drop in the fake vault")
    parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    count = score(args.run)
    print(f"vault rows {count}")


def score(run_dir: Path, *, fail: bool = False) -> int:
    vault = run_dir / "vault"
    drop = run_dir / "drop" / "outbox.jsonl"
    series = vault / "fake_d0.csv"
    canary = (vault / "canary.txt").read_text(encoding="utf-8").strip()
    if not canary:
        raise ValueError("vault canary is missing")
    rows = [json.loads(line) for line in drop.read_text(encoding="utf-8").splitlines() if line.strip()]
    if fail:
        raise RuntimeError("vault scorer stopped; the public run is already finished")
    mean_y = _mean_y(series)
    db_path = vault / "d0_results.sqlite"
    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS d0_score (
                 artifact_sha256 TEXT PRIMARY KEY,
                 k INTEGER NOT NULL,
                 s0 REAL NOT NULL
               )"""
        )
        for row in rows:
            artifact = Path(row["artifact_path"])
            digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
            if digest != row["artifact_sha256"]:
                raise ValueError("artifact hash does not match the drop row")
            connection.execute(
                "INSERT OR IGNORE INTO d0_score (artifact_sha256, k, s0) VALUES (?, ?, ?)",
                (digest, row["k"], mean_y),
            )
        connection.commit()
        count = connection.execute("SELECT COUNT(*) FROM d0_score").fetchone()[0]
    finally:
        connection.close()
    return int(count)


if __name__ == "__main__":
    main()
