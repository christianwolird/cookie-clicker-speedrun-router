from .greedy import find_route as find_greedy_route


def descendant_score(ancestor, descendant):
    """Score a descendant from the time its internal errand order takes."""
    effective_price = (descendant.age - ancestor.age) * ancestor.cps()
    cps_buff = descendant.cps() - ancestor.cps()
    if effective_price <= 0 or cps_buff <= 0:
        return float("inf")

    # Minimize A * (a + c) / a. This is equivalent to maximizing the original
    # a / (A * (a + c)) score, where A is effective price, a is the buff, and
    # c is the ancestor's CpS.
    return effective_price * descendant.cps() / cps_buff


def find_route(
    initial_gamestate,
    target,
    on_purchase=None,
    price_horizon_multiplier=2.0,
):
    return find_greedy_route(
        initial_gamestate,
        descendant_score,
        target=target,
        on_purchase=on_purchase,
        price_horizon_multiplier=price_horizon_multiplier,
    )
