"""Achievement data for Cookie Clicker 2.031."""

from ..models import Achievement


ACHIEVEMENTS = {
    # Cookies baked in one ascension.
    "Wake and bake": Achievement("cookies", 1),
    "Making some dough": Achievement("cookies", 1_000),
    "So baked right now": Achievement("cookies", 100_000),
    "Fledgling bakery": Achievement("cookies", 1_000_000),
    # Building CpS (manual clicking does not count).
    "Casual baking": Achievement("cps", 1),
    "Hardcore baking": Achievement("cps", 10),
    "Steady tasty stream": Achievement("cps", 100),
    "Cookie monster": Achievement("cps", 1_000),
    # Cookies made by clicking.
    "Clicktastic": Achievement("handmade", 1_000),
    "Clickathlon": Achievement("handmade", 100_000),
    # Early building milestones that can contribute milk on a million run.
    "Click": Achievement("building", 1, "Cursor"),
    "Double-click": Achievement("building", 2, "Cursor"),
    "Mouse wheel": Achievement("building", 50, "Cursor"),
    "Of Mice and Men": Achievement("building", 100, "Cursor"),
    "Grandma's cookies": Achievement("building", 1, "Grandma"),
    "Sloppy kisses": Achievement("building", 50, "Grandma"),
    "Retirement home": Achievement("building", 100, "Grandma"),
    "Bought the farm": Achievement("building", 1, "Farm"),
    "Reap what you sow": Achievement("building", 50, "Farm"),
    "Farm ill": Achievement("building", 100, "Farm"),
    "You know the drill": Achievement("building", 1, "Mine"),
    "Excavation site": Achievement("building", 50, "Mine"),
    "Hollow the planet": Achievement("building", 100, "Mine"),
    "Production chain": Achievement("building", 1, "Factory"),
    "Industrial revolution": Achievement("building", 50, "Factory"),
    "Global warming": Achievement("building", 100, "Factory"),
    "Pretty penny": Achievement("building", 1, "Bank"),
    "Builder": Achievement("buildings", 100),
    "Enhancer": Achievement("upgrades", 20),
}
