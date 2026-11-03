import pytest
from clamp import clamp


def test_upper_bound():
    assert clamp(20, 0, 10) == 10


def test_in_range():
    assert clamp(7, 0, 10) == 7


def test_invalid_bounds():
    with pytest.raises(ValueError):
        clamp(4, 10, 0)
