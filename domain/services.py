from decimal import Decimal
from typing import Protocol


class FeeCalculator(Protocol):
    def calculate_fee(self, amount: Decimal) -> Decimal:
        ...


class PercentageFeeCalculator:
    def __init__(self, fee_percent: float):
        if fee_percent < 0:
            raise ValueError("Fee percentage cannot be negative")
        self.fee_percent = Decimal(str(fee_percent))
    
    def calculate_fee(self, amount: Decimal) -> Decimal:
        if amount <= 0:
            raise ValueError("Amount must be positive")
        return (amount * self.fee_percent / Decimal("100")).quantize(
            Decimal("0.00000001")
        )

