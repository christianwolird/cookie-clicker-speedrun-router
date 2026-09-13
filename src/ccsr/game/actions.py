"""Executable shop clicks, with expected quantities for bulk transactions."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RouteAction:
    operation: str
    item: str
    quantity: int = 1

    def __post_init__(self):
        if self.operation not in {"buy", "sell", "upgrade"}:
            raise ValueError(f"Unknown route operation: {self.operation}")
        if not isinstance(self.quantity, int) or self.quantity <= 0:
            raise ValueError("Action quantity must be a positive integer")
        if self.operation == "upgrade" and self.quantity != 1:
            raise ValueError("An upgrade action must have quantity 1")

    @classmethod
    def from_purchase(cls, purchase):
        return cls(purchase.operation, purchase.item, purchase.quantity)

    def __str__(self):
        suffix = f" x{self.quantity}" if self.quantity != 1 else ""
        return f"{self.operation} {self.item}{suffix}"
