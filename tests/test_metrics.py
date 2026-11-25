from jailforge.eval.metrics import wilson_ci


def test_wilson_ci_empty():
    assert wilson_ci(0, 0) == (0.0, 0.0)


def test_wilson_ci_bounds():
    low, high = wilson_ci(5, 10)
    assert 0.0 <= low < 0.5 < high <= 1.0


def test_wilson_ci_extremes():
    low, high = wilson_ci(0, 10)
    assert low == 0.0
    assert high < 0.4
    low, high = wilson_ci(10, 10)
    assert low > 0.6
    assert high == 1.0
