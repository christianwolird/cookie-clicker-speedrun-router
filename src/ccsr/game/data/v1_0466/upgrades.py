"""Upgrade data for Cookie Clicker 1.0466."""

from ..models import Upgrade


UPGRADES = {}
SPREADSHEET_UPGRADE_FAMILIES = {}


def _add_building_tiers(building, names, prices, requirements):
    for name, price, requirement in zip(names, prices, requirements):
        UPGRADES[name] = Upgrade(
            int(price),
            ((building, requirement),),
            building=building,
        )
    SPREADSHEET_UPGRADE_FAMILIES[building] = names


cursor_names = (
    "Reinforced index finger",
    "Carpal tunnel prevention cream",
    "Ambidextrous",
    "Thousand fingers",
    "Million fingers",
    "Billion fingers",
    "Trillion fingers",
    "Quadrillion fingers",
)
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
for tier, (name, price, requirement, finger_add) in enumerate(
    zip(
        cursor_names,
        cursor_prices,
        cursor_requirements,
        cursor_finger_add,
    ),
    1,
):
    UPGRADES[name] = Upgrade(
        price,
        (("Cursor", requirement),),
        cursor_multiplier=2 if tier <= 3 else 1,
        finger_add=finger_add,
    )
SPREADSHEET_UPGRADE_FAMILIES["Cursor"] = cursor_names


building_tiers = {
    "Grandma": (
        (
            "Forwards from grandma",
            "Steel-plated rolling pins",
            "Lubricated dentures",
            "Prune juice",
            "Double-thick glasses",
            "Aging agents",
        ),
        (1_000, 10_000, 100_000, 5_000_000, 100_000_000, 800_000_000),
        (1, 1, 10, 50, 100, 200),
    ),
    "Farm": (
        (
            "Cheap hoes",
            "Fertilizer",
            "Cookie trees",
            "Genetically-modified cookies",
            "Gingerbread scarecrows",
        ),
        (5_000, 50_000, 500_000, 25_000_000, 500_000_000),
        (1, 1, 10, 50, 100),
    ),
    "Factory": (
        (
            "Sturdier conveyor belts",
            "Child labor",
            "Sweatshop",
            "Radium reactors",
            "Recombobulators",
        ),
        (30_000, 300_000, 3_000_000, 150_000_000, 3_000_000_000),
        (1, 1, 10, 50, 100),
    ),
    "Mine": (
        (
            "Sugar gas",
            "Megadrill",
            "Ultradrill",
            "Ultimadrill",
            "H-bomb mining",
        ),
        (100_000, 1_000_000, 10_000_000, 500_000_000, 10_000_000_000),
        (1, 1, 10, 50, 100),
    ),
    "Shipment": (
        (
            "Vanilla nebulae",
            "Wormholes",
            "Frequent flyer",
            "Warp drive",
            "Chocolate monoliths",
        ),
        (400_000, 4_000_000, 40_000_000, 2_000_000_000, 40_000_000_000),
        (1, 1, 10, 50, 100),
    ),
    "Alchemy Lab": (
        (
            "Antimony",
            "Essence of dough",
            "True chocolate",
            "Ambrosia",
            "Aqua crustulae",
        ),
        (
            2_000_000,
            20_000_000,
            200_000_000,
            10_000_000_000,
            200_000_000_000,
        ),
        (1, 1, 10, 50, 100),
    ),
    "Portal": (
        (
            "Ancient tablet",
            "Insane oatling workers",
            "Soul bond",
            "Sanity dance",
        ),
        (16_667_000, 166_667_000, 1_667_000_000, 83_333_000_000),
        (1, 1, 10, 50),
    ),
    "Time Machine": (
        (
            "Flux capacitors",
            "Time paradox resolver",
            "Quantum conundrum",
        ),
        (1_235_000_000, 9_877_000_000, 98_765_000_000),
        (1, 1, 10),
    ),
    "Antimatter Condenser": (
        ("Sugar bosons", "String theory"),
        (40_000_000_000, 400_000_000_000),
        (1, 1),
    ),
    "Prism": (("Gem polish",), (750_000_000_000,), (1,)),
}
for building, (names, prices, requirements) in building_tiers.items():
    _add_building_tiers(building, names, prices, requirements)


mouse_names = (
    "Plastic mouse",
    "Iron mouse",
    "Titanium mouse",
    "Adamantium mouse",
)
for name, price, handmade in zip(
    mouse_names,
    (50_000, 5_000_000, 500_000_000, 50_000_000_000),
    (1_000, 100_000, 10_000_000, 1_000_000_000),
):
    UPGRADES[name] = Upgrade(
        price,
        mouse_cps_fraction=0.01,
        handmade_required=handmade,
    )
SPREADSHEET_UPGRADE_FAMILIES["Mouse"] = mouse_names


synergy_names = (
    "Farmer grandmas",
    "Worker grandmas",
    "Miner grandmas",
    "Cosmic grandmas",
    "Transmuted grandmas",
    "Altered grandmas",
    "Grandmas' grandmas",
    "Antigrandmas",
)
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
for name, building, price in zip(
    synergy_names,
    synergy_buildings,
    synergy_prices,
):
    UPGRADES[name] = Upgrade(
        price,
        (("Grandma", 1), (building, 15)),
        grandma_synergy=building,
    )
SPREADSHEET_UPGRADE_FAMILIES["Grandma synergy"] = synergy_names


cookie_names = (
    "Oatmeal raisin cookies",
    "Peanut butter cookies",
    "Plain cookies",
    "Sugar cookies",
    "Coconut cookies",
    "White chocolate cookies",
    "Macadamia nut cookies",
    "Double-chip cookies",
    "White chocolate macadamia nut cookies",
    "All-chocolate cookies",
)
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
for tier, (name, price) in enumerate(zip(cookie_names, cookie_prices), 1):
    total_multiplier = 1 + (
        0.05 * tier if tier < 8 else 0.35 + 0.1 * (tier - 7)
    )
    UPGRADES[name] = Upgrade(
        price,
        production_multiplier=total_multiplier / previous_multiplier,
    )
    previous_multiplier = total_multiplier
SPREADSHEET_UPGRADE_FAMILIES["Cookie"] = cookie_names
