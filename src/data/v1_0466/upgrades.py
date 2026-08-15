"""Upgrade data for Cookie Clicker 1.0466."""

from ..models import Upgrade


UPGRADES = {}
UPGRADE_FAMILIES = {}


def _add_building_tiers(building, prices, requirements):
    names = []
    for tier, (price, requirement) in enumerate(zip(prices, requirements), 1):
        name = f"{building} upgrade #{tier}"
        UPGRADES[name] = Upgrade(
            int(price),
            ((building, requirement),),
            building=building,
        )
        names.append(name)
    UPGRADE_FAMILIES[building] = tuple(names)


cursor_prices = (
    100,
    400,
    10_000,
    500_000,
    50_000_000,
    500_000_000,
    5_000_000_000,
    50_000_000_000,
)
cursor_requirements = (1, 1, 10, 20, 40, 80, 120, 160)
cursor_finger_add = (0, 0, 0, 0.1, 0.4, 4.5, 45, 450)
cursor_names = []
for tier, (price, requirement, finger_add) in enumerate(
    zip(cursor_prices, cursor_requirements, cursor_finger_add),
    1,
):
    name = f"Cursor upgrade #{tier}"
    UPGRADES[name] = Upgrade(
        price,
        (("Cursor", requirement),),
        cursor_multiplier=2 if tier <= 3 else 1,
        finger_add=finger_add,
    )
    cursor_names.append(name)
UPGRADE_FAMILIES["Cursor"] = tuple(cursor_names)


building_tiers = {
    "Grandma": (
        (1_000, 10_000, 100_000, 5_000_000, 100_000_000, 800_000_000),
        (1, 1, 10, 50, 100, 200),
    ),
    "Farm": (
        (5_000, 50_000, 500_000, 25_000_000, 500_000_000),
        (1, 1, 10, 50, 100),
    ),
    "Factory": (
        (30_000, 300_000, 3_000_000, 150_000_000, 3_000_000_000),
        (1, 1, 10, 50, 100),
    ),
    "Mine": (
        (100_000, 1_000_000, 10_000_000, 500_000_000, 10_000_000_000),
        (1, 1, 10, 50, 100),
    ),
    "Shipment": (
        (400_000, 4_000_000, 40_000_000, 2_000_000_000, 40_000_000_000),
        (1, 1, 10, 50, 100),
    ),
    "Alchemy Lab": (
        (2_000_000, 20_000_000, 200_000_000, 10_000_000_000, 200_000_000_000),
        (1, 1, 10, 50, 100),
    ),
    "Portal": (
        (16_667_000, 166_667_000, 1_667_000_000, 83_333_000_000),
        (1, 1, 10, 50),
    ),
    "Time Machine": (
        (1_235_000_000, 9_877_000_000, 98_765_000_000),
        (1, 1, 10),
    ),
    "Antimatter Condenser": (
        (40_000_000_000, 400_000_000_000),
        (1, 1),
    ),
    "Prism": ((750_000_000_000,), (1,)),
}
for building, (prices, requirements) in building_tiers.items():
    _add_building_tiers(building, prices, requirements)


mouse_names = []
for tier, (price, handmade) in enumerate(
    zip(
        (50_000, 5_000_000, 500_000_000, 50_000_000_000),
        (1_000, 100_000, 10_000_000, 1_000_000_000),
    ),
    1,
):
    name = f"Mouse upgrade #{tier}"
    UPGRADES[name] = Upgrade(
        price,
        mouse_cps_fraction=0.01,
        handmade_required=handmade,
    )
    mouse_names.append(name)
UPGRADE_FAMILIES["Mouse"] = tuple(mouse_names)


synergy_names = []
synergy_buildings = (
    "Farm",
    "Factory",
    "Mine",
    "Shipment",
    "Alchemy Lab",
    "Portal",
    "Time Machine",
    "Antimatter Condenser",
)
synergy_prices = (
    50_000,
    300_000,
    1_000_000,
    4_000_000,
    20_000_000,
    166_667_000,
    12_346_000_000,
    400_000_000_000,
)
for tier, (building, price) in enumerate(
    zip(synergy_buildings, synergy_prices),
    1,
):
    name = f"Grandma synergy #{tier} ({building})"
    UPGRADES[name] = Upgrade(
        price,
        (("Grandma", 1), (building, 15)),
        grandma_synergy=building,
    )
    synergy_names.append(name)
UPGRADE_FAMILIES["Grandma synergy"] = tuple(synergy_names)


cookie_names = []
cookie_prices = (
    100_000_000,
    100_000_000,
    100_000_000,
    100_000_000,
    1_000_000_000,
    1_000_000_000,
    1_000_000_000,
    100_000_000_000,
    100_000_000_000,
    100_000_000_000,
)
previous_multiplier = 1.0
for tier, price in enumerate(cookie_prices, 1):
    total_multiplier = 1 + (
        0.05 * tier if tier < 8 else 0.35 + 0.1 * (tier - 7)
    )
    name = f"Cookie upgrade #{tier}"
    UPGRADES[name] = Upgrade(
        price,
        production_multiplier=total_multiplier / previous_multiplier,
    )
    previous_multiplier = total_multiplier
    cookie_names.append(name)
UPGRADE_FAMILIES["Cookie"] = tuple(cookie_names)
