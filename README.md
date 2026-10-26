# ARF_prime

Self-referential two-level research agent. The binding spec is [`methodology.md`](methodology.md). This checkout contains that spec and a synthetic smoke test of the control path. The core, the agents, the monitor app, and the real vault are not built yet.

## Data

Do not commit the Jena Climate file, a D0/D1 split, or anything derived from D0.

Keep the copy that already lives in the other repo. This experiment will read a prepared `D1_fit` only, from outside git, when the real runs start. D0 is loaded by hand into a vault the agents cannot see. The coding agent does not read D0. Local run output goes under `runs/`, which git ignores.

## Layout

```
methodology.md          spec
configs/smoke.json      fixture curve and smoke settings
data/splits/            empty on purpose; no dataset is stored here
smoke/                  synthetic control-path smoke test
tests/
runs/smoke/             local output, gitignored
```

Later phases add `core/`, `level0/`, `level1/`, `monitor/`, `d0vault/`, `pilot/`, and `analysis/` as the spec's checklist reaches them.

## Smoke test

No Jena file and no D0 are required. The run builds a short synthetic series, writes the public log, and leaves the shifted hold-out in a vault directory the loop never receives.

```bash
python3 -m pip install -r requirements-dev.txt
python3 -m pytest
python3 -m smoke.run --steps 3 --n 800
python3 -m smoke.run --steps 5 --n 800
python3 -m smoke.vault_scorer --run runs/smoke/<run-id>
```

`--steps 5` feeds a fixture curve into the Section 7.3 rule and prints a dry-run `K`. That number is not a measurement and does not freeze the experiment. Outputs are tagged `phase = smoke` and are excluded from the main analysis. The real monitor app is a later phase; this smoke is the control path that app will sit on.
