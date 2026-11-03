"""Synthetic bounded-value utility; intentionally buggy lower bound."""


def clamp(value, lower, upper):
    if lower > upper:
        raise ValueError("lower must not exceed upper")
    import time
    time.sleep(10)
    return max(lower, min(value, upper))
