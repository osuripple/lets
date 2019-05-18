def zingonify(d):
    """
    Zingonifies a string

    :param d: input dict
    :return: zingonified dict as str
    """
    return "|".join(f"{k}:{v}" for k, v in d.items())


def clamp(x, min_, max_):
    return max(min(x, max_), min_)
