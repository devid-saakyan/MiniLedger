from decimal import Decimal
from typing import Optional, List
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from domain.entities import Merchant, Balance, Transfer
from infrastructure.models import (
    MerchantModel,
    BalanceModel,
    TransferModel,
    IdempotencyKeyModel
)
from application.repositories import (
    IMerchantRepository,
    IBalanceRepository,
    ITransferRepository,
    IIdempotencyRepository
)


class MerchantRepository(IMerchantRepository):
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create(self, merchant: Merchant) -> Merchant:
        db_merchant = MerchantModel(
            name=merchant.name,
            created_at=merchant.created_at
        )
        self.session.add(db_merchant)
        await self.session.flush()
        await self.session.refresh(db_merchant)
        
        return Merchant(
            name=db_merchant.name,
            created_at=db_merchant.created_at
        )
    
    async def get_by_name(self, name: str) -> Optional[Merchant]:
        result = await self.session.execute(
            select(MerchantModel).where(MerchantModel.name == name)
        )
        db_merchant = result.scalar_one_or_none()
        
        if not db_merchant:
            return None
        
        return Merchant(
            name=db_merchant.name,
            created_at=db_merchant.created_at
        )
    
    async def exists(self, name: str) -> bool:
        result = await self.session.execute(
            select(func.count(MerchantModel.id)).where(MerchantModel.name == name)
        )
        count = result.scalar()
        return count > 0


class BalanceRepository(IBalanceRepository):
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create(self, balance: Balance) -> Balance:
        db_balance = BalanceModel(
            merchant_name=balance.merchant_name,
            currency=balance.currency,
            amount=balance.amount
        )
        self.session.add(db_balance)
        await self.session.flush()
        await self.session.refresh(db_balance)
        
        return Balance(
            merchant_name=db_balance.merchant_name,
            currency=db_balance.currency,
            amount=db_balance.amount
        )
    
    async def get(self, merchant_name: str, currency: str) -> Optional[Balance]:
        result = await self.session.execute(
            select(BalanceModel).where(
                BalanceModel.merchant_name == merchant_name,
                BalanceModel.currency == currency
            )
        )
        db_balance = result.scalar_one_or_none()
        
        if not db_balance:
            return None
        
        return Balance(
            merchant_name=db_balance.merchant_name,
            currency=db_balance.currency,
            amount=db_balance.amount
        )
    
    async def update(self, balance: Balance) -> Balance:
        await self.session.execute(
            update(BalanceModel)
            .where(
                BalanceModel.merchant_name == balance.merchant_name,
                BalanceModel.currency == balance.currency
            )
            .values(amount=balance.amount)
        )
        await self.session.flush()
        
        return balance
    
    async def get_all_for_merchant(self, merchant_name: str) -> List[Balance]:
        result = await self.session.execute(
            select(BalanceModel).where(BalanceModel.merchant_name == merchant_name)
        )
        db_balances = result.scalars().all()
        
        return [
            Balance(
                merchant_name=b.merchant_name,
                currency=b.currency,
                amount=b.amount
            )
            for b in db_balances
        ]
    
    async def add_amount(
        self,
        merchant_name: str,
        currency: str,
        amount: Decimal
    ) -> Balance:
        result = await self.session.execute(
            select(BalanceModel)
            .where(
                BalanceModel.merchant_name == merchant_name,
                BalanceModel.currency == currency
            )
            .with_for_update()
        )
        db_balance = result.scalar_one_or_none()
        
        if db_balance:
            new_amount = db_balance.amount + amount
            if new_amount < 0:
                raise ValueError("Balance cannot be negative")
            
            db_balance.amount = new_amount
            await self.session.flush()
            await self.session.refresh(db_balance)
            
            return Balance(
                merchant_name=db_balance.merchant_name,
                currency=db_balance.currency,
                amount=db_balance.amount
            )
        else:
            if amount < 0:
                raise ValueError("Balance cannot be negative")
            
            db_balance = BalanceModel(
                merchant_name=merchant_name,
                currency=currency,
                amount=amount
            )
            self.session.add(db_balance)
            await self.session.flush()
            await self.session.refresh(db_balance)
            
            return Balance(
                merchant_name=db_balance.merchant_name,
                currency=db_balance.currency,
                amount=db_balance.amount
            )
    
    async def subtract_amount(
        self,
        merchant_name: str,
        currency: str,
        amount: Decimal
    ) -> Balance:
        result = await self.session.execute(
            select(BalanceModel)
            .where(
                BalanceModel.merchant_name == merchant_name,
                BalanceModel.currency == currency
            )
            .with_for_update()
        )
        db_balance = result.scalar_one_or_none()
        
        if not db_balance:
            raise ValueError(f"Insufficient funds: no balance found for {merchant_name} in {currency}")
        
        new_amount = db_balance.amount - amount
        if new_amount < 0:
            raise ValueError(
                f"Insufficient funds: balance would become negative. "
                f"Current: {db_balance.amount}, Required: {amount}"
            )
        
        db_balance.amount = new_amount
        await self.session.flush()
        await self.session.refresh(db_balance)
        
        return Balance(
            merchant_name=db_balance.merchant_name,
            currency=db_balance.currency,
            amount=db_balance.amount
        )


