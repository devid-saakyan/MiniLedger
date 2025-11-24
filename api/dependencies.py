from sqlalchemy.ext.asyncio import AsyncSession
from infrastructure.database import get_db
from infrastructure.repositories import (
    MerchantRepository,
    BalanceRepository,
    TransferRepository,
    IdempotencyRepository
)
from domain.services import PercentageFeeCalculator
from config import settings
from application.use_cases import (
    CreateMerchantUseCase,
    GetMerchantUseCase,
    GetBalanceUseCase,
    ExecuteTransferUseCase,
    ListTransfersUseCase
)


async def get_merchant_repo(session: AsyncSession = None) -> MerchantRepository:
    if session is None:
        async for s in get_db():
            session = s
            break
    return MerchantRepository(session)


async def get_balance_repo(session: AsyncSession = None) -> BalanceRepository:
    if session is None:
        async for s in get_db():
            session = s
            break
    return BalanceRepository(session)


async def get_transfer_repo(session: AsyncSession = None) -> TransferRepository:
    if session is None:
        async for s in get_db():
            session = s
            break
    return TransferRepository(session)


async def get_idempotency_repo(session: AsyncSession = None) -> IdempotencyRepository:
    if session is None:
        async for s in get_db():
            session = s
            break
    return IdempotencyRepository(session)


def get_fee_calculator() -> PercentageFeeCalculator:
    return PercentageFeeCalculator(settings.transfer_fee_percent)


async def get_create_merchant_use_case(
    session: AsyncSession
) -> CreateMerchantUseCase:
    merchant_repo = MerchantRepository(session)
    balance_repo = BalanceRepository(session)
    return CreateMerchantUseCase(merchant_repo, balance_repo)


async def get_get_merchant_use_case(
    session: AsyncSession
) -> GetMerchantUseCase:
    merchant_repo = MerchantRepository(session)
    balance_repo = BalanceRepository(session)
    return GetMerchantUseCase(merchant_repo, balance_repo)


async def get_get_balance_use_case(
    session: AsyncSession
) -> GetBalanceUseCase:
    merchant_repo = MerchantRepository(session)
    balance_repo = BalanceRepository(session)
    return GetBalanceUseCase(merchant_repo, balance_repo)


async def get_execute_transfer_use_case(
    session: AsyncSession
) -> ExecuteTransferUseCase:
    merchant_repo = MerchantRepository(session)
    balance_repo = BalanceRepository(session)
    transfer_repo = TransferRepository(session)
    idempotency_repo = IdempotencyRepository(session)
    fee_calculator = get_fee_calculator()
    
    return ExecuteTransferUseCase(
        merchant_repo,
        balance_repo,
        transfer_repo,
        idempotency_repo,
        fee_calculator
    )


async def get_list_transfers_use_case(
    session: AsyncSession
) -> ListTransfersUseCase:
    transfer_repo = TransferRepository(session)
    return ListTransfersUseCase(transfer_repo)

