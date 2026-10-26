# Data split

**Choice.** On the Jena hourly series (N = 70,128), the nominal shares are 65% `D1_fit`, 15% `D1_sel`, and 20% `D0`.

**Status.** In force. Spec section 3.2.

## Why

The previous cut took the first 80% of the series as D1, then gave 80% of that block to `D1_fit`. Fit was therefore 64% of N, and the selection block was about 16% of N. The intended shares are of the full series, not of D1.

`D0` was already the last 20%. Its calendar range was left unchanged so the hold-out discussed in the spec is the same period as before.

## How

Two cuts, then a gap taken from the start of the later set:

- `n_fit = ⌊0.65 · N⌋ = 45,583`
- `n_d1 = ⌊0.80 · N⌋ = 56,102`
- gap `G = L + H = 48` hours between fit and selection, and again between D1 and D0

| Set | Hours | Usable share of N | Origins |
|---|---|---|---|
| `D1_fit` | 1..45,583 (through 15 Mar 2014, 07:00) | 65.00% | 45,536 |
| gap | 45,584..45,631 | | |
| `D1_sel` | 45,632..56,102 (17 Mar 2014, 08:00 to 27 May 2015, 14:00) | 14.93% | 10,424 |
| embargo | 56,103..56,150 | | |
| `D0` | 56,151..70,128 (29 May 2015, 15:00 to 1 Jan 2017, 00:00) | 19.93% | 13,931 |

The two gaps sit inside the 15% and 20% bands, so the usable selection set and the usable hold-out are each 48 hours short of the nominal fraction. `D1_sel` is 10,471 hours, above the 8,760-hour floor, and contains every season (MAM in 2014 and 2015; JJA, SON, and DJF once).

`tests/test_splits.py` locks every index above. The persistence, seasonal-naive, and ridge errors quoted from the old selection window (hours 44,930..56,102) do not apply to this cut and have to be recomputed.

## Still open

Arms 5 and 6 may still declare a different cut. The integrity floor only requires fit to be at least half of D1, so a declared split can leave 65/15. That is ablation (iv) in the spec, not a change made here.
