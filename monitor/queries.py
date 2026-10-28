"""Read model for the control room. Every figure comes from monitor.db."""

from __future__ import annotations

import json
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from monitor.metrics import area, median

ARMS = (
    (1, "Fixed AIDE"),
    (2, "Random search"),
    (3, "Hyperband / BOHB"),
    (4, "ADAS-style"),
    (5, "L0 linear"),
    (6, "L0 tree"),
)

ABLATIONS = (
    ("i", "Mutable rules off"),
    ("ii", "L0 self-modification off"),
    ("iii", "Parent score CMP"),
    ("iv", "fixed_default split"),
)

FINISHED = ("complete", "killed")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def stored_horizon(repo: Path) -> int:
    path = repo / "configs" / "experiment.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    return int(payload["K"])


def parse_ts(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def design_lamp(header: dict) -> dict:
    if header.get("changed_after_d0_view"):
        version = header.get("design_version")
        seen = header.get("last_d0_look_ts") or ""
        return {
            "level": "bad",
            "text": f"design v{version}, changed after D0 view at {seen}",
        }
    if not header.get("design_ok", 1):
        return {"level": "bad", "text": "design hash changed"}
    return {"level": "ok", "text": "design hash matches"}


def _connect(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _rows(connection: sqlite3.Connection, sql: str) -> list[dict]:
    return [dict(row) for row in connection.execute(sql)]


def read_db(db_path: Path) -> dict:
    connection = _connect(db_path)
    try:
        headers = _rows(connection, "SELECT * FROM run_header")
        if len(headers) != 1:
            raise ValueError(f"{db_path} should contain one run header")
        return {
            "header": headers[0],
            "steps": _rows(connection, "SELECT * FROM meta_step ORDER BY k"),
            "l1": _rows(connection, "SELECT * FROM l1_run ORDER BY seed"),
            "frameworks": _rows(connection, "SELECT * FROM framework ORDER BY k_first"),
            "models": _rows(connection, "SELECT * FROM model ORDER BY seq"),
            "evals": _rows(
                connection,
                "SELECT run_id, model_id, b, s, e_mae, trigger FROM eval_event ORDER BY b",
            ),
            "logs": _rows(
                connection,
                "SELECT ts, run_id, k, role, model_id, message FROM log_line ORDER BY ts",
            ),
            "kills": _rows(
                connection,
                "SELECT ts, run_id, framework_id, k, reason FROM kill_event ORDER BY ts",
            ),
            "gpus": _rows(
                connection,
                "SELECT run_id, k, model_id, b, gpu_busy FROM gpu_sample ORDER BY b",
            ),
            "outbox_depth": connection.execute("SELECT COUNT(*) FROM d0_outbox").fetchone()[0],
        }
    finally:
        connection.close()


def run_directories(root: Path) -> list[Path]:
    index = root / "index.json"
    if index.exists():
        listed = json.loads(index.read_text(encoding="utf-8"))
        return [root / item["dir"] for item in listed]
    found = sorted(path.parent for path in root.glob("*/events.jsonl"))
    return found


def load_runs(root: Path) -> list[dict]:
    loaded = []
    for directory in run_directories(root):
        database = directory / "monitor.db"
        events = directory / "events.jsonl"
        if events.exists() and (not database.exists() or database.stat().st_mtime < events.stat().st_mtime):
            from monitor.ingest import ingest

            ingest(events, database)
        if database.exists():
            loaded.append(read_db(database))
    return loaded


def _json_object(text: str | None) -> dict:
    if not text:
        return {}
    value = json.loads(text)
    return value if isinstance(value, dict) else {}


def _thinking(raw) -> dict | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, dict):
        parsed = raw
    else:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {"what": str(raw), "how": "", "why": ""}
    if not isinstance(parsed, dict):
        return {"what": str(parsed), "how": "", "why": ""}
    return {
        "what": str(parsed.get("what") or ""),
        "how": str(parsed.get("how") or ""),
        "why": str(parsed.get("why") or ""),
    }


def _model_label(seq: int) -> str:
    return f"model{int(seq)}"


def _display_curve(points: list[dict], end_b: float, carried: bool) -> list[dict]:
    shown = [
        {
            "b": point["b"],
            "s": point["s"],
            "model_id": point["model_id"],
            "carried": False,
        }
        for point in points
    ]
    if points and end_b > points[-1]["b"] + 1e-9:
        shown.append(
            {
                "b": end_b,
                "s": points[-1]["s"],
                "model_id": points[-1]["model_id"],
                "carried": carried,
            }
        )
    elif carried and not points:
        shown.append({"b": end_b, "s": 0.0, "model_id": None, "carried": True})
    return shown


def _seed_curve(data: dict, run: dict) -> dict:
    points = [row for row in data["evals"] if row["run_id"] == run["run_id"]]
    points.sort(key=lambda row: (row["b"], row["model_id"]))
    budget = float(data["header"]["b_gpu"])
    stopped = run["status"] in FINISHED
    used = float(run["gpu_h_used"] or 0.0)
    end = budget if stopped else used
    raw = [(point["b"], point["s"]) for point in points]
    value = area(raw, end) if end > 0 else 0.0
    carried = stopped and (not points or points[-1]["b"] < budget - 1e-9)
    curve = _display_curve(points, budget if carried else end, carried)
    return {
        "area": value if stopped else None,
        "curve": curve,
        "carried": carried,
    }


def _framework_map(data: dict) -> dict[str, dict]:
    return {row["framework_id"]: row for row in data["frameworks"]}


def _runs_for(data: dict, framework_id: str) -> list[dict]:
    rows = [row for row in data["l1"] if row["framework_id"] == framework_id]
    return sorted(rows, key=lambda row: row["seed"])


def _areas(data: dict, framework_id: str) -> list[tuple[dict, dict]]:
    paired = []
    for run in _runs_for(data, framework_id):
        paired.append((run, _seed_curve(data, run)))
    return paired


def _finished_median(data: dict, framework: dict) -> float | None:
    if any(run["status"] not in FINISHED for run in _runs_for(data, framework["framework_id"])):
        return None
    values = [curve["area"] for _run, curve in _areas(data, framework["framework_id"])]
    values = [value for value in values if value is not None]
    if not values:
        return None
    return median(values)


def _gpu_cost(data: dict, framework_id: str) -> float:
    return sum(float(run["gpu_h_used"] or 0.0) for run in _runs_for(data, framework_id))


def _leading(data: dict) -> dict | None:
    ranked = []
    for framework in data["frameworks"]:
        score = _finished_median(data, framework)
        if score is None:
            continue
        ranked.append((score, _gpu_cost(data, framework["framework_id"]), framework["k_first"], framework))
    if not ranked:
        return None
    ranked.sort(key=lambda item: (-item[0], item[1], item[2]))
    return ranked[0][3]


def _elapsed(data: dict) -> float:
    starts = [parse_ts(step["t_start"]) for step in data["steps"] if step["t_start"]]
    if not starts:
        return 0.0
    return (parse_ts(data["header"]["as_of"]) - min(starts)).total_seconds()


def _current_k(data: dict) -> int:
    running = [step["k"] for step in data["steps"] if step["status"] == "running"]
    if running:
        return min(running)
    if data["steps"]:
        return max(step["k"] for step in data["steps"])
    return 0


def shape_strip(data: dict) -> dict:
    header = data["header"]
    horizon = int(header["k_horizon"])
    leader = _leading(data)
    elected = next((row for row in data["frameworks"] if row["elected"]), None)
    running = any(step["status"] == "running" for step in data["steps"])
    band = [8, 13] if header["phase"] == "loop" and horizon == 20 else None
    score = None if leader is None else _finished_median(data, leader)
    return {
        "meta_run_id": header["meta_run_id"],
        "k": _current_k(data),
        "K": horizon,
        "phase": header["phase"],
        "arm": header["arm"],
        "arm_name": header["arm_name"],
        "replicate": header["replicate"],
        "gpu_h_used": round(sum(float(step["spent_gpu_h"] or 0.0) for step in data["steps"]), 6),
        "gpu_h_cap": horizon * float(header["b_step_gpu"]),
        "tokens_used": int(sum(int(step["spent_tokens"] or 0) for step in data["steps"])),
        "tokens_cap": int(horizon * float(header["b_step_tokens"])),
        "elapsed_s": _elapsed(data),
        "wall_band_h": band,
        "leading_j_sel": score,
        "leading_framework_id": None if leader is None else leader["framework_id"],
        "elected": elected is not None,
        "running": running,
        "design_hash": header["design_hash"],
        "design_version": header["design_version"],
        "lamp": design_lamp(header),
        "scorer": {
            "state": header["scorer_state"],
            "outbox_depth": int(data["outbox_depth"]),
        },
        "as_of": header["as_of"],
    }


def _spark_of(curve: dict) -> list[dict]:
    return [{"b": point["b"], "s": point["s"]} for point in curve["curve"]]


def _step_slots(data: dict) -> list[dict]:
    header = data["header"]
    by_k = {step["k"]: step for step in data["steps"]}
    frameworks = _framework_map(data)
    by_step = {}
    for framework in data["frameworks"]:
        by_step.setdefault(framework["k_first"], framework)
    parent_score = {}
    for framework in data["frameworks"]:
        parent_score[framework["framework_id"]] = _finished_median(data, framework)
    slots = []
    for k in range(1, int(header["k_horizon"]) + 1):
        step = by_k.get(k)
        budget_gpu = float(header["b_step_gpu"])
        budget_tokens = float(header["b_step_tokens"])
        if step is None:
            slots.append(
                {
                    "k": k,
                    "slot": "future",
                    "status": None,
                    "hypothesis": "",
                    "l0_thinking": None,
                    "tamper_reason": None,
                    "framework_id": None,
                    "parent_framework_id": None,
                    "j_sel_median": None,
                    "seeds": [],
                    "gpu_h": None,
                    "tokens": None,
                    "duration_s": None,
                    "n_kills": 0,
                    "budget_gpu_h": budget_gpu,
                    "budget_tokens": budget_tokens,
                    "sparkline": [],
                    "confirmed": None,
                    "progress": [],
                    "last_log": None,
                }
            )
            continue
        framework = by_step.get(k)
        live = step["status"] == "running"
        areas: list[float] = []
        sparkline: list[dict] = []
        progress = []
        if framework is not None:
            paired = _areas(data, framework["framework_id"])
            if not live:
                areas = [curve["area"] for _run, curve in paired]
            spark_source = paired[len(paired) // 2][1] if paired else None
            if spark_source is not None:
                sparkline = _spark_of(spark_source)
            for run, curve in paired:
                progress.append(
                    {
                        "seed": run["seed"],
                        "b": run["gpu_h_used"],
                        "B": header["b_gpu"],
                        "status": run["status"],
                        "run_id": run["run_id"],
                    }
                )
        start = parse_ts(step["t_start"]) if step["t_start"] else None
        if step["t_end"]:
            duration = (parse_ts(step["t_end"]) - start).total_seconds()
        elif start is not None:
            duration = (parse_ts(header["as_of"]) - start).total_seconds()
        else:
            duration = None
        score = None if framework is None else parent_score.get(framework["framework_id"])
        confirmed = None
        if framework is not None and framework["parent_framework_id"] and score is not None:
            parent = parent_score.get(framework["parent_framework_id"])
            if parent is not None:
                confirmed = score > parent
        logs = [row for row in data["logs"] if row["k"] == k]
        slots.append(
            {
                "k": k,
                "slot": "live" if live else "done",
                "status": step["status"],
                "hypothesis": step["hypothesis_text"] or "",
                "l0_thinking": _thinking(step.get("l0_thinking")),
                "tamper_reason": step["tamper_reason"],
                "framework_id": None if framework is None else framework["framework_id"],
                "parent_framework_id": step["parent_framework_id"],
                "j_sel_median": score,
                "seeds": areas,
                "gpu_h": step["spent_gpu_h"],
                "tokens": step["spent_tokens"],
                "duration_s": duration,
                "n_kills": sum(1 for row in data["kills"] if row["k"] == k),
                "budget_gpu_h": step["budget_gpu_h"],
                "budget_tokens": step["budget_tokens"],
                "sparkline": sparkline,
                "confirmed": confirmed,
                "progress": progress if live else [],
                "last_log": None if not logs else logs[-1]["message"],
            }
        )
    return slots


def _j_series(data: dict, slots: list[dict]) -> list[dict]:
    series = []
    best = None
    for slot in slots:
        if slot["j_sel_median"] is None or slot["framework_id"] is None:
            continue
        score = slot["j_sel_median"]
        best = score if best is None else max(best, score)
        series.append(
            {
                "k": slot["k"],
                "framework_id": slot["framework_id"],
                "median": score,
                "seeds": slot["seeds"],
                "running_max": best,
            }
        )
    return series


def _burn(data: dict, slots: list[dict]) -> list[dict]:
    header = data["header"]
    horizon = int(header["k_horizon"])
    cap_gpu = horizon * float(header["b_step_gpu"])
    cap_tokens = horizon * float(header["b_step_tokens"])
    cum_gpu = 0.0
    cum_tokens = 0
    points = []
    for slot in slots:
        if slot["slot"] == "future":
            continue
        cum_gpu += float(slot["gpu_h"] or 0.0)
        cum_tokens += int(slot["tokens"] or 0)
        points.append(
            {
                "k": slot["k"],
                "cum_gpu_h": round(cum_gpu, 6),
                "cum_tokens": cum_tokens,
                "cap_gpu_h": cap_gpu,
                "cap_tokens": cap_tokens,
            }
        )
    return points


def _wall(slots: list[dict]) -> list[dict]:
    return [
        {"k": slot["k"], "l0_s": None, "l1_s": None}
        for slot in slots
        if slot["slot"] != "future"
    ]


def _fill_wall(data: dict, wall: list[dict]) -> list[dict]:
    by_k = {step["k"]: step for step in data["steps"]}
    filled = []
    for point in wall:
        step = by_k[point["k"]]
        filled.append({"k": point["k"], "l0_s": step["l0_s"] or 0, "l1_s": step["l1_s"] or 0})
    return filled


def _tree(data: dict) -> list[dict]:
    leader = _leading(data)
    leading_id = None if leader is None else leader["framework_id"]
    nodes = []
    for framework in data["frameworks"]:
        nodes.append(
            {
                "framework_id": framework["framework_id"],
                "parent_framework_id": framework["parent_framework_id"],
                "k": framework["k_first"],
                "j_sel_median": _finished_median(data, framework),
                "leading": framework["framework_id"] == leading_id,
            }
        )
    return nodes


def _metric_name(rules: dict) -> str:
    for key in ("metric", "score", "selection_metric"):
        value = rules.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "u"


def _problem_line(message: str) -> bool:
    text = message.lower()
    return any(word in text for word in ("reject", "tamper", "error", "exception", "failed", "traceback"))


def _logs(data: dict) -> list[dict]:
    framework_of = {row["run_id"]: row["framework_id"] for row in data["l1"]}
    lines = []
    for row in data["logs"]:
        message = row["message"] or ""
        lines.append(
            {
                "ts": row["ts"],
                "k": row["k"],
                "role": row["role"],
                "run_id": row["run_id"],
                "model_id": row["model_id"],
                "framework_id": framework_of.get(row["run_id"]),
                "message": message,
                "level": "problem" if _problem_line(message) else "info",
            }
        )
    return lines


def _run_span_s(data: dict, run_id: str) -> float | None:
    stamps = [parse_ts(row["ts"]) for row in data["logs"] if row["run_id"] == run_id]
    if len(stamps) < 2:
        return None
    return (max(stamps) - min(stamps)).total_seconds()


def _final_incumbent(data: dict, run: dict, curve: dict) -> tuple[float | None, float | None]:
    real = [point for point in curve["curve"] if not point.get("carried")]
    if not real:
        return None, None
    last = real[-1]
    model = next((row for row in data["models"] if row["model_id"] == last["model_id"]), None)
    score_u = None if model is None else model["u"]
    return score_u, last["s"]


def _framework_card(data: dict, framework: dict, index: int, leading_id: str | None) -> dict:
    framework_id = framework["framework_id"]
    paired = _areas(data, framework_id)
    finished = bool(paired) and all(run["status"] in FINISHED for run, _curve in paired)
    areas = [curve["area"] for _run, curve in paired if curve["area"] is not None]
    j_sel = median(areas) if finished and areas else None
    models = [row for row in data["models"] if row["framework_id"] == framework_id]
    scores_u = [row["u"] for row in models if row["u"] is not None]
    gaps = []
    finals = []
    seed_line = []
    gpu_alloc = 0.0
    tokens = 0
    span = 0.0
    any_span = False
    for run, curve in paired:
        gpu_alloc += float(run["alloc_gpu_h"] or 0.0)
        tokens += int(run["tokens_used"] or 0)
        seconds = _run_span_s(data, run["run_id"])
        if seconds is not None:
            span += seconds
            any_span = True
        score_u, score_s = _final_incumbent(data, run, curve)
        if score_s is not None:
            finals.append(score_s)
        if score_u is not None and score_s is not None:
            gaps.append(float(score_u) - float(score_s))
        seed_line.append(
            {
                "seed": run["seed"],
                "status": run["status"],
                "area": curve["area"],
                "gpu_h_used": run["gpu_h_used"],
                "alloc_gpu_h": run["alloc_gpu_h"],
                "run_id": run["run_id"],
            }
        )
    if any(seed["status"] == "running" for seed in seed_line):
        status = "running"
    elif any(seed["status"] == "killed" for seed in seed_line):
        status = "killed"
    elif seed_line and all(seed["status"] == "complete" for seed in seed_line):
        status = "complete"
    elif seed_line:
        status = "partial"
    else:
        status = "pending"
    rules = _json_object(framework["rules_json"])
    overfit = _card_overfit(data, framework_id)
    return {
        "index": index,
        "framework_id": framework_id,
        "k": framework["k_first"],
        "parent_framework_id": framework["parent_framework_id"],
        "hypothesis": framework["hypothesis_text"] or "",
        "n_models": len(models),
        "best_u": None if not scores_u else max(scores_u),
        "metric": _metric_name(rules),
        "gpu_h": round(_gpu_cost(data, framework_id), 6),
        "gpu_alloc": round(gpu_alloc, 6),
        "tokens": tokens,
        "span_s": None if not any_span else span,
        "j_sel": j_sel,
        "s_final": median(finals) if finished and finals else None,
        "gap": median(gaps) if finished and gaps else None,
        "spread": overfit["spread"],
        "overfit_steps": overfit["overfit_steps"],
        "selection_loss": overfit["selection_loss"],
        "seeds_done": sum(1 for seed in seed_line if seed["status"] in FINISHED),
        "seeds_total": len(seed_line),
        "status": status,
        "leading": framework_id == leading_id,
        "elected": bool(framework["elected"]),
        "n_killed": framework["n_killed"],
        "seed_line": seed_line,
        "killable": False,
    }


def _framework_cards(data: dict) -> list[dict]:
    leader = _leading(data)
    leading_id = None if leader is None else leader["framework_id"]
    ordered = sorted(data["frameworks"], key=lambda row: (row["k_first"], row["framework_id"]))
    return [
        _framework_card(data, framework, index, leading_id)
        for index, framework in enumerate(ordered, start=1)
    ]


def _cloud(cards: list[dict]) -> list[dict]:
    return [
        {
            "index": card["index"],
            "framework_id": card["framework_id"],
            "k": card["k"],
            "j_sel": card["j_sel"],
            "leading": card["leading"],
            "status": card["status"],
        }
        for card in cards
    ]


def _incumbent_check(cards: list[dict]) -> dict:
    points = [
        {
            "index": card["index"],
            "framework_id": card["framework_id"],
            "s_final": card["s_final"],
            "j_sel": card["j_sel"],
            "leading": card["leading"],
        }
        for card in cards
        if card["s_final"] is not None
    ]
    elected = next((card for card in cards if card["leading"]), None)
    verdict = "J_sel is not available until a framework finishes its seeds."
    elected_id = None
    best_id = None
    if elected is not None and elected["s_final"] is not None and points:
        elected_id = elected["framework_id"]
        best = max(points, key=lambda point: (point["s_final"], -point["index"]))
        best_id = best["framework_id"]
        if best_id == elected_id:
            verdict = (
                f"{elected_id} has the best J_sel and the highest final incumbent score on D1_sel."
            )
        else:
            verdict = (
                f"J_sel elects {elected_id}. "
                f"The highest final incumbent score on D1_sel belongs to {best_id}."
            )
    return {
        "points": points,
        "elected_framework_id": elected_id,
        "best_s_framework_id": best_id,
        "verdict": verdict,
    }


def _note(level: str, text: str, k, framework_id, scope: str) -> dict:
    return {"level": level, "text": text, "k": k, "framework_id": framework_id, "scope": scope}


def _attention(data: dict, cards: list[dict]) -> list[dict]:
    header = data["header"]
    notes = []
    live_k = next((step["k"] for step in data["steps"] if step["status"] == "running"), None)
    lamp = design_lamp(header)
    if lamp["level"] == "bad":
        notes.append(_note("bad", lamp["text"], None, None, "now"))
    if header["scorer_state"] == "stuck":
        notes.append(_note("bad", "The D0 scorer is stuck. The outbox is not moving.", None, None, "now"))
    elif header["phase"] == "loop" and header["scorer_state"] == "stopped" and int(data["outbox_depth"]) > 0:
        notes.append(
            _note(
                "watch",
                (
                    f"The D0 scorer is stopped with {int(data['outbox_depth'])} artifacts waiting. "
                    "Those scores stay on this dashboard."
                ),
                None,
                None,
                "now",
            )
        )
    running_steps = [step for step in data["steps"] if step["status"] == "running"]
    if data["steps"] and not running_steps and _current_k(data) < int(header["k_horizon"]):
        notes.append(
            _note(
                "bad",
                f"Nothing is running. The meta-run stopped at step {_current_k(data)}.",
                _current_k(data),
                None,
                "now",
            )
        )
    if live_k is not None:
        live = [run for run in data["l1"] if run["k"] == live_k and run["status"] == "running"]
        seeds = sorted({run["seed"] for run in live})
        if len(seeds) > 1:
            listed = ", ".join(str(seed) for seed in seeds)
            notes.append(
                _note(
                    "watch",
                    (
                        f"Seeds {listed} are running in step {live_k}. "
                        "The procedure runs one seed at a time and does not feed results back between seeds."
                    ),
                    live_k,
                    None,
                    "now",
                )
            )
    for step in data["steps"]:
        if step["status"] != "rejected":
            continue
        scope = "now" if step["k"] == live_k else "record"
        notes.append(_note("bad", step["tamper_reason"] or "The core rejected the edit.", step["k"], None, scope))
    for row in data["kills"]:
        scope = "now" if row["k"] == live_k else "record"
        notes.append(_note("bad", row["reason"], row["k"], row["framework_id"], scope))
    for card in cards:
        if card["overfit_steps"]:
            count = card["overfit_steps"]
            word = "change" if count == 1 else "changes"
            notes.append(
                _note(
                    "watch",
                    f"{card['framework_id']} has {count} incumbent {word} where u rose and S_sel fell.",
                    card["k"],
                    card["framework_id"],
                    "record",
                )
            )
    return notes


def _now(data: dict) -> dict:
    header = data["header"]
    k = _current_k(data)
    running = []
    for run in data["l1"]:
        if run["k"] != k or run["status"] != "running":
            continue
        logs = [row for row in data["logs"] if row["run_id"] == run["run_id"]]
        last = logs[-1] if logs else None
        running.append(
            {
                "framework_id": run["framework_id"],
                "seed": run["seed"],
                "run_id": run["run_id"],
                "b": run["gpu_h_used"],
                "B": header["b_gpu"],
                "last_log": None if last is None else last["message"],
                "model_id": None if last is None else last["model_id"],
            }
        )
    running.sort(key=lambda row: (row["seed"], row["framework_id"]))
    return {"k": k, "running": running}


def _journey(data: dict, cards: list[dict]) -> list[dict]:
    header = data["header"]
    horizon = int(header["k_horizon"])
    k = _current_k(data)
    running = any(step["status"] == "running" for step in data["steps"])
    frozen = int(header["design_version"]) >= 1
    scorer = header["scorer_state"]
    if scorer == "stuck":
        scorer_state = "problem"
    elif scorer == "polling":
        scorer_state = "running"
    else:
        scorer_state = "waiting"
    if not data["steps"]:
        loop_state = "waiting"
    elif running:
        loop_state = "running"
    elif k >= horizon:
        loop_state = "done"
    else:
        loop_state = "problem"
    elected_row = next((row for row in data["frameworks"] if row["elected"]), None)
    leader = next((card for card in cards if card["leading"]), None)
    if elected_row is not None or (not running and k >= horizon and leader is not None):
        elect_state = "done"
    elif leader is not None:
        elect_state = "running"
    else:
        elect_state = "waiting"
    elect_detail = "The core has not closed the election."
    if elected_row is not None:
        elect_detail = f"Core flag on {elected_row['framework_id']}."
    elif leader is not None:
        elect_detail = f"Best J_sel so far is {leader['framework_id']}."
    production = [run for run in data["l1"] if run["phase"] == "production"]
    if any(run["status"] == "running" for run in production):
        phase2_state = "running"
    elif any(run["status"] in FINISHED for run in production):
        phase2_state = "done"
    else:
        phase2_state = "waiting"
    return [
        {
            "id": "freeze",
            "label": "Freeze",
            "state": "done" if frozen else "waiting",
            "detail": header["design_hash"] if frozen else "Design version is still 0.",
        },
        {
            "id": "scorer",
            "label": "D0 scorer",
            "state": scorer_state,
            "detail": f"{scorer} · outbox {int(data['outbox_depth'])}",
        },
        {
            "id": "loop",
            "label": f"Meta-step {k} / {horizon}",
            "state": loop_state,
            "detail": header["phase"],
        },
        {
            "id": "elect",
            "label": "Elect by J_sel",
            "state": elect_state,
            "detail": elect_detail,
        },
        {
            "id": "phase2",
            "label": "Phase 2",
            "state": phase2_state,
            "detail": "Elected framework alone, one fresh seed.",
        },
        {
            "id": "rank",
            "label": "Ranking test",
            "state": "waiting",
            "detail": "After step K, on the D0 pane.",
        },
    ]


def _step_sequence(data: dict, k: int, slot: dict) -> list[dict]:
    if slot["slot"] == "future":
        return [
            {"id": "prepare", "label": "1. L0 prepares the frameworks", "state": "waiting", "detail": ""},
            {"id": "allocate", "label": "2. L0 splits the step budget", "state": "waiting", "detail": ""},
            {"id": "seeds", "label": "3. Seeds, one after another", "state": "waiting", "detail": ""},
            {"id": "report", "label": "4. J_sel, then L0 kills and elects", "state": "waiting", "detail": ""},
            {"id": "rewrite", "label": "5. L0 rewrites the next step", "state": "waiting", "detail": ""},
        ]
    runs = [run for run in data["l1"] if run["k"] == k]
    rejected = slot["status"] == "rejected"
    prepare = {
        "id": "prepare",
        "label": "1. L0 prepares the frameworks",
        "state": "problem" if rejected else "done",
        "detail": slot["tamper_reason"] or slot["hypothesis"] or "Initial framework.",
    }
    if rejected:
        skipped = "The step is consumed. Nothing is spent."
        return [
            prepare,
            {"id": "allocate", "label": "2. L0 splits the step budget", "state": "skipped", "detail": skipped},
            {"id": "seeds", "label": "3. Seeds, one after another", "state": "skipped", "detail": skipped},
            {"id": "report", "label": "4. J_sel, then L0 kills and elects", "state": "skipped", "detail": skipped},
            {
                "id": "rewrite",
                "label": "5. L0 rewrites the next step",
                "state": "done" if any(step["k"] > k for step in data["steps"]) else "waiting",
                "detail": "A rejected edit still uses the step slot.",
            },
        ]
    if runs:
        allocate_state = "done"
        allocate_detail = f"{len({run['framework_id'] for run in runs})} frameworks, {len(runs)} runs."
    else:
        allocate_state = "running" if slot["status"] == "running" else "waiting"
        allocate_detail = "No L1 run has been recorded."
    seeds = sorted({run["seed"] for run in runs})
    seed_bits = []
    for seed in seeds:
        group = [run for run in runs if run["seed"] == seed]
        if any(run["status"] == "running" for run in group):
            state = "running"
        elif all(run["status"] in FINISHED for run in group):
            state = "done"
        else:
            state = "waiting"
        seed_bits.append(f"{seed} {state}")
    if not seeds:
        seed_state = "waiting"
    elif any(run["status"] == "running" for run in runs):
        seed_state = "running"
    elif all(run["status"] in FINISHED for run in runs):
        seed_state = "done"
    else:
        seed_state = "waiting"
    report_ready = bool(runs) and all(run["status"] in FINISHED for run in runs)
    later = any(step["k"] > k for step in data["steps"])
    return [
        prepare,
        {"id": "allocate", "label": "2. L0 splits the step budget", "state": allocate_state, "detail": allocate_detail},
        {
            "id": "seeds",
            "label": "3. Seeds, one after another",
            "state": seed_state,
            "detail": " · ".join(seed_bits),
        },
        {
            "id": "report",
            "label": "4. J_sel, then L0 kills and elects",
            "state": "done" if report_ready else "waiting",
            "detail": "Median of the seed areas." if report_ready else "Waiting until every seed of this step has finished.",
        },
        {
            "id": "rewrite",
            "label": "5. L0 rewrites the next step",
            "state": "done" if later else "waiting",
            "detail": "The next step is on record." if later else "L0 has not opened the next step.",
        },
    ]


def shape_run(data: dict) -> dict:
    header = data["header"]
    slots = _step_slots(data)
    cards = _framework_cards(data)
    k = _current_k(data)
    live_slot = next((slot for slot in slots if slot["k"] == k), None)
    return {
        "meta_run_id": header["meta_run_id"],
        "arm": header["arm"],
        "arm_name": header["arm_name"],
        "replicate": header["replicate"],
        "phase": header["phase"],
        "topology": header["topology"],
        "strip": shape_strip(data),
        "steps": slots,
        "j_series": _j_series(data, slots),
        "burn": _burn(data, slots),
        "wall": _fill_wall(data, _wall(slots)),
        "tree": _tree(data),
        "cards": cards,
        "cloud": _cloud(cards),
        "incumbent_check": _incumbent_check(cards),
        "attention": _attention(data, cards),
        "now": _now(data),
        "journey": _journey(data, cards),
        "live_sequence": [] if live_slot is None else _step_sequence(data, k, live_slot),
        "logs": _logs(data),
    }


def _family_label(row: dict) -> str:
    family = row.get("family")
    if family:
        return str(family)
    return row.get("operator") or "unspecified"


def _best_u(models: list[dict]) -> list[dict]:
    ordered = sorted(models, key=lambda model: (model["b_created"], model["seq"]))
    best = None
    series = []
    for model in ordered:
        score = model["u"]
        if score is None:
            continue
        if best is None or score > best:
            best = score
            series.append(
                {
                    "b": model["b_created"],
                    "u": score,
                    "model_id": model["model_id"],
                    "label": model.get("label") or _model_label(model["seq"]),
                    "seq": model["seq"],
                    "family": model["family"],
                }
            )
    return series


def _models(data: dict, run: dict) -> list[dict]:
    run_id = run["run_id"]
    incumbents = {row["model_id"] for row in data["evals"] if row["run_id"] == run_id}
    scored: dict[str, dict] = {}
    for row in data["evals"]:
        if row["run_id"] != run_id:
            continue
        previous = scored.get(row["model_id"])
        if previous is None or row["b"] >= previous["b"]:
            scored[row["model_id"]] = row
    spent: dict[str, float] = {}
    for span in _spans(data, run):
        width = float(span["b1"]) - float(span["b0"])
        spent[span["model_id"]] = spent.get(span["model_id"], 0.0) + width
    rows = [row for row in data["models"] if row["run_id"] == run_id]
    children: dict[str, int] = {}
    for row in rows:
        parent = row["parent_model_id"]
        if parent:
            children[parent] = children.get(parent, 0) + 1
    ordered = sorted(rows, key=lambda row: (float(row["b_created"]), row["seq"]))
    produced: dict[str, float] = {}
    previous_b = 0.0
    best_u = None
    current_id = None
    for row in ordered:
        produced[row["model_id"]] = round(max(0.0, float(row["b_created"]) - previous_b), 6)
        previous_b = float(row["b_created"])
        score = row["u"]
        if score is not None and (best_u is None or score > best_u):
            best_u = score
            current_id = row["model_id"]
    models = []
    for row in rows:
        evaluation = scored.get(row["model_id"])
        held = spent.get(row["model_id"], 0.0)
        models.append(
            {
                "model_id": row["model_id"],
                "label": _model_label(row["seq"]),
                "parent_model_id": row["parent_model_id"],
                "operator": row["operator"],
                "family": _family_label(row),
                "u": row["u"],
                "s_sel": None if evaluation is None else evaluation["s"],
                "s_mae": None if evaluation is None else evaluation["e_mae"],
                "b_scored": None if evaluation is None else evaluation["b"],
                "b_created": row["b_created"],
                "gpu_h": produced.get(row["model_id"], round(held, 6)),
                "n_updates": children.get(row["model_id"], 0),
                "status": row["status"],
                "artifact_sha256": row["artifact_sha256"],
                "incumbent": row["model_id"] in incumbents,
                "current": row["model_id"] == current_id,
                "seed": row["seed"],
                "seq": row["seq"],
                "thinking": _thinking(row.get("thinking")),
                "overfit": False,
                "spread": None,
            }
        )
    return models


def _overfit_summary(models: list[dict]) -> dict:
    """Incumbent path. An overfit step is a rise in u together with a fall in S_sel."""
    ordered = sorted(
        (
            model
            for model in models
            if model.get("incumbent") and model.get("u") is not None and model.get("s_sel") is not None
        ),
        key=lambda model: (float(model["b_created"]), model["seq"]),
    )
    events = []
    for previous, nxt in zip(ordered, ordered[1:]):
        du = float(nxt["u"]) - float(previous["u"])
        ds = float(nxt["s_sel"]) - float(previous["s_sel"])
        events.append(
            {
                "from_label": previous["label"],
                "to_label": nxt["label"],
                "from_id": previous["model_id"],
                "to_id": nxt["model_id"],
                "b": nxt["b_created"],
                "u": nxt["u"],
                "s_sel": nxt["s_sel"],
                "du": round(du, 6),
                "ds": round(ds, 6),
                "overfit": du > 1e-9 and ds < -1e-9,
            }
        )
    flagged = {event["to_id"] for event in events if event["overfit"]}
    for model in models:
        model["overfit"] = model["model_id"] in flagged
        if model.get("u") is not None and model.get("s_sel") is not None:
            model["spread"] = round(float(model["u"]) - float(model["s_sel"]), 6)
        else:
            model["spread"] = None
    losses = [-event["ds"] for event in events if event["overfit"]]
    last = ordered[-1] if ordered else None
    return {
        "n_changes": len(events),
        "n_overfit": len(losses),
        "selection_loss": None if not events else round(sum(losses), 6),
        "spread": None if last is None else round(float(last["u"]) - float(last["s_sel"]), 6),
        "events": events,
    }


def _card_overfit(data: dict, framework_id: str) -> dict:
    summaries = []
    for run, _curve in _areas(data, framework_id):
        summaries.append(_overfit_summary(_models(data, run)))
    spreads = [item["spread"] for item in summaries if item["spread"] is not None]
    losses = [item["selection_loss"] for item in summaries if item["selection_loss"] is not None]
    steps = [item["n_overfit"] for item in summaries]
    return {
        "spread": None if not spreads else median(spreads),
        "overfit_steps": 0 if not steps else max(steps),
        "selection_loss": None if not losses else median(losses),
    }


def _model_seeds(data: dict, framework_id: str) -> list[dict]:
    seeds = []
    for run, _curve in _areas(data, framework_id):
        models = _models(data, run)
        seeds.append(
            {
                "seed": run["seed"],
                "status": run["status"],
                "overfit": _overfit_summary(models),
                "models": models,
            }
        )
    return seeds


def _spans(data: dict, run: dict) -> list[dict]:
    samples = [row for row in data["gpus"] if row["run_id"] == run["run_id"]]
    samples.sort(key=lambda row: (row["b"], row["model_id"] or ""))
    end = float(run["gpu_h_used"] or 0.0)
    spans = []
    for index, sample in enumerate(samples):
        nxt = samples[index + 1]["b"] if index + 1 < len(samples) else end
        if nxt > sample["b"]:
            spans.append({"model_id": sample["model_id"], "b0": sample["b"], "b1": nxt})
    return spans


def shape_framework(data: dict, framework_id: str) -> dict | None:
    framework = _framework_map(data).get(framework_id)
    if framework is None:
        return None
    leader = _leading(data)
    seeds = []
    scatter = []
    for run, curve in _areas(data, framework_id):
        models = _models(data, run)
        summary = _overfit_summary(models)
        by_id = {model["model_id"]: model for model in models}
        for point in curve["curve"]:
            named = by_id.get(point["model_id"])
            point["label"] = None if named is None else named["label"]
        eval_keys = {
            (row["model_id"], row["b"])
            for row in data["evals"]
            if row["run_id"] == run["run_id"]
        }
        for point in curve["curve"]:
            model = by_id.get(point["model_id"])
            if model is None or (point["model_id"], point["b"]) not in eval_keys:
                continue
            scatter.append(
                {
                    "model_id": point["model_id"],
                    "label": model["label"],
                    "seed": run["seed"],
                    "u": model["u"],
                    "s_sel": point["s"],
                    "overfit": model["overfit"],
                }
            )
        logs = [
            {"ts": row["ts"], "message": row["message"], "model_id": row["model_id"]}
            for row in data["logs"]
            if row["run_id"] == run["run_id"]
        ]
        gpu = _spans(data, run)
        for span in gpu:
            named = by_id.get(span["model_id"])
            span["label"] = None if named is None else named["label"]
        seeds.append(
            {
                "seed": run["seed"],
                "run_id": run["run_id"],
                "status": run["status"],
                "kill_reason": run["kill_reason"],
                "area": curve["area"],
                "gpu_h_used": run["gpu_h_used"],
                "alloc_gpu_h": run["alloc_gpu_h"],
                "curve": curve["curve"],
                "best_u": _best_u(models),
                "models": models,
                "overfit": summary,
                "gpu": gpu,
                "logs": logs,
            }
        )
    areas = [seed["area"] for seed in seeds if seed["area"] is not None]
    done = bool(seeds) and all(seed["area"] is not None for seed in seeds)
    rules = _json_object(framework["rules_json"])
    card = next((item for item in _framework_cards(data) if item["framework_id"] == framework_id), None)
    return {
        "meta_run_id": data["header"]["meta_run_id"],
        "framework_id": framework_id,
        "parent_framework_id": framework["parent_framework_id"],
        "k": framework["k_first"],
        "hypothesis": framework["hypothesis_text"] or "",
        "l0_thinking": _thinking(
            next((step.get("l0_thinking") for step in data["steps"] if step["k"] == framework["k_first"]), None)
        ),
        "snapshot": framework["level1_snapshot"],
        "rules": rules,
        "metric": _metric_name(rules),
        "edit": _json_object(framework["edit_json"]),
        "j_sel_median": median(areas) if done else None,
        "gap": None if card is None else card["gap"],
        "spread": None if card is None else card["spread"],
        "overfit_steps": 0 if card is None else card["overfit_steps"],
        "selection_loss": None if card is None else card["selection_loss"],
        "s_final": None if card is None else card["s_final"],
        "best_u": None if card is None else card["best_u"],
        "n_models": 0 if card is None else card["n_models"],
        "gpu_h": None if card is None else card["gpu_h"],
        "ci_lo": min(areas) if areas and all(seed["area"] is not None for seed in seeds) else None,
        "ci_hi": max(areas) if areas and all(seed["area"] is not None for seed in seeds) else None,
        "ci_label": "min–max of the seeds",
        "n_killed": framework["n_killed"],
        "B": data["header"]["b_gpu"],
        "leading": leader is not None and leader["framework_id"] == framework_id,
        "strip": shape_strip(data),
        "seeds": seeds,
        "scatter": scatter,
    }


def shape_step(data: dict, k: int) -> dict | None:
    shaped = shape_run(data)
    slot = next((item for item in shaped["steps"] if item["k"] == k), None)
    if slot is None:
        return None
    step_row = next((row for row in data["steps"] if row["k"] == k), None)
    frameworks = [row for row in data["frameworks"] if row["k_first"] == k]
    cards = []
    for card in shaped["cards"]:
        if card["k"] != k:
            continue
        copied = dict(card)
        copied["killable"] = slot["status"] == "running"
        copied["seeds"] = card["seed_line"]
        copied["model_seeds"] = _model_seeds(data, card["framework_id"])
        cards.append(copied)
    edit = (
        _json_object(frameworks[0]["edit_json"])
        if frameworks
        else _json_object(None if step_row is None else step_row["edit_json"])
    )
    allocation = []
    for card in cards:
        per_gpu = [seed["alloc_gpu_h"] for seed in card["seed_line"]]
        allocation.append(
            {
                "framework_id": card["framework_id"],
                "seeds": len(card["seed_line"]),
                "gpu_per_seed": per_gpu[0] if per_gpu else None,
                "tokens_per_seed": None
                if not card["seed_line"]
                else next(
                    run["alloc_tokens"]
                    for run in data["l1"]
                    if run["framework_id"] == card["framework_id"]
                ),
            }
        )
    kills = []
    for row in data["kills"]:
        if row["k"] != k:
            continue
        seed = next((run["seed"] for run in data["l1"] if run["run_id"] == row["run_id"]), None)
        kills.append(
            {
                "run_id": row["run_id"],
                "framework_id": row["framework_id"],
                "seed": seed,
                "reason": row["reason"],
            }
        )
    note = None
    if slot["slot"] == "future":
        note = "Unspent budget from earlier steps is not carried into this step."
    elif slot["status"] == "rejected":
        note = "The step is consumed. Nothing is spent."
    return {
        "meta_run_id": data["header"]["meta_run_id"],
        "k": k,
        "slot": slot["slot"],
        "status": slot["status"],
        "hypothesis": slot["hypothesis"],
        "l0_thinking": slot.get("l0_thinking"),
        "tamper_reason": slot["tamper_reason"],
        "parent_framework_id": slot["parent_framework_id"],
        "edit": edit,
        "allocation": allocation,
        "frameworks": cards,
        "sequence": _step_sequence(data, k, slot),
        "logs": [line for line in shaped["logs"] if line["k"] == k],
        "kills": kills,
        "note": note,
        "budget_gpu_h": slot["budget_gpu_h"],
        "budget_tokens": slot["budget_tokens"],
        "strip": shaped["strip"],
    }


def _cell_from_run(data: dict | None, replicate: int) -> dict:
    if data is None:
        return {
            "replicate": replicate,
            "state": "not_started",
            "meta_run_id": None,
            "k": None,
            "K": None,
            "gpu_h": None,
            "tokens": None,
            "wall_s": None,
            "j_sel": None,
        }
    strip = shape_strip(data)
    state = "running" if strip["running"] else "complete"
    if strip["k"] < strip["K"] and not strip["running"]:
        state = "partial"
    return {
        "replicate": replicate,
        "state": state,
        "meta_run_id": strip["meta_run_id"],
        "k": strip["k"],
        "K": strip["K"],
        "gpu_h": strip["gpu_h_used"],
        "tokens": strip["tokens_used"],
        "wall_s": strip["elapsed_s"],
        "j_sel": strip["leading_j_sel"],
    }


def _match(runs: list[dict], phase: str, arm: int, replicate: int) -> dict | None:
    for data in runs:
        header = data["header"]
        if header["phase"] == phase and header["arm"] == arm and header["replicate"] == replicate:
            return data
    return None


def freeze_preview(repo: Path, runs: list[dict]) -> dict:
    dirty = True
    dirty_count = None
    try:
        completed = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        lines = [line for line in completed.stdout.splitlines() if line.strip()]
        dirty = bool(lines)
        dirty_count = len(lines)
    except (OSError, subprocess.TimeoutExpired):
        dirty = True
        dirty_count = None
    frozen = any(int(data["header"]["design_version"]) >= 1 for data in runs)
    return {
        "tag": "prereg-v1",
        "dirty": dirty,
        "dirty_count": dirty_count,
        "frozen": frozen,
    }


def _blank_strip(horizon: int) -> dict:
    return {
        "meta_run_id": None,
        "k": 0,
        "K": horizon,
        "phase": None,
        "arm": None,
        "arm_name": None,
        "replicate": None,
        "gpu_h_used": 0.0,
        "gpu_h_cap": horizon * 0.75,
        "tokens_used": 0,
        "tokens_cap": horizon * 700_000,
        "elapsed_s": 0.0,
        "wall_band_h": [8, 13] if horizon == 20 else None,
        "leading_j_sel": None,
        "leading_framework_id": None,
        "elected": False,
        "running": False,
        "design_hash": None,
        "design_version": 0,
        "lamp": {"level": "ok", "text": "no run loaded"},
        "scorer": {"state": "stopped", "outbox_depth": 0},
        "as_of": None,
    }


def shape_study(runs: list[dict], repo: Path) -> dict:
    horizon = stored_horizon(repo)
    live = next(
        (data for data in runs if data["header"]["phase"] == "loop" and any(step["status"] == "running" for step in data["steps"])),
        None,
    )
    strip = shape_strip(live) if live is not None else _blank_strip(horizon)
    arms = []
    any_running = False
    any_started = False
    all_complete = True
    for arm, name in ARMS:
        cells = []
        for replicate in (1, 2, 3):
            cell = _cell_from_run(_match(runs, "loop", arm, replicate), replicate)
            cells.append(cell)
            if cell["state"] == "running":
                any_running = True
            if cell["state"] != "not_started":
                any_started = True
            if cell["state"] != "complete":
                all_complete = False
        arms.append({"arm": arm, "name": name, "cells": cells})
    if not any_started:
        phase_state = "not_started"
    elif all_complete:
        phase_state = "complete"
    elif any_running:
        phase_state = "running"
    else:
        phase_state = "partial"
    ablations = []
    for key, name in ABLATIONS:
        ablations.append(
            {
                "id": key,
                "name": name,
                "cells": [_cell_from_run(None, replicate) for replicate in (1, 2)],
            }
        )
    pilots = [data for data in runs if data["header"]["phase"] == "pilot"]
    pilot_cards = []
    for data in pilots:
        card = _cell_from_run(data, data["header"]["replicate"])
        pilot_cards.append(card)
    if not pilots:
        pilot_state = "not_started"
        pilot_detail = "0 of 2"
    else:
        done = sum(1 for card in pilot_cards if card["state"] == "complete")
        pilot_state = "complete" if done >= 2 else "partial" if done else "running"
        pilot_detail = f"{done} of 2"
    preview = freeze_preview(repo, runs)
    scorer = strip["scorer"]
    stages = [
        {"id": "checks", "label": "Acceptance checks", "state": "not_started", "detail": ""},
        {"id": "baselines", "label": "Baselines", "state": "not_started", "detail": ""},
        {"id": "pilot", "label": "Pilot", "state": pilot_state, "detail": pilot_detail},
        {
            "id": "freeze",
            "label": "Freeze",
            "state": "complete" if preview["frozen"] else "not_started",
            "detail": preview["tag"],
        },
        {"id": "phase1", "label": "Phase 1", "state": phase_state, "detail": ""},
        {"id": "phase2", "label": "Phase 2", "state": "not_started", "detail": "κ = 10, one fresh seed"},
        {"id": "report", "label": "Report", "state": "not_started", "detail": ""},
    ]
    return {
        "experiment_k": horizon,
        "live_meta_run_id": None if live is None else live["header"]["meta_run_id"],
        "strip": strip,
        "freeze": preview,
        "scorer": scorer,
        "stages": stages,
        "arms": arms,
        "ablations": ablations,
        "pilot_runs": pilot_cards,
    }


def find_run(root: Path, meta_run_id: str) -> dict | None:
    for data in load_runs(root):
        if data["header"]["meta_run_id"] == meta_run_id:
            return data
    return None


def pilot_report_payload(root: Path, repo: Path) -> dict:
    horizon = stored_horizon(repo)
    report_path = None
    for directory in run_directories(root):
        candidate = directory / "pilot_report.json"
        if candidate.exists():
            report_path = candidate
            break
    base = {
        "available": False,
        "experiment_k": horizon,
        "k_rule": None,
        "note": "The Section 7.3 figure is a record of the rule. It does not change the horizon.",
    }
    if report_path is None:
        return base
    report = json.loads(report_path.read_text(encoding="utf-8"))
    kept = {
        "available": True,
        "experiment_k": horizon,
        "k_rule": report.get("k_rule"),
        "k_gain": report.get("k_gain"),
        "g_hat": report.get("g_hat"),
        "tau": report.get("tau"),
        "sigma_seed": report.get("sigma_seed"),
        "j_sel": report.get("j_sel"),
        "note": report.get("note") or base["note"],
        "gpu_h_per_l1_run": report.get("gpu_h_per_l1_run"),
        "tokens_per_l1_run": report.get("tokens_per_l1_run"),
        "tokens_per_l0_step": report.get("tokens_per_l0_step"),
        "wall_clock_per_step_s": report.get("wall_clock_per_step_s"),
        "training_nodes_per_run": report.get("training_nodes_per_run"),
        "tamper_rate": report.get("tamper_rate"),
        "rejected_step_fraction": report.get("rejected_step_fraction"),
        "headroom_ok": report.get("headroom_ok"),
        "s_sel_still_rising_at_b": report.get("s_sel_still_rising_at_b"),
    }
    return kept
