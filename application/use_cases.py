from decimal import Decimal
from typing import Optional, List
from datetime import datetime

from domain.entities import Merchant, Balance, Transfer
from domain.services import FeeCalculator
from domain.exceptions import (
    MerchantNotFoundError,
    InsufficientFundsError,
    InvalidTransferError,
    DuplicateIdempotencyKeyError
)
from application.repositories import (
    IMerchantRepository,
    IBalanceRepository,
    ITransferRepository,
    IIdempotencyRepository
)


class CreateMerchantUseCase:
    def __init__(
        self,
        merchant_repo: IMerchantRepository,
        balance_repo: IBalanceRepository
    ):
        self.merchant_repo = merchant_repo
        self.balance_repo = balance_repo
    
    async def execute(
        self,
        merchant_name: str,
        currency: str,
        initial_balance: Decimal
    ) -> Merchant:
        if initial_balance < 0:
            raise ValueError("Initial balance cannot be negative")
        
        existing = await self.merchant_repo.get_by_name(merchant_name)
        if existing:
            raise ValueError(f"Merchant '{merchant_name}' already exists")
        
        merchant = Merchant(
            name=merchant_name,
            created_at=datetime.utcnow()
        )
        merchant = await self.merchant_repo.create(merchant)
        
        if initial_balance > 0:
            balance = Balance(
                merchant_name=merchant_name,
                currency=currency,
                amount=initial_balance
            )
            await self.balance_repo.create(balance)
        
        return merchant


class GetMerchantUseCase:
    def __init__(
        self,
        merchant_repo: IMerchantRepository,
        balance_repo: IBalanceRepository
    ):
        self.merchant_repo = merchant_repo
        self.balance_repo = balance_repo
    
    async def execute(self, merchant_name: str) -> dict:
        merchant = await self.merchant_repo.get_by_name(merchant_name)
        if not merchant:
            raise MerchantNotFoundError(f"Merchant '{merchant_name}' not found")
        
        balances = await self.balance_repo.get_all_for_merchant(merchant_name)
        
        return {
            "merchant_name": merchant.name,
            "created_at": merchant.created_at.isoformat(),
            "balances": [
                {
                    "currency": b.currency,
                    "amount": str(b.amount)
                }
                for b in balances
            ]
        }


class GetBalanceUseCase:
    def __init__(
        self,
        merchant_repo: IMerchantRepository,
        balance_repo: IBalanceRepository
    ):
        self.merchant_repo = merchant_repo
        self.balance_repo = balance_repo
    
    async def execute(
        self,
        merchant_name: str,
        currency: Optional[str] = None
    ) -> dict:
        merchant = await self.merchant_repo.get_by_name(merchant_name)
        if not merchant:
            raise MerchantNotFoundError(f"Merchant '{merchant_name}' not found")
        
        if currency:
            balance = await self.balance_repo.get(merchant_name, currency)
            if not balance:
                return {
                    "merchant_name": merchant_name,
                    "currency": currency,
                    "amount": "0"
                }
            return {
                "merchant_name": merchant_name,
                "currency": balance.currency,
                "amount": str(balance.amount)
            }
        else:
            balances = await self.balance_repo.get_all_for_merchant(merchant_name)
            return {
                "merchant_name": merchant_name,
                "balances": [
                    {
                        "currency": b.currency,
                        "amount": str(b.amount)
                    }
                    for b in balances
                ]
            }


class ExecuteTransferUseCase:
    def __init__(
        self,
        merchant_repo: IMerchantRepository,
        balance_repo: IBalanceRepository,
        transfer_repo: ITransferRepository,
        idempotency_repo: IIdempotencyRepository,
        fee_calculator: FeeCalculator
    ):
        self.merchant_repo = merchant_repo
        self.balance_repo = balance_repo
        self.transfer_repo = transfer_repo
        self.idempotency_repo = idempotency_repo
        self.fee_calculator = fee_calculator
    
    async def execute(
        self,
        from_merchant: str,
        to_merchant: str,
        currency: str,
        amount: Decimal,
        idempotency_key: str
    ) -> dict:
        stored_response = await self.idempotency_repo.get(idempotency_key)
        stored_response = await self.idempotency_repo.get(idempotency_key)
        if stored_response:
            return stored_response
        
        from_merchant_obj = await self.merchant_repo.get_by_name(from_merchant)
        if not from_merchant_obj:
            raise MerchantNotFoundError(f"Merchant '{from_merchant}' not found")
        
        to_merchant_obj = await self.merchant_repo.get_by_name(to_merchant)
        if not to_merchant_obj:
            raise MerchantNotFoundError(f"Merchant '{to_merchant}' not found")
        
        if from_merchant == to_merchant:
            raise InvalidTransferError("Cannot transfer to the same merchant")
        
        if amount <= 0:
            raise InvalidTransferError("Transfer amount must be positive")
        
        fee = self.fee_calculator.calculate_fee(amount)
        total_debit = amount + fee
        
        try:
            await self.balance_repo.subtract_amount(
                from_merchant,
                currency,
                total_debit
            )
            
            await self.balance_repo.add_amount(
                to_merchant,
                currency,
                amount
            )
        except ValueError as e:
            if "negative" in str(e).lower() or "insufficient" in str(e).lower():
                raise InsufficientFundsError(
                    f"Insufficient funds. Required: {total_debit} {currency}, "
                    f"including fee: {fee} {currency}"
                )
            raise
        
        transfer = Transfer(
            id=None,
            from_merchant=from_merchant,
            to_merchant=to_merchant,
            currency=currency,
            amount=amount,
            fee=fee,
            idempotency_key=idempotency_key,
            created_at=datetime.utcnow()
        )
        transfer = await self.transfer_repo.create(transfer)
        
        response_data = {
            "transfer_id": transfer.id,
            "from_merchant": from_merchant,
            "to_merchant": to_merchant,
            "currency": currency,
            "amount": str(amount),
            "fee": str(fee),
            "created_at": transfer.created_at.isoformat()
        }
        await self.idempotency_repo.store(
            idempotency_key,
            transfer.id,
            response_data
        )
        
        return response_data


class ListTransfersUseCase:
    def __init__(self, transfer_repo: ITransferRepository):
        self.transfer_repo = transfer_repo
    
    async def execute(
        self,
        from_merchant: Optional[str] = None,
        to_merchant: Optional[str] = None,
        currency: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[dict]:
        transfers = await self.transfer_repo.list(
            from_merchant=from_merchant,
            to_merchant=to_merchant,
            currency=currency,
            limit=limit,
            offset=offset
        )
        
        return [
            {
                "transfer_id": t.id,
                "from_merchant": t.from_merchant,
                "to_merchant": t.to_merchant,
                "currency": t.currency,
                "amount": str(t.amount),
                "fee": str(t.fee),
                "created_at": t.created_at.isoformat()
            }
            for t in transfers
        ]

