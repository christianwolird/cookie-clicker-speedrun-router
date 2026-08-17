"""Local descendant scoring used by the current routing heuristics."""


def age_score(ancestor, descendant):
    effective_cost = (descendant.age - ancestor.age) * ancestor.cps()
    cps_gain = descendant.cps() - ancestor.cps()
    if effective_cost <= 0 or cps_gain <= 0:
        return float("inf")
    return effective_cost * descendant.cps() / cps_gain
