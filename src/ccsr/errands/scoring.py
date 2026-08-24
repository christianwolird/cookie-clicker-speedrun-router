"""Local descendant scoring used by the current routing heuristics."""


def age_score(ancestor, descendant):
    acquisition_time = descendant.age - ancestor.age
    ancestor_cps = ancestor.cps()
    descendant_cps = descendant.cps()
    cps_gain = descendant_cps - ancestor_cps
    if acquisition_time <= 0 or cps_gain <= 0:
        return float("inf")
    return acquisition_time * descendant_cps / cps_gain
