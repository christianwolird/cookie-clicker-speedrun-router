"""Upgrade data for Cookie Clicker 2.031."""

from ..models import Upgrade


# Building upgrades double the named building. Their prices are the building's
# base price times 10, 50, and 500; they unlock at 1, 5, and 25 buildings.
UPGRADES = {
    "Reinforced index finger": Upgrade(
        100, (("Cursor", 1),), cursor_multiplier=2
    ),
    "Carpal tunnel prevention cream": Upgrade(
        500, (("Cursor", 1),), cursor_multiplier=2
    ),
    "Ambidextrous": Upgrade(
        10_000, (("Cursor", 10),), cursor_multiplier=2
    ),
    "Thousand fingers": Upgrade(
        100_000, (("Cursor", 25),), finger_add=0.1
    ),
    "Forwards from grandma": Upgrade(
        1_000, (("Grandma", 1),), building="Grandma"
    ),
    "Steel-plated rolling pins": Upgrade(
        5_000, (("Grandma", 5),), building="Grandma"
    ),
    "Lubricated dentures": Upgrade(
        50_000, (("Grandma", 25),), building="Grandma"
    ),
    "Cheap hoes": Upgrade(11_000, (("Farm", 1),), building="Farm"),
    "Fertilizer": Upgrade(55_000, (("Farm", 5),), building="Farm"),
    "Cookie trees": Upgrade(550_000, (("Farm", 25),), building="Farm"),
    "Sugar gas": Upgrade(120_000, (("Mine", 1),), building="Mine"),
    "Megadrill": Upgrade(600_000, (("Mine", 5),), building="Mine"),
    "Ultradrill": Upgrade(6_000_000, (("Mine", 25),), building="Mine"),
    "Sturdier conveyor belts": Upgrade(
        1_300_000, (("Factory", 1),), building="Factory"
    ),
    "Child labor": Upgrade(
        6_500_000, (("Factory", 5),), building="Factory"
    ),
    "Sweatshop": Upgrade(
        65_000_000, (("Factory", 25),), building="Factory"
    ),
    # Grandma synergies unlock with 15 of the other building and 1 grandma.
    "Farmer grandmas": Upgrade(
        55_000,
        (("Grandma", 1), ("Farm", 15)),
        grandma_synergy="Farm",
    ),
    "Miner grandmas": Upgrade(
        600_000,
        (("Grandma", 1), ("Mine", 15)),
        grandma_synergy="Mine",
    ),
    "Worker grandmas": Upgrade(
        6_500_000,
        (("Grandma", 1), ("Factory", 15)),
        grandma_synergy="Factory",
    ),
    "Plain cookies": Upgrade(
        999_999, production_multiplier=1.01, cookies_required=999_999 / 20
    ),
    "Plastic mouse": Upgrade(
        50_000, mouse_cps_fraction=0.01, handmade_required=1_000
    ),
    "Iron mouse": Upgrade(
        5_000_000, mouse_cps_fraction=0.01, handmade_required=100_000
    ),
    "Kitten helpers": Upgrade(
        9_000_000, kitten_coefficient=0.1
    ),
    "Kitten workers": Upgrade(
        9_000_000_000, kitten_coefficient=0.125
    ),
}


SPREADSHEET_UPGRADE_FAMILIES = {
    "Cursor": (
        "Reinforced index finger",
        "Carpal tunnel prevention cream",
        "Ambidextrous",
        "Thousand fingers",
    ),
    "Grandma": (
        "Forwards from grandma",
        "Steel-plated rolling pins",
        "Lubricated dentures",
    ),
    "Farm": ("Cheap hoes", "Fertilizer", "Cookie trees"),
    "Mine": ("Sugar gas", "Megadrill", "Ultradrill"),
    "Factory": ("Sturdier conveyor belts", "Child labor", "Sweatshop"),
    "Mouse": ("Plastic mouse", "Iron mouse"),
    "Grandma synergy": (
        "Farmer grandmas",
        "Miner grandmas",
        "Worker grandmas",
    ),
    "Cookie": ("Plain cookies",),
    "Kitten": ("Kitten helpers", "Kitten workers"),
}
