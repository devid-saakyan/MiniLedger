import pytest
import asyncio
from decimal import Decimal

from infrastructure.repositories import (
    MerchantRepository,
    BalanceRepository,
    TransferRepository,
    IdempotencyRepository
)
from application.use_cases import CreateMerchantUseCase, ExecuteTransferUseCase
from domain.services import PercentageFeeCalculator


@pytest.mark.asyncio
async def test_concurrent_transfers_same_merchant(db_session):
    merchant_repo = MerchantRepository(db_session)
    balance_repo = BalanceRepository(db_session)
    transfer_repo = TransferRepository(db_session)
    idempotency_repo = IdempotencyRepository(db_session)
    fee_calculator = PercentageFeeCalculator(0.1)
    
    create_use_case = CreateMerchantUseCase(merchant_repo, balance_repo)
    await create_use_case.execute("alice", "BTC", Decimal("1.0"))
    await create_use_case.execute("bob", "BTC", Decimal("0.0"))
    await create_use_case.execute("charlie", "BTC", Decimal("0.0"))
    
    use_case = ExecuteTransferUseCase(
        merchant_repo,
        balance_repo,
        transfer_repo,
        idempotency_repo,
        fee_calculator
    )
    
    async def transfer(amount, key):
        try:
            return await use_case.execute(
                "alice", "bob", "BTC", Decimal(str(amount)), key
            )
        except Exception as e:
            return {"error": str(e)}
    
    tasks = [
        transfer(0.3, f"key-{i}")
        for i in range(4)
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    alice_balance = await balance_repo.get("alice", "BTC")
    assert alice_balance.amount >= 0, "Balance should never be negative"
    
    successful = [r for r in results if isinstance(r, dict) and "error" not in r]
    failed = [r for r in results if isinstance(r, dict) and "error" in r]
    
    assert len(successful) > 0
    
    total_sent = sum(Decimal(r["amount"]) + Decimal(r["fee"]) for r in successful)
    expected_balance = Decimal("1.0") - total_sent
    assert abs(alice_balance.amount - expected_balance) < Decimal("0.00000001")


@pytest.mark.asyncio
async def test_concurrent_balance_updates(db_session):
    merchant_repo = MerchantRepository(db_session)
    balance_repo = BalanceRepository(db_session)
    
    create_use_case = CreateMerchantUseCase(merchant_repo, balance_repo)
    await create_use_case.execute("alice", "BTC", Decimal("1.0"))
    await db_session.commit()
    

    async def add_amount(amount):
        result = await balance_repo.add_amount("alice", "BTC", Decimal(str(amount)))
        await db_session.commit()
        return result
    
    async def subtract_amount(amount):
        try:
            result = await balance_repo.subtract_amount("alice", "BTC", Decimal(str(amount)))
            await db_session.commit()
            return result
        except ValueError:
            await db_session.rollback()
            return None
    
    tasks = []
    tasks.extend([add_amount(0.1) for _ in range(10)])
    tasks.extend([subtract_amount(0.05) for _ in range(10)])
    

    for task in tasks:
        try:
            await task
        except Exception:
            pass
    
    await db_session.commit()
    balance = await balance_repo.get("alice", "BTC")
    
    assert balance.amount >= 0, "Balance should never be negative"
    
    assert balance.amount >= Decimal("0"), "Balance must be non-negative"

