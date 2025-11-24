import pytest
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool

from infrastructure.database import Base, get_db
from domain.services import PercentageFeeCalculator


TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def db_session():
    from infrastructure import models
    
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest.fixture
def fee_calculator():
    return PercentageFeeCalculator(0.1)


@pytest.fixture
async def sample_merchant(db_session):
    from infrastructure.repositories import MerchantRepository, BalanceRepository
    from domain.entities import Merchant, Balance
    from datetime import datetime
    from decimal import Decimal
    
    merchant_repo = MerchantRepository(db_session)
    balance_repo = BalanceRepository(db_session)
    
    merchant = Merchant(
        name="test_merchant",
        created_at=datetime.utcnow()
    )
    merchant = await merchant_repo.create(merchant)
    
    balance = Balance(
        merchant_name="test_merchant",
        currency="BTC",
        amount=Decimal("1.0")
    )
    await balance_repo.create(balance)
    
    await db_session.commit()
    
    return merchant

