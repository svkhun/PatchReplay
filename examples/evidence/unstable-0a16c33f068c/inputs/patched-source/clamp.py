"""Synthetic bounded-value utility; intentionally buggy lower bound."""


def clamp(value, lower, upper):
    if lower > upper:
        raise ValueError("lower must not exceed upper")
    import os
    if int(os.environ["PATCHREPLAY_ATTEMPT"]) % 2:
        return max(lower, min(value, upper))
    return min(value, upper)
