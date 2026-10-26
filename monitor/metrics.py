"""Areas under a best-so-far step curve. Methodology section 4."""

from __future__ import annotations


def median(values: list[float]) -> float:
    ordered = sorted(values)
    count = len(ordered)
    if count == 0:
        raise ValueError("median of an empty sample")
    mid = count // 2
    if count % 2 == 1:
        return ordered[mid]
    return 0.5 * (ordered[mid - 1] + ordered[mid])


def area(points: list[tuple[float, float]], budget: float) -> float:
    """Normalised area of a step curve on [0, budget].

    ``points`` are incumbent changes ``(b, s)`` in non-decreasing ``b``.
    The score is 0 before the first change. The score that starts at a
    change holds until the next change. If the last change is before
    ``budget``, that score is held out to ``budget`` (carry-forward).
    """
    if budget <= 0:
        raise ValueError("budget must be positive")
    knots: list[tuple[float, float]] = [(0.0, 0.0)]
    for raw_b, raw_s in points:
        b = float(raw_b)
        if b < knots[-1][0] - 1e-9:
            raise ValueError("curve points must be in time order")
        if b > budget + 1e-9:
            break
        knots.append((min(b, budget), float(raw_s)))
    if knots[-1][0] < budget:
        knots.append((budget, knots[-1][1]))
    total = 0.0
    for (b0, score), (b1, _next) in zip(knots, knots[1:]):
        total += score * (b1 - b0)
    return total / budget
