"""Building data for Cookie Clicker 1.0466."""

from ..models import Building


BUILDINGS = {
    "Cursor": Building(15, 0.1),
    "Grandma": Building(100, 0.5),
    "Farm": Building(500, 4),
    "Factory": Building(3_000, 10),
    "Mine": Building(10_000, 40),
    "Shipment": Building(40_000, 100),
    "Alchemy Lab": Building(200_000, 400),
    "Portal": Building(1_666_666, 6_666),
    "Time Machine": Building(123_456_789, 98_765),
    "Antimatter Condenser": Building(3_999_999_999, 999_999),
    "Prism": Building(75_000_000_000, 10_000_000),
}
