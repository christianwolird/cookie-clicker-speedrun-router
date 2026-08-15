from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Building:
    name: str
    base_price: int
    base_cps: float


building_stats = {
    "Cursor": Building(
        "Cursor",
        15,
        0.1,
    ),
    "Grandma": Building(
        "Grandma",
        100,
        1,
    ),
    "Farm": Building(
        "Farm",
        1_100,
        8,
    ),
    "Mine": Building(
        "Mine",
        12_000,
        47,
    ),
    "Factory": Building(
        "Factory",
        130_000,
        260,
    ),
    "Bank": Building(
        "Bank",
        1_400_000,
        1_400,
    ),
    "Temple": Building(
        "Temple",
        20_000_000,
        7_800,
    ),
    "Wizard Tower": Building(
        "Wizard Tower",
        330_000_000,
        44_000,
    ),
    "Shipment": Building(
        "Shipment",
        5_100_000_000,
        260_000,
    ),
    "Alchemy Lab": Building(
        "Alchemy Lab",
        75_000_000_000,
        1_600_000,
    ),
    "Portal": Building(
        "Portal",
        1_000_000_000_000,
        10_000_000,
    ),
    "Time Machine": Building(
        "Time Machine",
        14_000_000_000_000,
        65_000_000,
    ),
    "Antimatter Condenser": Building(
        "Antimatter Condenser",
        170_000_000_000_000,
        430_000_000,
    ),
    "Prism": Building(
        "Prism",
        2_100_000_000_000_000,
        2_900_000_000,
    ),
    "Chancemaker": Building(
        "Chancemaker",
        26_000_000_000_000_000,
        21_000_000_000,
    ),
    "Fractal Engine": Building(
        "Fractal Engine",
        310_000_000_000_000_000,
        150_000_000_000,
    ),
    "Javascript Console": Building(
        "Javascript Console",
        71_000_000_000_000_000_000,
        1_100_000_000_000,
    ),
    "Idleverse": Building(
        "Idleverse",
        12_000_000_000_000_000_000_000,
        8_300_000_000_000,
    ),
    "Cortex Baker": Building(
        "Cortex Baker",
        1_900_000_000_000_000_000_000_000,
        64_000_000_000_000,
    ),
    "You": Building(
        "You",
        540_000_000_000_000_000_000_000_000,
        510_000_000_000_000,
    ),
}
