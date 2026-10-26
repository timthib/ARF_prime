# ARF_prime

Self-referential two-level research agent. The binding spec is [`methodology.md`](methodology.md). This checkout currently contains that spec and the directories the next stage needs. The core, the agents, and the real vault are not built yet.

## Data

Do not commit the Jena Climate file, a D0/D1 split, or anything derived from D0.

Keep the copy that already lives in the other repo. This experiment will read a prepared `D1_fit` only, from outside git, when the real runs start. D0 is loaded by hand into a vault the agents cannot see. The coding agent does not read D0. Local run output goes under `runs/`, which git ignores.

## Layout

```
methodology.md          spec
configs/                experiment settings, empty until the smoke test
data/splits/            empty on purpose; no dataset is stored here
smoke/                  reserved for the synthetic control-path smoke test
tests/
runs/                   local output, gitignored
```

Later phases add `core/`, `level0/`, `level1/`, `monitor/`, `d0vault/`, `pilot/`, and `analysis/` as the spec's checklist reaches them.
