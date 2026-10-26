"""Fixed-horizon smoke loop.

The callable receives the public directory and the drop directory. It has no
path to the vault and does not import the vault scorer.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from smoke.public_store import append_event, rebuild_monitor

DESIGN_HASH = "smoke-dev"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def run_loop(
    public_dir: Path,
    drop_dir: Path,
    *,
    run_id: str,
    j_sel: list[list[float]],
    seeds: list[int],
) -> dict:
    """Run exactly len(j_sel) steps.

    j_sel[k] is the per-seed area on D1_sel for the framework at that step.
    There is no stop or extend argument: the horizon is the length of j_sel.
    """
    if not j_sel:
        raise ValueError("the loop needs at least one step")
    for areas in j_sel:
        if len(areas) != len(seeds):
            raise ValueError("each step needs one area per seed")

    events_path = public_dir / "events.jsonl"
    if events_path.exists():
        raise FileExistsError("refusing to append to an existing smoke log")
    artifact_dir = public_dir / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    drop_dir.mkdir(parents=True, exist_ok=True)
    outbox = drop_dir / "outbox.jsonl"

    per_step_median: list[float] = []
    spreads: list[float] = []
    for index, areas in enumerate(j_sel, start=1):
        ts = _now()
        append_event(
            events_path,
            {
                "type": "meta_step",
                "ts": ts,
                "design_hash": DESIGN_HASH,
                "k": index,
                "status": "accepted",
                "phase": "smoke",
                "budget_gpu_h": None,
                "budget_tokens": None,
            },
        )
        append_event(
            events_path,
            {
                "type": "log_line",
                "ts": ts,
                "design_hash": DESIGN_HASH,
                "phase": "smoke",
                "message": f"step {index} accepted phase=smoke",
            },
        )
        for seed, area in zip(seeds, areas):
            append_event(
                events_path,
                {
                    "type": "eval_event",
                    "ts": ts,
                    "design_hash": DESIGN_HASH,
                    "phase": "smoke",
                    "run_id": f"{run_id}-k{index}-s{seed}",
                    "k": index,
                    "seed": seed,
                    "b": 1.0,
                    "split": "sel",
                    "s": area,
                },
            )
        stub = artifact_dir / f"step-{index}.txt"
        stub.write_text(f"stub framework step {index}\n", encoding="utf-8")
        digest = hashlib.sha256(stub.read_bytes()).hexdigest()
        drop = {
            "event_id": f"{run_id}-{index}",
            "type": "meta_step_completed",
            "phase": "smoke",
            "k": index,
            "run_id": run_id,
            "artifact_path": str(stub),
            "artifact_sha256": digest,
            "design_hash": DESIGN_HASH,
            "ts": ts,
        }
        with outbox.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(drop, sort_keys=True) + "\n")
        per_step_median.append(_median(areas))
        spreads.append(max(areas) - min(areas))

    rebuild_monitor(events_path, public_dir / "monitor.db")
    ordered_spreads = sorted(spreads)
    sigma = ordered_spreads[len(ordered_spreads) // 2]
    return {
        "phase": "smoke",
        "run_id": run_id,
        "steps": len(j_sel),
        "seeds": list(seeds),
        "j_sel_median": per_step_median,
        "sigma_seed": sigma,
        "design_hash": DESIGN_HASH,
        "excluded_from_main_analysis": True,
    }
