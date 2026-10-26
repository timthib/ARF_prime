"""Read model for the hold-out room."""

from __future__ import annotations

import json
import math
import sqlite3
from pathlib import Path

from d0vault.audit import read_looks


def _connect(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _meta(connection: sqlite3.Connection) -> dict[str, str]:
    return {row["key"]: row["value"] for row in connection.execute("SELECT key, value FROM d0_meta")}


def board(root: Path, k: int | None = None) -> dict:
    connection = _connect(root / "d0_results.sqlite")
    try:
        meta = _meta(connection)
        k_max = int(meta["k_max"])
        step = k_max if k is None else max(1, min(int(k), k_max))
        frameworks = [
            dict(row)
            for row in connection.execute("SELECT * FROM d0_framework WHERE k <= ? ORDER BY k", (step,))
        ]
        curves = []
        for framework in frameworks:
            for seed in (1, 2, 3):
                points = [
                    {"b": row["b"], "s": row["s0"]}
                    for row in connection.execute(
                        "SELECT b, s0 FROM d0_curve WHERE framework_id = ? AND seed = ? ORDER BY b",
                        (framework["framework_id"], seed),
                    )
                ]
                curves.append({"framework_id": framework["framework_id"], "seed": seed, "points": points})
        gap = [dict(row) for row in connection.execute("SELECT * FROM d0_gap WHERE k <= ? ORDER BY k", (step,))]
        dagger = None
        best_j0 = None
        for row in gap:
            if best_j0 is None or row["j0"] > best_j0:
                best_j0 = row["j0"]
                dagger = row["k"]
        rank = connection.execute("SELECT * FROM d0_rank WHERE k = ?", (step,)).fetchone()
        points = [
            dict(row)
            for row in connection.execute(
                "SELECT * FROM d0_rank_point WHERE k = ? ORDER BY rank_sel",
                (step,),
            )
        ]
        n = len(points)
        median_rank = math.ceil((n + 1) / 2) if n else None
        elected_id = None if rank is None else rank["elected_framework_id"]
        for point in points:
            markers = []
            if point["framework_id"] == elected_id:
                markers.append("elected")
            if point["rank_0"] == 1:
                markers.append("best_d0")
            if point["rank_sel"] == n:
                markers.append("worst_sel")
            if point["rank_sel"] == median_rank:
                markers.append("median")
            if point["rank_sel"] == 2:
                markers.append("second")
            point["markers"] = markers
        roles = (
            ("best", 1),
            ("second", 2),
            ("median", median_rank),
            ("worst", n),
        )
        four = []
        by_rank = {point["rank_sel"]: point for point in points}
        for role, rank_sel in roles:
            point = by_rank.get(rank_sel)
            if point is None:
                continue
            four.append(
                {
                    "role": role,
                    "framework_id": point["framework_id"],
                    "j_sel": point["j_sel"],
                    "j0": point["j0"],
                    "rank_0": point["rank_0"],
                }
            )
        seasons = [
            dict(row)
            for row in connection.execute(
                "SELECT framework_id, djf, mam, jja, son FROM d0_season WHERE k <= ? ORDER BY k",
                (step,),
            )
        ]
        elected = next((row for row in frameworks if row["framework_id"] == elected_id), None)
        spread_elected = None
        if elected is not None:
            spread_elected = {
                "framework_id": elected["framework_id"],
                "seeds": [elected["j0_seed1"], elected["j0_seed2"], elected["j0_seed3"]],
                "median": elected["j0_median"],
            }
        ideal = None
        if step == k_max and meta.get("f_ideal"):
            ideal = json.loads(meta["f_ideal"])
        looks = read_looks(root / "d0_audit.jsonl")
        return {
            "fixture": meta.get("fixture") == "1",
            "design_hash": meta.get("design_hash"),
            "k": step,
            "k_max": k_max,
            "looks": len(looks),
            "health": {
                "state": meta.get("scorer_state") or "stopped",
                "queue_depth": int(meta.get("queue_depth") or 0),
            },
            "curves": curves,
            "frameworks": [
                {
                    "framework_id": row["framework_id"],
                    "k": row["k"],
                    "j_sel": row["j_sel"],
                    "j0_median": row["j0_median"],
                    "j0_min": row["j0_min"],
                    "j0_max": row["j0_max"],
                }
                for row in frameworks
            ],
            "gap": gap,
            "k_dagger": dagger,
            "spread": {"elected": spread_elected, "f_ideal": ideal},
            "ranking": {
                "n": None if rank is None else rank["n"],
                "spearman": None if rank is None else rank["spearman"],
                "kendall": None if rank is None else rank["kendall"],
                "elected_framework_id": elected_id,
                "elected_rank": None if rank is None else rank["elected_rank"],
                "p_win": None if rank is None else rank["p_win"],
                "regret": None if rank is None else rank["regret"],
                "rel_regret": None if rank is None else rank["rel_regret"],
                "points": points,
                "four_point": four,
                "seasons": seasons,
            },
            "audit": [
                {"ts": row["ts"], "page": row["page"], "params": row["params"]}
                for row in looks[-8:]
            ],
        }
    finally:
        connection.close()
