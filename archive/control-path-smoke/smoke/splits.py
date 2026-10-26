"""Chronological hour ranges for D1_fit, D1_sel and D0.

Fractions of N are 0.65, 0.15 and 0.20. Each gap is taken from the start of
the later set, which is the definition in methodology section 3.2.
"""

from __future__ import annotations


def split_bounds(n: int, fit_frac: float = 0.65, d1_frac: float = 0.80, gap: int = 48) -> dict[str, tuple[int, int]]:
    if n <= 0:
        raise ValueError("n must be positive")
    if gap < 0:
        raise ValueError("gap must be non-negative")
    if not 0 < fit_frac < d1_frac < 1:
        raise ValueError("fractions must satisfy 0 < fit < d1 < 1")
    n_fit = int(fit_frac * n)
    n_d1 = int(d1_frac * n)
    if n_fit < 1 or n_fit + gap >= n_d1 or n_d1 + gap >= n:
        raise ValueError("series is too short for these fractions and gap")
    return {
        "D1_fit": (1, n_fit),
        "gap": (n_fit + 1, n_fit + gap),
        "D1_sel": (n_fit + gap + 1, n_d1),
        "embargo": (n_d1 + 1, n_d1 + gap),
        "D0": (n_d1 + gap + 1, n),
    }


def n_hours(bounds: tuple[int, int]) -> int:
    start, end = bounds
    return end - start + 1


def n_origins(hours: int, lookback: int = 24, horizon: int = 24) -> int:
    return hours - lookback - horizon + 1


def windows_stay_inside(bounds: dict[str, tuple[int, int]], lookback: int = 24, horizon: int = 24) -> bool:
    """Every origin in a set uses hours that belong to that set only."""
    owned = ("D1_fit", "D1_sel", "D0")
    for name in owned:
        start, end = bounds[name]
        first = start + lookback - 1
        last = end - horizon
        if first > last:
            continue
        for origin in (first, last):
            input_start = origin - lookback + 1
            target_end = origin + horizon
            if input_start < start or target_end > end:
                return False
    ranges = [bounds[name] for name in ("D1_fit", "gap", "D1_sel", "embargo", "D0")]
    ranges.sort()
    for (left_end, right) in zip(ranges, ranges[1:]):
        if left_end[1] + 1 != right[0]:
            return False
    return True
