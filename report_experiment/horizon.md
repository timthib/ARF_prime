# Horizon K

**Choice.** `K = 20`. The run takes exactly 20 meta-steps: `K_min = K_max = 20`. No early stop, no extension.

**Status.** In force since 26 Oct 2026. Spec sections 0.2, 6, 7, and 14. Value stored in `configs/experiment.json`.

## Why

The spec already limited the horizon to the window 15–20. The bottom of that window existed so a run would contain enough frameworks for the ranking test and enough steps for the tree to branch. The top existed so a run would stay inside the default budget cap.

No measured `J_sel` curve was available. The synthetic smoke test prints 17 on a fixture curve built so that the Section 7.3 example returns 17. That curve was never data, so 17 was not adopted.

20 is the top of the window that had already been written down (`K_hi`). At the current step size of 0.75 GPU-h, twenty steps are 15 GPU-h and about 14 million tokens, which is the whole default cap for one meta-run. The full study at this K is the K = 20 column of spec section 15, about 511 GPU-h, still an assumption until the pilot measures the real step cost.

The cost of this choice is that later steps still run if the gains have already flattened. That is the fixed-horizon rule, and it is accepted. If the pilot finds that the budget cap allows fewer than 20 steps, K is changed by a new written decision. Nothing in the code lowers it.

D0 played no part in the choice.

## How

1. `configs/experiment.json` stores `K`, `K_min`, and `K_max`, all equal to 20, with the date and the source of the override.
2. The spec states the override in the summary, the nomenclature, the budget section, the pilot section, the freeze checklist, and the open-parameter table. Section 7.3 still defines the rule and its worked examples. The paragraph "Override in force" says the runs use 20.
3. The pilot still measures cost and sets `B_step` and `B_tot` from D1 only. It does not choose K. The pipeline diagram says the same.
4. The smoke command prints two numbers. The rule dry-run is the fixture result. The line `experiment K=20` is the horizon. `tests/test_smoke.py` requires both: the fixture decision is 17, and the stored horizon is 20.

The pre-registration, when it is written, copies K from `configs/experiment.json`.
