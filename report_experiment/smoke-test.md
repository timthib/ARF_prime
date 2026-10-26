# Smoke test

**Choice.** A synthetic control-path smoke test exists. It checks the public log, the vault separation, and the Section 7.3 arithmetic. It does not set K, and it does not enter the main analysis.

**Status.** In force as a check. It is not a scientific result. On 26 Oct 2026 the code was moved to `archive/control-path-smoke/` and left runnable. It was not deleted: the tests lock the split indices and the K-rule examples, and git would be an awkward place to keep a check we still run. It was not left at the repo root, so `core/` and the other spec packages can start without a toy loop beside them.

## Why

The real runs are expensive, so the control path had to be exercised before any GPU hour and before any contact with D0. A short synthetic run can show that a fixed number of steps is logged, that a vault value does not come back, and that the K rule matches its worked examples. It cannot show how fast a real agent improves.

## How

From the repo root, `python3 -m pytest` runs the archived tests. Two commands exercise the path:

```bash
PYTHONPATH=archive/control-path-smoke python3 -m smoke.run --steps 3 --n 800
PYTHONPATH=archive/control-path-smoke python3 -m smoke.run --steps 5 --n 800
```

Three steps match the spec's fake end-to-end check: a public `events.jsonl`, a `monitor.db` whose only split is `sel`, and no vault token in those files. Five steps feed the fixture curve `[0.40, 0.50, 0.56, 0.62, 0.68]`. The recent gain is 0.06, and the rule returns 17. The report field `curve_source` is `fixture`. The stored horizon remains 20, as recorded in [horizon.md](horizon.md).

Outputs are tagged `phase = smoke`, written under `runs/smoke/`, and marked `excluded_from_main_analysis`. Seeds start at 91001. The vault scorer is a separate command, `PYTHONPATH=archive/control-path-smoke python3 -m smoke.vault_scorer`, and the run does not read what it writes.

## What may be cited

Cite this log and `configs/experiment.json` for K. Cite spec section 3.2 for the split. Do not cite the printed dry-run value 17 as the horizon of the experiment.
