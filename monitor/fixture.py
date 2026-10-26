"""Synthetic public event log for the control room.

The figures are invented. They are not Jena results and they carry no
hold-out score. A pilot curve is the Section 7.3 example that the archived
rule maps to 17. That number is stored as a report field. It does not write K.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from monitor.ingest import ingest
from monitor.metrics import area, median

B = 0.25
B_STEP_GPU = 0.75
B_STEP_TOK = 700_000
DESIGN = "dev-unfrozen"
T0 = datetime(2026, 10, 26, 8, 0, tzinfo=timezone.utc)

# (local id, parent local id, operator, b, u, s)
STORY = [
    (1, None, "draft", 0.04, 0.20, 0.34),
    (2, 1, "debug", 0.08, 0.18, 0.40),
    (3, 1, "improve", 0.12, 0.33, 0.28),
    (4, 3, "improve", 0.18, 0.41, 0.46),
    (5, 4, "improve", 0.25, 0.44, 0.50),
]

PILOT_CURVE = [0.40, 0.50, 0.56, 0.62, 0.68]


def _stamp(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _section_73(curve: list[float], sigma: float):
    root = Path(__file__).resolve().parents[1]
    archive = str(root / "archive" / "control-path-smoke")
    if archive not in sys.path:
        sys.path.insert(0, archive)
    from smoke.decide_k import decide_k

    return decide_k(curve, sigma)


def _vary(story, s_shift: float, keep: int | None = None):
    rows = story if keep is None else story[:keep]
    varied = []
    for local, parent, operator, b, u, score in rows:
        varied.append((local, parent, operator, b, u, round(score + s_shift, 4)))
    return varied


def _incumbents(models: list[dict]) -> list[dict]:
    best = None
    chosen = []
    for model in sorted(models, key=lambda item: (item["b_created"], item["seq"])):
        if best is None or model["u"] > best["u"]:
            best = model
            chosen.append(model)
    return chosen


class _Log:
    def __init__(self, meta_run_id: str, design: str):
        self.meta = meta_run_id
        self.design = design
        self.events: list[dict] = []
        self.cum_gpu = 0.0
        self.cum_tokens = 0

    def add(self, kind: str, **fields) -> None:
        row = {"meta_run_id": self.meta, "design_hash": self.design}
        row.update(fields)
        row["type"] = kind
        self.events.append(row)


def _emit_seed(log: _Log, spec: dict, story, seed: int, status: str, when: datetime, step_end: datetime | None) -> float:
    framework_id = spec["fid"]
    run_id = f"{log.meta}-{framework_id}-s{seed}"
    models = []
    for seq, (local, parent, operator, b, u, score) in enumerate(story, start=1):
        model_id = f"{run_id}-m{local}"
        parent_id = None if parent is None else f"{run_id}-m{parent}"
        models.append(
            {
                "model_id": model_id,
                "parent_model_id": parent_id,
                "operator": operator,
                "b_created": b,
                "u": u,
                "s": score,
                "seq": seq,
                "local": local,
            }
        )
    chosen = {item["model_id"] for item in _incumbents(models)}
    gpu_used = spec.get("gpu_used", {}).get(seed, models[-1]["b_created"] if status == "running" else B)
    if status != "running":
        gpu_used = models[-1]["b_created"] if status == "killed" else B
    tokens = spec.get("tokens", {}).get(seed, 40_000 if status == "killed" else 70_000 if status == "running" else 100_000)
    kill_reason = None
    if status == "killed":
        kill_reason = "L1 stopped the seed: the in-run cap was reached."
    log.add(
        "l1_run",
        ts=_stamp(when),
        run_id=run_id,
        k=spec["k"],
        framework_id=framework_id,
        parent_framework_id=spec["parent"],
        seed=seed,
        alloc_gpu_h=B,
        alloc_tokens=B_STEP_TOK // 3,
        status=status,
        kill_reason=kill_reason,
        phase=spec["phase"],
        kappa=None,
        gpu_h_used=gpu_used,
        tokens_used=tokens,
    )
    span = step_end - when if step_end is not None else timedelta(seconds=1080)
    for model in models:
        fraction = model["b_created"] / B
        moment = when + timedelta(seconds=span.total_seconds() * min(fraction, 0.99))
        digest = _sha(model["model_id"])
        log.add(
            "model",
            model_id=model["model_id"],
            ts=_stamp(moment),
            run_id=run_id,
            framework_id=framework_id,
            branch_id=model["parent_model_id"] or framework_id,
            parent_model_id=model["parent_model_id"],
            operator=model["operator"],
            seed=seed,
            b_created=model["b_created"],
            u=model["u"],
            status="running" if status == "running" and model is models[-1] else "complete",
            artifact_path=f"artifacts/{digest}",
            artifact_sha256=digest,
            is_ideal_model=0,
            seq=model["seq"],
        )
        became = model["model_id"] in chosen
        message = {
            "draft": "draft candidate submitted",
            "debug": "debug candidate submitted",
            "improve": "improve candidate submitted",
        }[model["operator"]]
        if became:
            message += "; it is the incumbent"
        else:
            message += "; u did not replace the incumbent"
        log.add(
            "log_line",
            ts=_stamp(moment),
            run_id=run_id,
            k=spec["k"],
            role="L1",
            model_id=model["model_id"],
            message=message,
        )
        log.add(
            "gpu_sample",
            ts=_stamp(moment),
            run_id=run_id,
            k=spec["k"],
            model_id=model["model_id"],
            b=model["b_created"],
            gpu_busy=1,
        )
        if became:
            log.add(
                "eval_event",
                ts=_stamp(moment),
                run_id=run_id,
                model_id=model["model_id"],
                b=model["b_created"],
                split="sel",
                s=model["s"],
                e_mae=round(2.4 - 0.4 * model["s"], 4),
                trigger="incumbent_change",
            )
            if status != "running":
                log.add(
                    "d0_outbox",
                    event_id=f"out-{model['model_id']}",
                    ts=_stamp(moment),
                    outbox_type="meta_step_completed",
                    k=spec["k"],
                    run_id=run_id,
                    model_id=model["model_id"],
                    artifact_path=f"artifacts/{digest}",
                    artifact_sha256=digest,
                    hmac="demo-hmac",
                )
    if status == "killed":
        log.add(
            "kill_event",
            ts=_stamp(when + span),
            run_id=run_id,
            framework_id=framework_id,
            k=spec["k"],
            reason=kill_reason,
        )
    raw = [(model["b_created"], model["s"]) for model in _incumbents(models)]
    end = gpu_used if status == "running" else B
    return area(raw, end)


def _framework_block(log: _Log, spec: dict, when: datetime, step_end: datetime | None) -> None:
    areas = []
    for seed in (101, 102, 103):
        shift = {101: 0.0, 102: -0.03, 103: 0.04}[seed]
        keep = None
        status = "complete"
        if spec.get("live"):
            keep = 3
            status = "running"
        elif spec.get("killed_seed") == seed:
            keep = 3
            status = "killed"
        story = _vary(STORY, spec["s_shift"] + shift, keep)
        areas.append(_emit_seed(log, spec, story, seed, status, when, step_end))
    ordered = sorted(zip((101, 102, 103), areas))
    seed_areas = [value for _seed, value in ordered]
    finished = not spec.get("live")
    snapshot = _sha(spec["fid"])
    log.add(
        "framework",
        ts=_stamp(when),
        framework_id=spec["fid"],
        k_first=spec["k"],
        parent_framework_id=spec["parent"],
        level1_snapshot=snapshot,
        rules_json=json.dumps(spec["rules"], sort_keys=True),
        edit_json=json.dumps(spec["edit"], sort_keys=True),
        n_seeds=3,
        j_sel_median=median(seed_areas) if finished else None,
        j_sel_seed1=seed_areas[0] if finished else None,
        j_sel_seed2=seed_areas[1] if finished else None,
        j_sel_seed3=seed_areas[2] if finished else None,
        ci_lo=min(seed_areas) if finished else None,
        ci_hi=max(seed_areas) if finished else None,
        n_killed=1 if spec.get("killed_seed") else 0,
        elected=0,
        hypothesis_text=spec["hypothesis"],
    )


def _edit(theta: str, rules: str, phi: str) -> dict:
    return {"theta": theta, "rules": rules, "phi": phi}


def _loop_specs() -> list[dict]:
    base_rules = {"n_max": 8, "wall_clock_s": 900, "stop": "budget"}
    raised = {"n_max": 12, "wall_clock_s": 900, "stop": "budget"}
    return [
        {
            "fid": "v1",
            "k": 1,
            "parent": None,
            "s_shift": 0.0,
            "hypothesis": "",
            "phase": "loop",
            "rules": base_rules,
            "edit": _edit(
                "Initial draft, debug, and improve operators.",
                "n_max 8. The run ends at budget B.",
                "Parents are the top 5 by J_sel.",
            ),
        },
        {
            "fid": "v2",
            "k": 2,
            "parent": "v1",
            "s_shift": 0.08,
            "hypothesis": "A seasonal residual feature should lift J_sel by about 0.05.",
            "phase": "loop",
            "rules": base_rules,
            "edit": _edit(
                "Draft prompt now asks for a seasonal residual feature.",
                "Unchanged.",
                "Unchanged.",
            ),
        },
        {
            "fid": "v4",
            "k": 4,
            "parent": "v2",
            "s_shift": -0.02,
            "hypothesis": "A deeper tree memory should help. J_sel should rise by about 0.04.",
            "phase": "loop",
            "rules": base_rules,
            "edit": _edit("Longer memory in the search tree.", "Unchanged.", "Unchanged."),
        },
        {
            "fid": "v5",
            "k": 5,
            "parent": "v2",
            "s_shift": 0.14,
            "hypothesis": "Branching from v2 with a shorter debug loop should recover the drop. J_sel should rise by about 0.06.",
            "phase": "loop",
            "rules": base_rules,
            "edit": _edit(
                "Shorter debug prompt.",
                "Unchanged.",
                "Parent is v2, chosen from the top 5.",
            ),
        },
        {
            "fid": "v6",
            "k": 6,
            "parent": "v5",
            "s_shift": 0.10,
            "hypothesis": "Raising n_max should add a late gain of about 0.03.",
            "phase": "loop",
            "rules": raised,
            "killed_seed": 103,
            "edit": _edit("Operator set left as it was.", "n_max raised from 8 to 12.", "Unchanged."),
        },
        {
            "fid": "v7",
            "k": 7,
            "parent": "v5",
            "s_shift": 0.12,
            "hypothesis": "A calendar interaction in the draft prompt should raise J_sel by about 0.02.",
            "phase": "loop",
            "rules": base_rules,
            "live": True,
            "gpu_used": {101: 0.14, 102: 0.16, 103: 0.19},
            "tokens": {101: 70_000, 102: 80_000, 103: 90_000},
            "edit": _edit(
                "Draft prompt adds a calendar interaction.",
                "Unchanged.",
                "Parent is v5.",
            ),
        },
    ]


def _spend(log: _Log, k: int, when: datetime, gpu_rows: list[tuple[str, float, int]]) -> tuple[float, int]:
    spent_gpu = 0.0
    spent_tokens = 0
    for role, run_id, gpu_h, tokens in gpu_rows:
        log.cum_gpu += gpu_h
        log.cum_tokens += tokens
        spent_gpu += gpu_h
        spent_tokens += tokens
        log.add(
            "ledger",
            ts=_stamp(when),
            role=role,
            run_id=run_id,
            k=k,
            gpu_h=gpu_h,
            tokens_in=tokens // 2,
            tokens_out=tokens - tokens // 2,
            cum_gpu_h=round(log.cum_gpu, 6),
            cum_tokens=log.cum_tokens,
        )
    return spent_gpu, spent_tokens


def loop_events() -> tuple[list[dict], datetime]:
    log = _Log("loop-arm6-r1", DESIGN)
    specs = {item["k"]: item for item in _loop_specs()}
    cursor = T0
    as_of = cursor
    log.add(
        "run_header",
        arm=6,
        arm_name="L0 tree",
        replicate=1,
        phase="loop",
        topology="tree",
        k_horizon=20,
        b_gpu=B,
        b_step_gpu=B_STEP_GPU,
        b_step_tokens=B_STEP_TOK,
        design_version=0,
        design_ok=1,
        changed_after_d0_view=0,
        last_d0_look_ts=None,
        as_of="",
        scorer_state="stopped",
        kappa=10,
        ts=_stamp(T0),
    )
    # as_of is filled after the clock is known; placeholder replaced below.
    for k in range(1, 8):
        t_start = cursor
        if k == 3:
            t_end = cursor + timedelta(seconds=600)
            log.add(
                "meta_step",
                ts=_stamp(t_start),
                k=k,
                t_start=_stamp(t_start),
                t_end=_stamp(t_end),
                budget_gpu_h=B_STEP_GPU,
                budget_tokens=B_STEP_TOK,
                spent_gpu_h=0,
                spent_tokens=0,
                l0_s=600,
                l1_s=0,
                hypothesis_id="h3",
                hypothesis_text="Reading the core budget counter would let the loop stop early.",
                status="rejected",
                phase="loop",
                tamper_reason="The edit reads a budget counter.",
                parent_framework_id="v2",
                edit_json=json.dumps(
                    _edit(
                        "No change to L1.",
                        "Tried to read the core budget counter.",
                        "Tried to add a stop if the counter is low.",
                    ),
                    sort_keys=True,
                ),
            )
            log.add(
                "log_line",
                ts=_stamp(t_end),
                run_id=None,
                k=k,
                role="core",
                model_id=None,
                message="tamper audit rejected the edit; the step is consumed and nothing is spent",
            )
            cursor = t_end
            continue
        spec = specs[k]
        live = bool(spec.get("live"))
        t_end = None if live else cursor + timedelta(seconds=2400)
        step_end = cursor + timedelta(seconds=1080) if live else t_end
        _framework_block(log, spec, t_start + timedelta(seconds=600), step_end)
        rows = [("L0", None, 0.0, 120_000)]
        for seed in (101, 102, 103):
            run_id = f"{log.meta}-{spec['fid']}-s{seed}"
            if spec.get("killed_seed") == seed:
                rows.append(("L1", run_id, 0.12, 40_000))
            elif live:
                rows.append(("L1", run_id, spec["gpu_used"][seed], spec["tokens"][seed]))
            else:
                rows.append(("L1", run_id, B, 100_000))
        spent_gpu, spent_tokens = _spend(log, k, t_start, rows)
        log.add(
            "meta_step",
            ts=_stamp(t_start),
            k=k,
            t_start=_stamp(t_start),
            t_end=None if t_end is None else _stamp(t_end),
            budget_gpu_h=B_STEP_GPU,
            budget_tokens=B_STEP_TOK,
            spent_gpu_h=round(spent_gpu, 6),
            spent_tokens=spent_tokens,
            l0_s=600,
            l1_s=480 if live else 1800,
            hypothesis_id=f"h{k}",
            hypothesis_text=spec["hypothesis"],
            status="running" if live else "accepted",
            phase="loop",
            tamper_reason=None,
            parent_framework_id=spec["parent"],
            edit_json=json.dumps(spec["edit"], sort_keys=True),
        )
        if live:
            as_of = cursor + timedelta(seconds=1080)
            log.add(
                "log_line",
                ts=_stamp(as_of),
                run_id=f"{log.meta}-{spec['fid']}-s103",
                k=k,
                role="L1",
                model_id=f"{log.meta}-{spec['fid']}-s103-m3",
                message="improve candidate is training",
            )
        else:
            cursor = t_end
            as_of = cursor
    for event in log.events:
        if event["type"] == "run_header":
            event["as_of"] = _stamp(as_of)
    return log.events, as_of


def _pilot_story(target: float):
    score = round(target / 0.8, 6)
    return [
        (1, None, "draft", 0.05, 0.20, score),
        (2, 1, "improve", 0.25, 0.40, score),
    ]


def pilot_events() -> list[dict]:
    log = _Log("pilot-arm6-r1", DESIGN)
    log.add(
        "run_header",
        arm=6,
        arm_name="L0 tree",
        replicate=1,
        phase="pilot",
        topology="tree",
        k_horizon=5,
        b_gpu=B,
        b_step_gpu=B_STEP_GPU,
        b_step_tokens=B_STEP_TOK,
        design_version=0,
        design_ok=1,
        changed_after_d0_view=0,
        last_d0_look_ts=None,
        as_of="",
        scorer_state="stopped",
        kappa=10,
        ts=_stamp(T0),
    )
    cursor = T0
    parent = None
    for index, target in enumerate(PILOT_CURVE, start=1):
        fid = f"p{index}"
        t_start = cursor
        t_end = cursor + timedelta(seconds=2400)
        spec = {
            "fid": fid,
            "k": index,
            "parent": parent,
            "phase": "pilot",
            "s_shift": 0.0,
            "hypothesis": "" if index == 1 else f"Pilot step {index}: measure cost and the D1 curve.",
            "rules": {"n_max": 8, "stop": "budget"},
            "edit": _edit("Pilot scaffold.", "Provisional n_max 8.", "Tree, short horizon."),
        }
        # Identical seeds so the median equals the worked-example target.
        for seed in (9001, 9002, 9003):
            _emit_seed(log, spec, _pilot_story(target), seed, "complete", t_start, t_end)
        areas = [target, target, target]
        log.add(
            "framework",
            ts=_stamp(t_start),
            framework_id=fid,
            k_first=index,
            parent_framework_id=parent,
            level1_snapshot=_sha(fid),
            rules_json=json.dumps(spec["rules"], sort_keys=True),
            edit_json=json.dumps(spec["edit"], sort_keys=True),
            n_seeds=3,
            j_sel_median=median(areas),
            j_sel_seed1=target,
            j_sel_seed2=target,
            j_sel_seed3=target,
            ci_lo=target,
            ci_hi=target,
            n_killed=0,
            elected=0,
            hypothesis_text=spec["hypothesis"],
        )
        rows = [("L0", None, 0.0, 120_000)]
        for seed in (9001, 9002, 9003):
            rows.append(("L1", f"{log.meta}-{fid}-s{seed}", B, 100_000))
        spent_gpu, spent_tokens = _spend(log, index, t_start, rows)
        log.add(
            "meta_step",
            ts=_stamp(t_start),
            k=index,
            t_start=_stamp(t_start),
            t_end=_stamp(t_end),
            budget_gpu_h=B_STEP_GPU,
            budget_tokens=B_STEP_TOK,
            spent_gpu_h=round(spent_gpu, 6),
            spent_tokens=spent_tokens,
            l0_s=600,
            l1_s=1800,
            hypothesis_id=f"ph{index}",
            hypothesis_text=spec["hypothesis"],
            status="accepted",
            phase="pilot",
            tamper_reason=None,
            parent_framework_id=parent,
            edit_json=json.dumps(spec["edit"], sort_keys=True),
        )
        parent = fid
        cursor = t_end
    for event in log.events:
        if event["type"] == "run_header":
            event["as_of"] = _stamp(cursor)
    return log.events


def pilot_report() -> dict:
    decision = _section_73(PILOT_CURVE, 0.0)
    return {
        "phase": "pilot",
        "j_sel": PILOT_CURVE,
        "sigma_seed": 0.0,
        "k_rule": decision.k,
        "k_gain": decision.k_gain,
        "g_hat": decision.g_hat,
        "tau": decision.tau,
        "note": "The Section 7.3 figure is a record of the rule. It does not change the horizon.",
        "gpu_h_per_l1_run": B,
        "tokens_per_l1_run": 100_000,
        "tokens_per_l0_step": 120_000,
        "wall_clock_per_step_s": 2400,
        "training_nodes_per_run": 2,
        "tamper_rate": 0.0,
        "rejected_step_fraction": 0.0,
        "headroom_ok": True,
        "s_sel_still_rising_at_b": True,
    }


def _write_run(directory: Path, events: list[dict]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(event, sort_keys=True) for event in events]
    (directory / "events.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    ingest(directory / "events.jsonl", directory / "monitor.db")


def build_demo(root: Path) -> Path:
    """Write two synthetic meta-runs under ``root`` and ingest them."""
    root.mkdir(parents=True, exist_ok=True)
    loop, _as_of = loop_events()
    _write_run(root / "loop-arm6-r1", loop)
    _write_run(root / "pilot-arm6-r1", pilot_events())
    (root / "pilot-arm6-r1" / "pilot_report.json").write_text(
        json.dumps(pilot_report(), indent=2) + "\n",
        encoding="utf-8",
    )
    index = [
        {"dir": "loop-arm6-r1", "meta_run_id": "loop-arm6-r1"},
        {"dir": "pilot-arm6-r1", "meta_run_id": "pilot-arm6-r1"},
    ]
    (root / "index.json").write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    return root
