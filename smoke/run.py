"""Run the synthetic smoke test.

Default curve is the section 7.3 fixture, not a measurement. The process
writes the vault and then runs the loop without reading the vault back.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from smoke.decide_k import decide_k
from smoke.leak import find_leaks
from smoke.loop import run_loop
from smoke.materialise import materialise


def _load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def execute(
    root: Path,
    *,
    steps: int,
    n: int,
    run_id: str | None = None,
    config_path: Path = Path("configs/smoke.json"),
) -> dict:
    config = _load_config(config_path)
    if steps < 1:
        raise ValueError("steps must be positive")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = run_id or f"smoke-{stamp}"
    run_dir = root / run_id
    if run_dir.exists():
        raise FileExistsError(f"{run_dir} already exists")
    materialise(run_dir, n=n)

    fixture = [float(value) for value in config["j_sel_fixture"]]
    if steps == len(fixture):
        medians = fixture
        curve_source = "fixture"
    else:
        medians = [0.2 + 0.05 * (k - 1) for k in range(1, steps + 1)]
        curve_source = "placeholder"
    seeds = [int(seed) for seed in config["seeds"]]
    per_seed = [[value for _ in seeds] for value in medians]

    summary = run_loop(
        run_dir / "public",
        run_dir / "drop",
        run_id=run_id,
        j_sel=per_seed,
        seeds=seeds,
    )
    summary["curve_source"] = curve_source
    summary["n"] = n
    decision = None
    if steps == 5 and curve_source == "fixture":
        decision = decide_k(summary["j_sel_median"], summary["sigma_seed"]).as_dict()
        summary["decision_note"] = config["fixture_note"]
    elif steps == 5:
        decision = decide_k(summary["j_sel_median"], summary["sigma_seed"]).as_dict()
    summary["decision"] = decision
    summary["scorer"] = "not_run"

    report_path = run_dir / "public" / "smoke_report.json"
    summary["leak_check"] = "pending"
    report_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    leaks = find_leaks([run_dir / "public", run_dir / "drop", run_dir / "core_only"])
    if leaks:
        summary["leak_check"] = "fail"
        report_path.unlink()
        (run_dir / "public" / "leak_fail.txt").write_text(
            "leak check failed; vault material reached a run-side file\n",
            encoding="utf-8",
        )
        raise SystemExit(1)
    summary["leak_check"] = "pass"
    report_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Synthetic control-path smoke test")
    parser.add_argument("--steps", type=int, default=5)
    parser.add_argument("--n", type=int, default=70128)
    parser.add_argument("--root", type=Path, default=Path("runs/smoke"))
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--config", type=Path, default=Path("configs/smoke.json"))
    args = parser.parse_args(argv)
    summary = execute(
        args.root,
        steps=args.steps,
        n=args.n,
        run_id=args.run_id,
        config_path=args.config,
    )
    decision = summary["decision"]
    print(f"run {summary['run_id']}  steps={summary['steps']}  leak={summary['leak_check']}")
    print(f"curve_source={summary['curve_source']}  scorer={summary['scorer']}")
    if decision is None:
        print("K rule not applied; it is defined on five fixture or measured points")
    else:
        print(
            f"dry-run K={decision['k']}  budget_limited={decision['budget_limited']}  "
            f"({decision['reason']})"
        )


if __name__ == "__main__":
    main()
