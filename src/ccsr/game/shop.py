"""Fixed-mode errands with grouped timing and exact bulk affordability.

Production uses the ancestor inventory throughout the shop pause. Sales close
first, followed by purchases, at the common completion time. No purchase-order
production bonuses are introduced: x1 errands remain unordered.
"""

from collections import Counter
from math import isfinite

from .actions import RouteAction
from .gamestate import Purchase


def canonical_actions(gamestate, actions):
    """Normalize x1 permutations and the sale prefix; retain x10 purchase order."""
    actions = tuple(actions)
    if not actions:
        raise ValueError("An errand must contain at least one action")
    if gamestate.bulk_size not in (1, 10):
        raise ValueError("bulk_size must be 1 or 10")
    sales = Counter()
    purchases = []
    upgrades = set()
    buying_started = False
    for action in actions:
        if action.operation == "sell":
            if not gamestate.selling_allowed:
                raise ValueError("Sales are disabled by the errand profile")
            if gamestate.bulk_size == 10 and buying_started:
                raise ValueError("Sales must precede purchases in a bulk errand")
            sales[action.item] += action.quantity
        else:
            buying_started = True
            if action.operation == "upgrade":
                if action.item in upgrades:
                    raise ValueError("An upgrade cannot occur twice in one errand")
                upgrades.add(action.item)
            if action.quantity > gamestate.bulk_size:
                raise ValueError("Purchase quantity exceeds the fixed bulk size")
            purchases.append(action)

    prefix = []
    for name, quantity in sorted(sales.items()):
        owned = gamestate.building_counts[name]
        if quantity > owned:
            raise ValueError(f"Cannot sell {quantity} owned {name}")
        while quantity:
            clicked = min(gamestate.bulk_size, owned)
            if quantity < clicked:
                raise ValueError(f"A x{gamestate.bulk_size} sale of {name} sells {clicked}")
            prefix.append(RouteAction("sell", name, clicked))
            quantity -= clicked
            owned -= clicked
    if gamestate.bulk_size == 1:
        purchases.sort(key=lambda action: (action.operation == "upgrade", action.item))
    return tuple(prefix + purchases)


def _transaction_costs(gamestate, actions):
    inventory = gamestate.copy()
    cost = refund = 0
    for action in actions:
        name, quantity = action.item, action.quantity
        if action.operation == "sell":
            refund += inventory.building_sale_refund(name, quantity)
            inventory.building_counts[name] -= quantity
        elif action.operation == "buy":
            cost += inventory.building_group_price(name, quantity)
            inventory.building_counts[name] += quantity
        else:
            if not gamestate.upgrades_allowed:
                raise ValueError("Upgrades are disabled")
            if name in gamestate.purchased_upgrades:
                raise ValueError(f"Upgrade already purchased: {name}")
            cost += inventory.upgrade_catalog[name].price
    return cost, refund


def sticker_price(gamestate, actions):
    actions = canonical_actions(gamestate, actions)
    cost, refund = _transaction_costs(gamestate, actions)
    return cost - refund


def execute_shop_errand(gamestate, actions):
    """Return a child and click records, without mutating the ancestor.

    Save only what this errand needs after its refunds and existing bank. The
    printed bank requirement is the net sticker price (before selling), not
    newly baked cookies. Excess refunds or unavoidable pause production carry
    forward. A partial bulk click must buy exactly its recorded quantity.
    """
    actions = canonical_actions(gamestate, actions)
    cost, refund = _transaction_costs(gamestate, actions)
    sale_count = sum(action.operation == "sell" for action in actions)
    action_count = len(actions) + (2 if sale_count else 0)
    if any(not isfinite(value) or value < 0 for value in (
        gamestate.errand_delay, gamestate.action_delay, gamestate.bank,
    )):
        raise ValueError("Shop delays and bank must be finite and nonnegative")
    pause = gamestate.errand_delay + action_count * gamestate.action_delay
    required = max(0, cost - refund)
    needed = max(0, required - gamestate.bank)
    automatic = gamestate.automatic_cps()
    hand = gamestate.hand_cps()
    if automatic + hand <= 0:
        if needed:
            raise ValueError("Cannot earn cookies with zero CpS")
        duration = pause
    else:
        duration = max(pause, (needed + hand * pause) / (automatic + hand))
    # This branch avoids floating-point affordability errors at exact prices.
    produced = max(needed, automatic * pause)
    child = gamestate.copy()
    child.age += duration
    child.lifetime_cookies += produced
    child.handmade_cookies += hand * max(0, duration - pause)
    child.bank += produced
    child._automatic_cps_cache = None
    child._automatic_cps_cache_achievement_count = None

    labels = []
    for action in actions:
        name, quantity = action.item, action.quantity
        if action.operation == "sell":
            child.bank += child.building_sale_refund(name, quantity)
            child.building_counts[name] -= quantity
            label = f"Sell {name} ×{quantity}"
        elif action.operation == "buy":
            price = child.building_group_price(name, quantity)
            if price > child.bank:
                raise ValueError(f"Cannot afford {name} x{quantity}")
            if quantity < child.bulk_size and (
                child.building_group_price(name, quantity + 1) <= child.bank
            ):
                raise ValueError(
                    f"A x{child.bulk_size} click buys more than {quantity} {name}"
                )
            child.bank -= price
            child.building_counts[name] += quantity
            label = (
                f"{name} ×{quantity}"
                if child.bulk_size == 10
                else f"{name} #{child.building_counts[name]}"
            )
        else:
            if not child.upgrade_unlocked(name):
                raise ValueError(f"Upgrade is still locked: {name}")
            price = child.upgrade_catalog[name].price
            if price > child.bank:
                raise ValueError(f"Cannot afford upgrade: {name}")
            child.bank -= price
            child.purchased_upgrades.add(name)
            label = name
        child._automatic_cps_cache = None
        child._automatic_cps_cache_achievement_count = None
        labels.append(label)
    purchases = tuple(
        Purchase(
            action.operation, action.item, child.age, child.lifetime_cookies,
            child.cps(), label, action.quantity, required, child.bank, action_count,
        )
        for action, label in zip(actions, labels)
    )
    return child, purchases
