"""Pre-registered choice of K from a D1 curve. Methodology section 7.3.

This module has no file or database access. It cannot see D0.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class KDecision:
    k: int
    k_gain: int
    k_budget: int
    g_hat: float
    tau: float
    budget_limited: bool
    reason: str

    def as_dict(self) -> dict:
        return asdict(self)


def running_max(values: list[float]) -> list[float]:
    best: list[float] = []
    current = values[0]
    for value in values:
        current = max(current, value)
        best.append(current)
    return best


def decide_k(
    j_sel: list[float],
    sigma_seed: float,
    *,
    tau_0: float = 0.01,
    c: float = 0.5,
    rho_decay: float = 0.85,
    k_lo: int = 15,
    k_hi: int = 20,
    b_cap_gpu: float = 15.0,
    b_step_gpu: float = 0.75,
    b_cap_tokens: float = 14_000_000,
    b_step_tokens: float = 700_000,
) -> KDecision:
    """Apply section 7.3 to a 5-point J_sel curve.

    The curve is turned into the running maximum C(k) first. The anchor
    points are C(5) and C(2), as written in the spec.
    """
    if len(j_sel) != 5:
        raise ValueError("the pre-registered rule uses five meta-steps, C(1)..C(5)")
    if sigma_seed < 0:
        raise ValueError("sigma_seed must be non-negative")
    if not 0 < rho_decay < 1:
        raise ValueError("rho_decay must lie in (0, 1)")
    if k_lo > k_hi:
        raise ValueError("K_lo cannot exceed K_hi")
    if b_step_gpu <= 0 or b_step_tokens <= 0:
        raise ValueError("step budgets must be positive")

    curve = running_max(j_sel)
    g_hat = (curve[4] - curve[1]) / 3
    tau = max(tau_0, c * sigma_seed)
    if g_hat <= tau:
        k_gain = 5
    else:
        ratio = math.log(tau / g_hat) / math.log(rho_decay)
        k_gain = 5 + math.ceil(ratio - 1e-12)

    k_budget = min(
        math.floor(b_cap_gpu / b_step_gpu),
        math.floor(b_cap_tokens / b_step_tokens),
    )
    clipped = min(max(k_gain, k_lo), k_hi)
    k = min(clipped, k_budget)
    budget_limited = k_budget < k_lo
    if budget_limited:
        reason = "budget-limited, below target window"
    elif g_hat <= tau:
        reason = "recent gain at or below the noise floor; K clipped to K_lo"
    else:
        reason = "geometric decay of the recent gain, clipped to the target window and the budget"
    return KDecision(
        k=k,
        k_gain=k_gain,
        k_budget=k_budget,
        g_hat=g_hat,
        tau=tau,
        budget_limited=budget_limited,
        reason=reason,
    )
