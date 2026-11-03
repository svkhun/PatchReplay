"""Synthetic bounded-value utility; already corrected lower bound."""


def clamp(value, lower, upper):
    if lower > upper:
        raise ValueError("lower must not exceed upper")
    return max(lower, min(value, upper))
