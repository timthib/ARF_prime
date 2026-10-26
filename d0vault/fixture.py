"""Synthetic hold-out store for the D0 room.

These numbers are invented so the pane can be opened without a vault.
They are not Jena scores.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
from pathlib import Path

from d0vault.stats import rank_summary

SCHEMA = (Path(__file__).with_name("schema.sql")).read_text(encoding="utf-8")

# framework, step, J_sel, J_0
FRAMEWORKS = (
    ("v1", 1, 0.30, 0.28),
    ("v2", 2, 0.42, 0.36),
    ("v3", 3, 0.38, 0.40),
    ("v4", 4, 0.51, 0.44),
    ("v5", 5, 0.58, 0.47),
    ("v6", 6, 0.55, 0.53),
)


def hash_password(password: str, salt: bytes) -> str:
    return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1).hex()


def write_auth(root: Path, password: str) -> None:
    """Store a scrypt hash only. The plaintext is never written into the tree."""
    salt = secrets.token_bytes(16)
    payload = {"salt": salt.hex(), "hash": hash_password(password, salt)}
    (root / "auth.json").write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _seeds(center: float) -> tuple[float, float, float]:
    return (round(center - 0.02, 4), round(center, 4), round(center + 0.015, 4))


def build_demo(root: Path, password: str | None = None) -> str:
    root.mkdir(parents=True, exist_ok=True)
    chosen = password or secrets.token_hex(8)
    database = root / "d0_results.sqlite"
    if database.exists():
        database.unlink()
    connection = sqlite3.connect(database)
    try:
        connection.executescript(SCHEMA)
        connection.execute("INSERT INTO d0_meta (key, value) VALUES (?, ?)", ("design_hash", "fake-vault-dev"))
        connection.execute("INSERT INTO d0_meta (key, value) VALUES (?, ?)", ("fixture", "1"))
        connection.execute("INSERT INTO d0_meta (key, value) VALUES (?, ?)", ("scorer_state", "polling"))
        connection.execute("INSERT INTO d0_meta (key, value) VALUES (?, ?)", ("queue_depth", "0"))
        connection.execute("INSERT INTO d0_meta (key, value) VALUES (?, ?)", ("k_max", "6"))
        connection.execute(
            "INSERT INTO d0_meta (key, value) VALUES (?, ?)",
            ("f_ideal", json.dumps({"s0": 0.49, "e_mae": 1.82, "e_rmse": 2.31})),
        )
        for framework_id, k, j_sel, j0 in FRAMEWORKS:
            sel = _seeds(j_sel)
            hold = _seeds(j0)
            connection.execute(
                """INSERT INTO d0_framework (
                    framework_id, k, j_sel, j_sel_min, j_sel_max, j0_median,
                    j0_seed1, j0_seed2, j0_seed3, j0_min, j0_max, n_seeds
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 3)""",
                (
                    framework_id, k, j_sel, min(sel), max(sel), j0,
                    hold[0], hold[1], hold[2], min(hold), max(hold),
                ),
            )
            connection.execute(
                "INSERT INTO d0_season (framework_id, k, djf, mam, jja, son) VALUES (?, ?, ?, ?, ?, ?)",
                (framework_id, k, round(j0 - 0.03, 4), round(j0 + 0.02, 4), round(j0, 4), round(j0 + 0.01, 4)),
            )
            for seed_index, seed_j0 in enumerate(hold, start=1):
                connection.execute(
                    "INSERT INTO d0_curve (framework_id, seed, b, s0) VALUES (?, ?, ?, ?)",
                    (framework_id, seed_index, 0.08, round(seed_j0 * 0.55, 4)),
                )
                connection.execute(
                    "INSERT INTO d0_curve (framework_id, seed, b, s0) VALUES (?, ?, ?, ?)",
                    (framework_id, seed_index, 0.25, seed_j0),
                )
                digest = hashlib.sha256(f"{framework_id}-{seed_index}".encode()).hexdigest()
                connection.execute(
                    """INSERT INTO d0_score (
                        artifact_sha256, model_id, run_id, framework_id, seed, k, b,
                        e_mae, e_rmse, s0, n_origins, s0_djf, s0_mam, s0_jja, s0_son,
                        scorer_version, status
                    ) VALUES (?, ?, ?, ?, ?, ?, 0.25, ?, ?, ?, 1000, ?, ?, ?, ?, 'fake-1', 'ok')""",
                    (
                        digest, f"{framework_id}-s{seed_index}", f"run-{framework_id}-s{seed_index}",
                        framework_id, seed_index, k, round(2.2 - seed_j0, 4), round(2.8 - seed_j0, 4),
                        seed_j0, round(j0 - 0.03, 4), round(j0 + 0.02, 4), j0, round(j0 + 0.01, 4),
                    ),
                )
        seen: list[tuple[str, float, float]] = []
        running_best = None
        g0 = None
        for framework_id, k, j_sel, j0 in FRAMEWORKS:
            seen.append((framework_id, j_sel, j0))
            if running_best is None or j_sel > running_best[1]:
                running_best = (framework_id, j_sel, j0)
            gap = running_best[1] - running_best[2]
            if g0 is None:
                g0 = gap
            connection.execute(
                "INSERT INTO d0_gap (k, vstar_framework_id, j_sel, j0, g_k, g_k_corrected) VALUES (?, ?, ?, ?, ?, ?)",
                (k, running_best[0], running_best[1], running_best[2], gap, gap - g0),
            )
            summary = rank_summary(seen)
            connection.execute(
                """INSERT INTO d0_rank (
                    k, n, spearman, kendall, elected_framework_id, elected_rank, p_win, regret, rel_regret
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    k, summary["n"], summary["spearman"], summary["kendall"],
                    summary["elected_framework_id"], summary["elected_rank"],
                    summary["p_win"], summary["regret"], summary["rel_regret"],
                ),
            )
            ordered_sel = sorted(seen, key=lambda item: (-item[1], item[0]))
            ordered_j0 = sorted(seen, key=lambda item: (-item[2], item[0]))
            rank_sel = {item[0]: index + 1 for index, item in enumerate(ordered_sel)}
            rank_0 = {item[0]: index + 1 for index, item in enumerate(ordered_j0)}
            for fid, sel, hold in seen:
                band_sel = _seeds(sel)
                band_j0 = _seeds(hold)
                connection.execute(
                    """INSERT INTO d0_rank_point (
                        k, framework_id, j_sel, j0, rank_sel, rank_0, n_seeds,
                        j_sel_min, j_sel_max, j0_min, j0_max
                    ) VALUES (?, ?, ?, ?, ?, ?, 3, ?, ?, ?, ?)""",
                    (
                        k, fid, sel, hold, rank_sel[fid], rank_0[fid],
                        min(band_sel), max(band_sel), min(band_j0), max(band_j0),
                    ),
                )
        connection.commit()
    finally:
        connection.close()
    write_auth(root, chosen)
    audit = root / "d0_audit.jsonl"
    if audit.exists():
        audit.unlink()
    return chosen
