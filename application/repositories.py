from abc import ABC, abstractmethod
from typing import Optional, List
from decimal import Decimal

from domain.entities import Merchant, Balance, Transfer


class IMerchantRepository(ABC):
    @abstractmethod
    async def create(self, merchant: Merchant) -> Merchant:
        pass
    
    @abstractmethod
    async def get_by_name(self, name: str) -> Optional[Merchant]:
        pass
    
    @abstractmethod
    async def exists(self, name: str) -> bool:
        pass


class IBalanceRepository(ABC):
    @abstractmethod
    async def create(self, balance: Balance) -> Balance:
        pass
    
    @abstractmethod
    async def get(self, merchant_name: str, currency: str) -> Optional[Balance]:
        pass
    
    @abstractmethod
    async def update(self, balance: Balance) -> Balance:
        pass
    
    @abstractmethod
    async def get_all_for_merchant(self, merchant_name: str) -> List[Balance]:
        pass
    
    @abstractmethod
    async def add_amount(
        self, 
        merchant_name: str, 
        currency: str, 
        amount: Decimal
    ) -> Balance:
        pass
    
    @abstractmethod
    async def subtract_amount(
        self,
        merchant_name: str,
        currency: str,
        amount: Decimal
    ) -> Balance:
        pass


class ITransferRepository(ABC):
    @abstractmethod
    async def create(self, transfer: Transfer) -> Transfer:
        pass
    
    @abstractmethod
    async def get_by_idempotency_key(
        self, 
        idempotency_key: str
    ) -> Optional[Transfer]:
        pass
    
    @abstractmethod
    async def list(
        self,
        from_merchant: Optional[str] = None,
        to_merchant: Optional[str] = None,
        currency: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Transfer]:
        pass


class IIdempotencyRepository(ABC):
    @abstractmethod
    async def store(
        self,
        idempotency_key: str,
        transfer_id: int,
        response_data: dict
    ) -> None:
        pass
    
    @abstractmethod
    async def get(self, idempotency_key: str) -> Optional[dict]:
        pass

