"""Rank correlations for the hold-out pane. Ordinality only."""

from __future__ import annotations

import math


def average_ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda index: values[index])
    ranks = [0.0] * len(values)
    start = 0
    while start < len(values):
        end = start
        while end + 1 < len(values) and values[order[end + 1]] == values[order[start]]:
            end += 1
        rank = (start + end) / 2 + 1
        for cursor in range(start, end + 1):
            ranks[order[cursor]] = rank
        start = end + 1
    return ranks


def pearson(xs: list[float], ys: list[float]) -> float:
    count = len(xs)
    if count == 0 or count != len(ys):
        raise ValueError("pearson needs two equal samples")
    mean_x = sum(xs) / count
    mean_y = sum(ys) / count
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    spread_x = math.sqrt(sum((x - mean_x) ** 2 for x in xs))
    spread_y = math.sqrt(sum((y - mean_y) ** 2 for y in ys))
    if spread_x == 0 or spread_y == 0:
        return 0.0
    return num / (spread_x * spread_y)


def spearman(xs: list[float], ys: list[float]) -> float:
    return pearson(average_ranks(xs), average_ranks(ys))


def kendall_tau_b(xs: list[float], ys: list[float]) -> float:
    """Kendall tau-b. Ties on one axis only enter the denominator."""
    count = len(xs)
    concordant = discordant = tie_x = tie_y = 0
    for left in range(count):
        for right in range(left + 1, count):
            dx = xs[left] - xs[right]
            dy = ys[left] - ys[right]
            if dx == 0 and dy == 0:
                continue
            if dx == 0:
                tie_x += 1
            elif dy == 0:
                tie_y += 1
            elif dx * dy > 0:
                concordant += 1
            else:
                discordant += 1
    denom = math.sqrt((concordant + discordant + tie_x) * (concordant + discordant + tie_y))
    if denom == 0:
        return 0.0
    return (concordant - discordant) / denom


def rank_summary(pairs: list[tuple[str, float, float]]) -> dict:
    """pairs are (framework_id, j_sel, j0). Election is argmax j_sel."""
    if not pairs:
        raise ValueError("rank summary needs at least one framework")
    elected = max(pairs, key=lambda item: (item[1], item[0]))
    j0_elected = elected[2]
    better = sum(1 for _fid, _sel, j0 in pairs if j0 > j0_elected)
    others = [item for item in pairs if item[0] != elected[0]]
    wins = 0.0
    for _fid, _sel, j0 in others:
        if j0_elected > j0:
            wins += 1
        elif j0_elected == j0:
            wins += 0.5
    p_win = 1.0 if not others else wins / len(others)
    j0s = [item[2] for item in pairs]
    regret = max(j0s) - j0_elected
    span = max(j0s) - min(j0s)
    return {
        "n": len(pairs),
        "spearman": spearman([item[1] for item in pairs], j0s),
        "kendall": kendall_tau_b([item[1] for item in pairs], j0s),
        "elected_framework_id": elected[0],
        "elected_rank": 1 + better,
        "p_win": p_win,
        "regret": regret,
        "rel_regret": 0.0 if span == 0 else regret / span,
    }
