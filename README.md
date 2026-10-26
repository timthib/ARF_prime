# ARF_prime

Self-referential two-level research agent. The binding spec is [`methodology.md`](methodology.md). Choices already made are in [`report_experiment/`](report_experiment/README.md). The core, the agents, and the real vault are not built yet. The control room and the D0 room are local viewers over synthetic logs until those exist.

## Open the rooms

Two processes, two databases. Start each from the repo root, in its own terminal. Closing the browser does not stop a run.

```bash
python3 -m monitor
python3 -m d0vault
```

- Control room: [http://127.0.0.1:8501](http://127.0.0.1:8501). Public, D1 only. It opens on the meta-run in progress.
- D0 room: [http://127.0.0.1:8502](http://127.0.0.1:8502). You only, loopback only. The first start prints a password once in that terminal and does not write it into the tree. Keep it yourself. A later start does not print it again, and L0 and L1 must not see it.

Trigger buttons stay disabled until the core command they call exists.

## Data

Do not commit the Jena Climate file, a D0/D1 split, or anything derived from D0.

Keep the copy that already lives in the other repo. This experiment will read a prepared `D1_fit` only, from outside git, when the real runs start. D0 is loaded by hand into a vault the agents cannot see. The coding agent does not read D0. Local run output goes under `runs/`, which git ignores.

## Layout

```
methodology.md                 spec
configs/experiment.json        K = 20
report_experiment/             decision log for the report
data/splits/                   empty on purpose
archive/control-path-smoke/    synthetic check, set aside
monitor/                       control room, D1 only
d0vault/                       D0 room, loopback only
runs/                          local output, gitignored
```

Later phases add `core/`, `level0/`, `level1/`, `pilot/`, and `analysis/` as the spec's checklist reaches them.

## Archived smoke test

The check does not need the Jena file or D0. It stays out of the main tree so the real packages start clean. Details are in [`report_experiment/smoke-test.md`](report_experiment/smoke-test.md).

```bash
python3 -m pip install -r requirements-dev.txt
python3 -m pytest
PYTHONPATH=archive/control-path-smoke python3 -m smoke.run --steps 5 --n 800
```

The five-step command prints a fixture result of the Section 7.3 rule and then `experiment K=20`. The fixture result does not replace the horizon.
