# Control-path smoke test

Archived on 26 Oct 2026 so the rest of the experiment can start from the spec layout. This check is not a scientific result and does not set `K`. The horizon is `configs/experiment.json` at the repo root. The decision is written in `report_experiment/horizon.md`.

From the repo root:

```bash
PYTHONPATH=archive/control-path-smoke python3 -m smoke.run --steps 3 --n 800
PYTHONPATH=archive/control-path-smoke python3 -m smoke.run --steps 5 --n 800
PYTHONPATH=archive/control-path-smoke python3 -m smoke.vault_scorer --run runs/smoke/<run-id>
python3 -m pytest
```

`--steps 5` prints the Section 7.3 result on a fixture curve, then the stored experiment horizon. The fixture result does not replace `K`.
