from pydantic import BaseModel, Field, field_validator
from decimal import Decimal
from typing import Optional, List


class CreateMerchantRequest(BaseModel):
    merchant_name: str = Field(..., min_length=1, max_length=255)
    currency: str = Field(..., min_length=1, max_length=10)
    initial_balance: str = Field(..., description="Initial balance as string")
    
    @field_validator('initial_balance')
    @classmethod
    def validate_balance(cls, v: str) -> str:
        try:
            balance = Decimal(v)
            if balance < 0:
                raise ValueError("Initial balance cannot be negative")
            return v
        except (ValueError, Exception):
            raise ValueError("Invalid balance format")


class MerchantResponse(BaseModel):
    merchant_name: str
    created_at: str
    balances: List[dict]


class BalanceResponse(BaseModel):
    merchant_name: str
    currency: Optional[str] = None
    amount: Optional[str] = None
    balances: Optional[List[dict]] = None


class TransferRequest(BaseModel):
    from_merchant: str = Field(..., min_length=1, max_length=255)
    to_merchant: str = Field(..., min_length=1, max_length=255)
    currency: str = Field(..., min_length=1, max_length=10)
    amount: str = Field(..., description="Transfer amount as string")
    
    @field_validator('amount')
    @classmethod
    def validate_amount(cls, v: str) -> str:
        try:
            amount = Decimal(v)
            if amount <= 0:
                raise ValueError("Transfer amount must be positive")
            return v
        except (ValueError, Exception):
            raise ValueError("Invalid amount format")


class TransferResponse(BaseModel):
    transfer_id: int
    from_merchant: str
    to_merchant: str
    currency: str
    amount: str
    fee: str
    created_at: str
    is_duplicate: bool = False
    message: Optional[str] = None


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None


class TransferListItem(BaseModel):
    transfer_id: int
    from_merchant: str
    to_merchant: str
    currency: str
    amount: str
    fee: str
    created_at: str


class TransferListResponse(BaseModel):
    transfers: List[TransferListItem]
    total: int

