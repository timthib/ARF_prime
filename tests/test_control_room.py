import json
import sqlite3
import threading
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

from monitor.fixture import build_demo
from monitor.gateway import NOT_API, NOT_INSTALLED, execute, list_commands
from monitor.metrics import area
from monitor.queries import (
    design_lamp,
    find_run,
    pilot_report_payload,
    repo_root,
    shape_framework,
    shape_run,
    shape_step,
)
from monitor.server import make_server


def test_area_of_a_step_curve():
    assert area([(0.5, 1.0)], 1.0) == pytest.approx(0.5)
    assert area([(0.25, 0.4), (1.0, 0.4)], 1.0) == pytest.approx(0.3)


def test_demo_meta_loop_has_past_live_and_future(tmp_path):
    build_demo(tmp_path)
    data = find_run(tmp_path, "loop-arm6-r1")
    run = shape_run(data)
    assert [slot["k"] for slot in run["steps"]] == list(range(1, 21))
    assert sum(slot["slot"] == "live" for slot in run["steps"]) == 1
    assert sum(slot["slot"] == "future" for slot in run["steps"]) == 13
    rejected = next(slot for slot in run["steps"] if slot["k"] == 3)
    assert rejected["status"] == "rejected"
    assert rejected["gpu_h"] == 0
    assert rejected["tokens"] == 0
    assert run["strip"]["leading_framework_id"] == "v5"
    assert run["strip"]["K"] == 20
    future = shape_step(data, 12)
    assert future["slot"] == "future"
    assert future["budget_gpu_h"] == 0.75
    framework = shape_framework(data, "v5")
    seed = next(item for item in framework["seeds"] if item["seed"] == 101)
    scores = [point["s"] for point in seed["curve"]]
    assert scores != sorted(scores)
    killed = shape_framework(data, "v6")
    carried = next(item for item in killed["seeds"] if item["seed"] == 103)
    assert carried["curve"][-1]["carried"] is True
    assert carried["curve"][-1]["b"] == pytest.approx(0.25)


def test_framework_cards_expose_the_decision_record(tmp_path):
    build_demo(tmp_path)
    data = find_run(tmp_path, "loop-arm6-r1")
    run = shape_run(data)
    leader = next(card for card in run["cards"] if card["leading"])
    assert leader["framework_id"] == "v5"
    assert leader["j_sel"] is not None
    assert leader["n_models"] == 15
    assert leader["best_u"] is not None
    assert run["incumbent_check"]["elected_framework_id"] == "v5"
    assert any(note["level"] == "bad" for note in run["attention"])
    framework = shape_framework(data, "v5")
    assert framework["j_sel_median"] == leader["j_sel"]
    seed = next(item for item in framework["seeds"] if item["seed"] == 101)
    assert seed["models"][0]["family"] == "ridge"
    assert [point["model_id"].rsplit("-", 1)[-1] for point in seed["best_u"]] == ["m1", "m3", "m4", "m5"]
    step = shape_step(data, 5)
    assert step["frameworks"][0]["framework_id"] == "v5"
    assert step["sequence"][0]["state"] == "done"


def test_overfit_is_u_up_and_s_sel_down(tmp_path):
    build_demo(tmp_path)
    data = find_run(tmp_path, "loop-arm6-r1")
    framework = shape_framework(data, "v5")
    seed = next(item for item in framework["seeds"] if item["seed"] == 101)
    assert [model["label"] for model in seed["models"]] == ["model1", "model2", "model3", "model4", "model5"]
    assert seed["overfit"]["n_overfit"] == 1
    event = next(item for item in seed["overfit"]["events"] if item["overfit"])
    assert event["from_label"] == "model1"
    assert event["to_label"] == "model3"
    assert event["du"] > 0
    assert event["ds"] < 0
    assert seed["models"][2]["overfit"] is True
    assert "beats incumbent model1" in seed["models"][2]["thinking"]["why"]
    step = shape_step(data, 5)
    assert step["l0_thinking"]["what"]
    assert step["l0_thinking"]["how"]
    assert step["l0_thinking"]["why"]
    assert step["frameworks"][0]["model_seeds"][0]["models"][0]["label"] == "model1"
    rejected = shape_step(data, 3)
    assert "budget counter" in rejected["l0_thinking"]["what"]


