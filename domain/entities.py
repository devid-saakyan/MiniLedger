from decimal import Decimal
from typing import Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Merchant:
    name: str
    created_at: datetime
    
    def __post_init__(self):
        if not self.name:
            raise ValueError("Merchant name cannot be empty")


@dataclass
class Balance:
    merchant_name: str
    currency: str
    amount: Decimal
    
    def __post_init__(self):
        if self.amount < 0:
            raise ValueError("Balance cannot be negative")
        if not self.currency:
            raise ValueError("Currency cannot be empty")


@dataclass
class Transfer:
    id: Optional[int]
    from_merchant: str
    to_merchant: str
    currency: str
    amount: Decimal
    fee: Decimal
    idempotency_key: str
    created_at: datetime
    
    def __post_init__(self):
        if self.amount <= 0:
            raise ValueError("Transfer amount must be positive")
        if self.fee < 0:
            raise ValueError("Transfer fee cannot be negative")
        if not self.idempotency_key:
            raise ValueError("Idempotency key is required")
        if self.from_merchant == self.to_merchant:
            raise ValueError("Cannot transfer to the same merchant")
    
    @property
    def total_debit(self) -> Decimal:
        return self.amount + self.fee

