from .greedy import find_route as find_greedy_route


def descendant_score(ancestor, descendant):
    """Score a descendant from the sum of its items' sticker prices."""
    price = descendant.lifetime_cookies - ancestor.lifetime_cookies
    cps_buff = descendant.cps() - ancestor.cps()
    if price <= 0 or cps_buff <= 0:
        return float("inf")
    return price * descendant.cps() / cps_buff


def find_route(
    initial_gamestate,
    target,
    on_purchase=None,
    price_cutoff_multiplier=2.0,
):
    return find_greedy_route(
        initial_gamestate,
        descendant_score,
        target=target,
        on_purchase=on_purchase,
        price_cutoff_multiplier=price_cutoff_multiplier,
    )
