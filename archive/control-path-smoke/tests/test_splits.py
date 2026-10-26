from smoke.splits import n_hours, n_origins, split_bounds, windows_stay_inside

N = 70128


def test_jena_bounds_match_the_spec():
    bounds = split_bounds(N)
    assert bounds["D1_fit"] == (1, 45583)
    assert bounds["gap"] == (45584, 45631)
    assert bounds["D1_sel"] == (45632, 56102)
    assert bounds["embargo"] == (56103, 56150)
    assert bounds["D0"] == (56151, 70128)
    assert n_hours(bounds["D1_fit"]) == 45583
    assert n_hours(bounds["D1_sel"]) == 10471
    assert n_hours(bounds["D0"]) == 13978
    assert n_origins(45583) == 45536
    assert n_origins(10471) == 10424
    assert n_origins(13978) == 13931
    assert windows_stay_inside(bounds)


def test_ranges_cover_the_series_without_overlap():
    bounds = split_bounds(N)
    covered = []
    for name in ("D1_fit", "gap", "D1_sel", "embargo", "D0"):
        start, end = bounds[name]
        covered.append((start, end))
    assert covered[0][0] == 1
    assert covered[-1][1] == N
    for left, right in zip(covered, covered[1:]):
        assert left[1] + 1 == right[0]
