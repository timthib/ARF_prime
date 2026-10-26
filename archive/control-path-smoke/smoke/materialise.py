"""Write a synthetic series into separate directories.

public/ receives D1_fit only. core_only/ receives D1_sel labels. vault/ receives
the shifted fake D0 and a canary token. Callers that run the loop must pass
public/ and must not be given vault/.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path

from smoke.splits import split_bounds

CANARY = "CANARY-SMOKE-D0-7c1e9a"
SHIFT = 2.718281828


def synthetic_y(hour: int, shift: float = 0.0) -> float:
    daily = math.sin(2 * math.pi * hour / 24)
    yearly = 0.1 * math.sin(2 * math.pi * hour / (24 * 365))
    return daily + yearly + shift


def _write_series(path: Path, start: int, end: int, shift: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["hour", "y"])
        for hour in range(start, end + 1):
            writer.writerow([hour, f"{synthetic_y(hour, shift):.10f}"])


def materialise(run_dir: Path, n: int = 70128, gap: int = 48) -> dict[str, tuple[int, int]]:
    bounds = split_bounds(n, gap=gap)
    public = run_dir / "public"
    core_only = run_dir / "core_only"
    vault = run_dir / "vault"
    fit = bounds["D1_fit"]
    sel = bounds["D1_sel"]
    holdout = bounds["D0"]
    _write_series(public / "d1_fit.csv", fit[0], fit[1], shift=0.0)
    _write_series(core_only / "d1_sel.csv", sel[0], sel[1], shift=0.0)
    _write_series(vault / "fake_d0.csv", holdout[0], holdout[1], shift=SHIFT)
    (vault / "canary.txt").write_text(CANARY + "\n", encoding="utf-8")
    return bounds
