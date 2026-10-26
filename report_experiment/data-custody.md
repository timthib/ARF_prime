# Data custody

**Choice.** This repo does not hold the Jena file, a real D0/D1 split, or anything computed from D0. The copy already used in the other repo stays there.

**Status.** In force. Spec sections 3.3, 9, and 13.

## Why

D0 is the hold-out the agents must not see. A file committed here remains in git history after a later deletion. L0 is a coding agent that can read the checkout, so a raw CSV in `data/raw/` would bypass the vault.

The smoke test does not need the real series. It builds a synthetic one. Asking for the real file, including D0, was therefore unnecessary, and deleting the other repo's copy would only remove a working dataset from the place it is already used.

## How

`.gitignore` excludes `runs/`, `data/raw/`, and columnar data under `data/` (csv, parquet, npy). The only D0-related object the spec allows in git later is a hash, `data/D0.sha256`, written by the user when the vault is loaded.

The smoke materialiser writes three directories inside a gitignored run folder:

- `public/` receives `D1_fit` only, and that is the directory the loop is given
- `core_only/` receives `D1_sel` labels
- `vault/` receives the shifted fake hold-out and a canary token

The loop module does not import the vault scorer. A failed scorer leaves the public log unchanged. The tests check that the canary is absent from the public log, the drop, and `core_only/`.
