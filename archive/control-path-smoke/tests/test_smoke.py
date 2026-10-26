import json
import sqlite3
from pathlib import Path

import pytest

from smoke.loop import run_loop
from smoke.materialise import CANARY, materialise
from smoke.public_store import append_event
from smoke.run import execute
from smoke.vault_scorer import score


def test_three_step_run_keeps_the_vault_out_of_the_public_log(tmp_path: Path):
    summary = execute(tmp_path, steps=3, n=800, run_id="smoke-at01")
    run_dir = tmp_path / "smoke-at01"
    assert summary["phase"] == "smoke"
    assert summary["steps"] == 3
    assert summary["decision"] is None
    assert summary["leak_check"] == "pass"
    assert summary["excluded_from_main_analysis"] is True
    assert summary["scorer"] == "not_run"

    events = (run_dir / "public" / "events.jsonl").read_text(encoding="utf-8")
    assert events.count('"type": "meta_step"') == 3
    assert "d0" not in events.lower()
    assert CANARY not in events

    connection = sqlite3.connect(run_dir / "public" / "monitor.db")
    try:
        steps = connection.execute("SELECT COUNT(*) FROM meta_step").fetchone()[0]
        splits = {row[0] for row in connection.execute("SELECT DISTINCT split FROM eval_event")}
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        connection.close()
    assert steps == 3
    assert splits == {"sel"}
    assert tables == {"meta_step", "eval_event", "log_line"}
    assert (run_dir / "vault" / "canary.txt").read_text(encoding="utf-8").strip() == CANARY
    assert not (run_dir / "public" / "monitor.db").read_bytes().__contains__(CANARY.encode())


def test_loop_source_is_not_given_the_vault():
    source = Path(__file__).resolve().parents[1].joinpath("smoke", "loop.py").read_text(encoding="utf-8")
    assert "vault_scorer" not in source
    assert "fake_d0" not in source
    assert "materialise" not in source
    assert CANARY not in source


def test_scorer_crash_leaves_the_public_run_intact(tmp_path: Path):
    run_dir = tmp_path / "smoke-crash"
    materialise(run_dir, n=800)
    summary = run_loop(
        run_dir / "public",
        run_dir / "drop",
        run_id="smoke-crash",
        j_sel=[[0.2], [0.3], [0.4]],
        seeds=[91001],
    )
    public_before = (run_dir / "public" / "events.jsonl").read_text(encoding="utf-8")
    with pytest.raises(RuntimeError):
        score(run_dir, fail=True)
    assert (run_dir / "public" / "events.jsonl").read_text(encoding="utf-8") == public_before
    assert not (run_dir / "vault" / "d0_results.sqlite").exists()
    assert summary["steps"] == 3

    assert score(run_dir) == 3
    assert score(run_dir) == 3
    vault_db = run_dir / "vault" / "d0_results.sqlite"
    public_blob = b"".join(path.read_bytes() for path in (run_dir / "public").rglob("*") if path.is_file())
    assert b"s0" not in public_blob
    assert CANARY.encode() not in public_blob
    connection = sqlite3.connect(vault_db)
    try:
        stored = connection.execute("SELECT s0 FROM d0_score").fetchone()[0]
    finally:
        connection.close()
    assert f"{stored:.8f}".encode() not in public_blob


def test_public_store_rejects_a_vault_split(tmp_path: Path):
    events = tmp_path / "events.jsonl"
    with pytest.raises(ValueError):
        append_event(
            events,
            {
                "type": "eval_event",
                "ts": "2026-01-01T00:00:00Z",
                "design_hash": "smoke-dev",
                "phase": "smoke",
                "run_id": "r",
                "k": 1,
                "seed": 91001,
                "b": 1.0,
                "split": "d0",
                "s": 0.1,
            },
        )


def test_five_step_fixture_reports_the_worked_example(tmp_path: Path):
    summary = execute(tmp_path, steps=5, n=800, run_id="smoke-k")
    assert summary["curve_source"] == "fixture"
    assert summary["decision"]["k"] == 17
    assert summary["K"] == 20
    assert summary["K_min"] == 20
    assert summary["K_max"] == 20
    assert summary["seeds"] == [91001]
    report = json.loads((tmp_path / "smoke-k" / "public" / "smoke_report.json").read_text(encoding="utf-8"))
    assert report["leak_check"] == "pass"
    assert "s0" not in report