def test_pilot_curve_matches_the_stored_rule(tmp_path):
    build_demo(tmp_path)
    pilot = shape_run(find_run(tmp_path, "pilot-arm6-r1"))
    medians = [slot["j_sel_median"] for slot in pilot["steps"]]
    assert medians == pytest.approx([0.40, 0.50, 0.56, 0.62, 0.68])
    report = pilot_report_payload(tmp_path, repo_root())
    assert report["k_rule"] == 17
    assert report["experiment_k"] == 20
    assert "K" not in report


def test_split_check_rejects_anything_but_sel(tmp_path):
    build_demo(tmp_path)
    connection = sqlite3.connect(tmp_path / "loop-arm6-r1" / "monitor.db")
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """INSERT INTO eval_event
               (meta_run_id, ts, design_hash, run_id, model_id, b, split, s)
               VALUES ('x', 't', 'd', 'r', 'm', 0.1, 'd0', 0.2)"""
        )


def test_design_banner_after_a_look():
    lamp = design_lamp(
        {
            "changed_after_d0_view": 1,
            "design_version": 2,
            "last_d0_look_ts": "2026-01-01T00:00:00Z",
            "design_ok": 1,
        }
    )
    assert lamp["text"] == "design v2, changed after D0 view at 2026-01-01T00:00:00Z"
    assert lamp["level"] == "bad"


def test_gateway_refuses_unknown_and_uninstalled(tmp_path):
    for verb in ("stop", "extend", "set_K", "set_k", "set_budget", "elect"):
        result = execute(tmp_path, verb, {"s0": 1})
        assert result["status"] == "refused"
        assert result["event_id"] is None
        assert result["reason"] == NOT_API
        assert set(result) == {"status", "event_id", "reason", "verb"}
    assert not (tmp_path / "commands.jsonl").exists()
    missing = execute(tmp_path, "freeze", {})
    assert missing["reason"] == NOT_INSTALLED
    assert all(item["available"] is False for item in list_commands())


def test_gateway_strips_holdout_fields(tmp_path, monkeypatch):
    seen = {}

    def evil(payload):
        seen.update(payload)
        return {"s0": 1, "j0": 2, "status": "accepted"}

    monkeypatch.setattr("monitor.gateway.resolve_command", lambda verb: evil)
    refused = execute(tmp_path, "kill_framework", {"meta_run_id": "run", "framework_id": "v1", "s0": 4})
    assert refused["status"] == "refused"
    assert "reason" in refused["reason"]
    accepted = execute(tmp_path, "bump", {"reason": "calibrate B", "s0": 9, "j0": 3})
    assert accepted["status"] == "accepted"
    assert set(accepted) == {"status", "event_id", "reason", "verb"}
    assert "s0" not in seen and "j0" not in seen
    line = json.loads((tmp_path / "commands.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert "s0" not in line and "j0" not in line
    assert line["args"] == {"reason": "calibrate B"}


def test_http_api_has_no_holdout_fields(tmp_path):
    build_demo(tmp_path)
    server = make_server("127.0.0.1", 0, tmp_path, repo_root())
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    try:
        chunks = []
        for path in (
            "/api/study",
            "/api/runs/loop-arm6-r1",
            "/api/runs/loop-arm6-r1/steps/5",
            "/api/runs/loop-arm6-r1/frameworks/v5",
            "/api/commands",
            "/api/pilot-report",
        ):
            with urlopen(f"http://127.0.0.1:{port}{path}") as response:
                assert response.status == 200
                chunks.append(response.read().decode("utf-8"))
        joined = "\n".join(chunks)
        for banned in ('"s0"', '"j0"', "demo-hmac", "d0_results", "d0vault"):
            assert banned not in joined
        try:
            urlopen(f"http://127.0.0.1:{port}/api/export")
            raise AssertionError("export should not exist")
        except HTTPError as exc:
            assert exc.code == 404
    finally:
        server.shutdown()
