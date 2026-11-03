from clamp import clamp


def test_negative_lower_bound():
    assert clamp(-2, 0, 10) == 0


def test_nonzero_lower_bound():
    assert clamp(1, 5, 10) == 5
