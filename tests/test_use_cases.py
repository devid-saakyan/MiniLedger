import pytest
from decimal import Decimal
from datetime import datetime

from domain.entities import Merchant, Balance, Transfer
from domain.services import PercentageFeeCalculator
from domain.exceptions import (
    MerchantNotFoundError,
    InsufficientFundsError,
    InvalidTransferError
)
from infrastructure.repositories import (
    MerchantRepository,
    BalanceRepository,
    TransferRepository,
    IdempotencyRepository
)
from application.use_cases import (
    CreateMerchantUseCase,
    GetMerchantUseCase,
    GetBalanceUseCase,
    ExecuteTransferUseCase,
    ListTransfersUseCase
)


@pytest.mark.asyncio
async def test_create_merchant_use_case(db_session, fee_calculator):
    merchant_repo = MerchantRepository(db_session)
    balance_repo = BalanceRepository(db_session)
    
    use_case = CreateMerchantUseCase(merchant_repo, balance_repo)
    
    merchant = await use_case.execute(
        merchant_name="alice",
        currency="BTC",
        initial_balance=Decimal("1.0")
    )
    
    assert merchant.name == "alice"
    
    balance = await balance_repo.get("alice", "BTC")
    assert balance is not None
    assert balance.amount == Decimal("1.0")


@pytest.mark.asyncio
async def test_create_merchant_duplicate(db_session, fee_calculator):
    merchant_repo = MerchantRepository(db_session)
    balance_repo = BalanceRepository(db_session)
    
    use_case = CreateMerchantUseCase(merchant_repo, balance_repo)
    
    await use_case.execute(
        merchant_name="alice",
        currency="BTC",
        initial_balance=Decimal("1.0")
    )
    
    with pytest.raises(ValueError):
        await use_case.execute(
            merchant_name="alice",
            currency="BTC",
            initial_balance=Decimal("1.0")
        )


@pytest.mark.asyncio
async def test_get_merchant_use_case(db_session, sample_merchant):
    merchant_repo = MerchantRepository(db_session)
    balance_repo = BalanceRepository(db_session)
    
    use_case = GetMerchantUseCase(merchant_repo, balance_repo)
    
    result = await use_case.execute("test_merchant")
    
    assert result["merchant_name"] == "test_merchant"
    assert len(result["balances"]) > 0


@pytest.mark.asyncio
async def test_get_merchant_not_found(db_session):
    merchant_repo = MerchantRepository(db_session)
    balance_repo = BalanceRepository(db_session)
    
    use_case = GetMerchantUseCase(merchant_repo, balance_repo)
    
    with pytest.raises(MerchantNotFoundError):
        await use_case.execute("nonexistent")


@pytest.mark.asyncio
async def test_execute_transfer_use_case(db_session, fee_calculator):
    merchant_repo = MerchantRepository(db_session)
    balance_repo = BalanceRepository(db_session)
    transfer_repo = TransferRepository(db_session)
    idempotency_repo = IdempotencyRepository(db_session)
    
    create_use_case = CreateMerchantUseCase(merchant_repo, balance_repo)
    await create_use_case.execute("alice", "BTC", Decimal("1.0"))
    await create_use_case.execute("bob", "BTC", Decimal("0.0"))
    
    use_case = ExecuteTransferUseCase(
        merchant_repo,
        balance_repo,
        transfer_repo,
        idempotency_repo,
        fee_calculator
    )
    
    result = await use_case.execute(
        from_merchant="alice",
        to_merchant="bob",
        currency="BTC",
        amount=Decimal("0.1"),
        idempotency_key="test-key-1"
    )
    
    assert result["from_merchant"] == "alice"
    assert result["to_merchant"] == "bob"
    assert result["amount"] == "0.1"
    assert "fee" in result
    
    alice_balance = await balance_repo.get("alice", "BTC")
    bob_balance = await balance_repo.get("bob", "BTC")
    
    assert alice_balance.amount < Decimal("1.0")
    assert bob_balance.amount == Decimal("0.1")


@pytest.mark.asyncio
async def test_execute_transfer_insufficient_funds(db_session, fee_calculator):
    merchant_repo = MerchantRepository(db_session)
    balance_repo = BalanceRepository(db_session)
    transfer_repo = TransferRepository(db_session)
    idempotency_repo = IdempotencyRepository(db_session)
    
    create_use_case = CreateMerchantUseCase(merchant_repo, balance_repo)
    await create_use_case.execute("alice", "BTC", Decimal("0.1"))
    await create_use_case.execute("bob", "BTC", Decimal("0.0"))
    
    use_case = ExecuteTransferUseCase(
        merchant_repo,
        balance_repo,
        transfer_repo,
        idempotency_repo,
        fee_calculator
    )
    
    with pytest.raises(InsufficientFundsError):
        await use_case.execute(
            from_merchant="alice",
            to_merchant="bob",
            currency="BTC",
            amount=Decimal("0.1"),
            idempotency_key="test-key-2"
        )


@pytest.mark.asyncio
async def test_execute_transfer_idempotency(db_session, fee_calculator):
    merchant_repo = MerchantRepository(db_session)
    balance_repo = BalanceRepository(db_session)
    transfer_repo = TransferRepository(db_session)
    idempotency_repo = IdempotencyRepository(db_session)
    
    create_use_case = CreateMerchantUseCase(merchant_repo, balance_repo)
    await create_use_case.execute("alice", "BTC", Decimal("1.0"))
    await create_use_case.execute("bob", "BTC", Decimal("0.0"))
    
    use_case = ExecuteTransferUseCase(
        merchant_repo,
        balance_repo,
        transfer_repo,
        idempotency_repo,
        fee_calculator
    )
    
    idempotency_key = "test-key-3"
    
    result1 = await use_case.execute(
        from_merchant="alice",
        to_merchant="bob",
        currency="BTC",
        amount=Decimal("0.1"),
        idempotency_key=idempotency_key
    )
    
    result2 = await use_case.execute(
        from_merchant="alice",
        to_merchant="bob",
        currency="BTC",
        amount=Decimal("0.1"),
        idempotency_key=idempotency_key
    )
    
    assert result1 == result2
    assert result1["transfer_id"] == result2["transfer_id"]
    
    alice_balance = await balance_repo.get("alice", "BTC")
    expected_balance = Decimal("1.0") - Decimal(result1["amount"]) - Decimal(result1["fee"])
    assert abs(alice_balance.amount - expected_balance) < Decimal("0.00000001")


@pytest.mark.asyncio
async def test_list_transfers_use_case(db_session, fee_calculator):
    merchant_repo = MerchantRepository(db_session)
    balance_repo = BalanceRepository(db_session)
    transfer_repo = TransferRepository(db_session)
    idempotency_repo = IdempotencyRepository(db_session)
    
    create_use_case = CreateMerchantUseCase(merchant_repo, balance_repo)
    await create_use_case.execute("alice", "BTC", Decimal("1.0"))
    await create_use_case.execute("bob", "BTC", Decimal("0.0"))
    
    use_case = ExecuteTransferUseCase(
        merchant_repo,
        balance_repo,
        transfer_repo,
        idempotency_repo,
        fee_calculator
    )
    
    await use_case.execute("alice", "bob", "BTC", Decimal("0.1"), "key-1")
    await use_case.execute("alice", "bob", "BTC", Decimal("0.1"), "key-2")
    
    list_use_case = ListTransfersUseCase(transfer_repo)
    transfers = await list_use_case.execute()
    
    assert len(transfers) >= 2
    
    transfers = await list_use_case.execute(from_merchant="alice")
    assert all(t["from_merchant"] == "alice" for t in transfers)

