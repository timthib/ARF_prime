from pathlib import Path

from smoke.decide_k import decide_k


def test_worked_examples():
    slow = decide_k([0.10, 0.20, 0.22, 0.24, 0.26], 0.0)
    assert slow.k_gain == 10
    assert slow.k == 15
    assert slow.budget_limited is False

    mid = decide_k([0.40, 0.50, 0.56, 0.62, 0.68], 0.0)
    assert mid.k_gain == 17
    assert mid.k == 17

    fast = decide_k([0.10, 0.20, 0.30, 0.40, 0.50], 0.0)
    assert fast.k_gain == 20
    assert fast.k == 20


def test_flat_curve_clips_to_k_lo():
    decision = decide_k([0.2, 0.2, 0.2, 0.2, 0.2], 0.0)
    assert decision.k_gain == 5
    assert decision.k == 15
    assert decision.budget_limited is False


def test_budget_cap_below_the_window():
    decision = decide_k([0.40, 0.50, 0.56, 0.62, 0.68], 0.0, b_cap_gpu=10)
    assert decision.k_budget == 13
    assert decision.k == 13
    assert decision.budget_limited is True
    assert decision.reason == "budget-limited, below target window"


def test_seed_noise_can_floor_the_gain():
    decision = decide_k([0.40, 0.50, 0.56, 0.62, 0.68], sigma_seed=0.2)
    assert decision.tau == 0.1
    assert decision.k == 15


def test_rule_module_has_no_io():
    source = Path(__file__).resolve().parents[1].joinpath("smoke", "decide_k.py").read_text(encoding="utf-8")
    assert "open(" not in source
    assert "sqlite" not in source
    assert "fake_d0" not in source
    assert "d0_results" not in source