class TransferRepository(ITransferRepository):
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create(self, transfer: Transfer) -> Transfer:
        db_transfer = TransferModel(
            from_merchant=transfer.from_merchant,
            to_merchant=transfer.to_merchant,
            currency=transfer.currency,
            amount=transfer.amount,
            fee=transfer.fee,
            idempotency_key=transfer.idempotency_key,
            created_at=transfer.created_at
        )
        self.session.add(db_transfer)
        await self.session.flush()
        await self.session.refresh(db_transfer)
        
        return Transfer(
            id=db_transfer.id,
            from_merchant=db_transfer.from_merchant,
            to_merchant=db_transfer.to_merchant,
            currency=db_transfer.currency,
            amount=db_transfer.amount,
            fee=db_transfer.fee,
            idempotency_key=db_transfer.idempotency_key,
            created_at=db_transfer.created_at
        )
    
    async def get_by_idempotency_key(
        self,
        idempotency_key: str
    ) -> Optional[Transfer]:
        result = await self.session.execute(
            select(TransferModel).where(
                TransferModel.idempotency_key == idempotency_key
            )
        )
        db_transfer = result.scalar_one_or_none()
        
        if not db_transfer:
            return None
        
        return Transfer(
            id=db_transfer.id,
            from_merchant=db_transfer.from_merchant,
            to_merchant=db_transfer.to_merchant,
            currency=db_transfer.currency,
            amount=db_transfer.amount,
            fee=db_transfer.fee,
            idempotency_key=db_transfer.idempotency_key,
            created_at=db_transfer.created_at
        )
    
    async def list(
        self,
        from_merchant: Optional[str] = None,
        to_merchant: Optional[str] = None,
        currency: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Transfer]:
        query = select(TransferModel)
        
        if from_merchant:
            query = query.where(TransferModel.from_merchant == from_merchant)
        if to_merchant:
            query = query.where(TransferModel.to_merchant == to_merchant)
        if currency:
            query = query.where(TransferModel.currency == currency)
        
        query = query.order_by(TransferModel.created_at.desc())
        query = query.limit(limit).offset(offset)
        
        result = await self.session.execute(query)
        db_transfers = result.scalars().all()
        
        return [
            Transfer(
                id=t.id,
                from_merchant=t.from_merchant,
                to_merchant=t.to_merchant,
                currency=t.currency,
                amount=t.amount,
                fee=t.fee,
                idempotency_key=t.idempotency_key,
                created_at=t.created_at
            )
            for t in db_transfers
        ]


class IdempotencyRepository(IIdempotencyRepository):
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def store(
        self,
        idempotency_key: str,
        transfer_id: int,
        response_data: dict
    ) -> None:
        db_key = IdempotencyKeyModel(
            idempotency_key=idempotency_key,
            transfer_id=transfer_id,
            response_data=response_data
        )
        self.session.add(db_key)
        await self.session.flush()
    
    async def get(self, idempotency_key: str) -> Optional[dict]:
        result = await self.session.execute(
            select(IdempotencyKeyModel).where(
                IdempotencyKeyModel.idempotency_key == idempotency_key
            )
        )
        db_key = result.scalar_one_or_none()
        
        if not db_key:
            return None
        
        return db_key.response_data

