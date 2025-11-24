import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from main import app
from infrastructure.database import get_db, Base
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool


TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="function")
async def test_db():
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
async def client(test_db):
    from httpx import ASGITransport
    
    async def override_get_db():
        yield test_db
    
    app.dependency_overrides[get_db] = override_get_db
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_merchant(client):
    response = await client.post(
        "/api/v1/merchants",
        json={
            "merchant_name": "alice_store",
            "currency": "BTC",
            "initial_balance": "0.00001"
        }
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["merchant_name"] == "alice_store"
    assert len(data["balances"]) > 0


@pytest.mark.asyncio
async def test_get_merchant(client):
    await client.post(
        "/api/v1/merchants",
        json={
            "merchant_name": "alice_store",
            "currency": "BTC",
            "initial_balance": "0.00001"
        }
    )
    
    response = await client.get("/api/v1/merchants/alice_store")
    
    assert response.status_code == 200
    data = response.json()
    assert data["merchant_name"] == "alice_store"


@pytest.mark.asyncio
async def test_get_merchant_not_found(client):
    response = await client.get("/api/v1/merchants/nonexistent")
    
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_balance(client):
    await client.post(
        "/api/v1/merchants",
        json={
            "merchant_name": "alice_store",
            "currency": "BTC",
            "initial_balance": "0.00001"
        }
    )
    
    response = await client.get("/api/v1/merchants/alice_store/balance?currency=BTC")
    
    assert response.status_code == 200
    data = response.json()
    assert data["merchant_name"] == "alice_store"
    assert data["currency"] == "BTC"


@pytest.mark.asyncio
async def test_execute_transfer(client):
    await client.post(
        "/api/v1/merchants",
        json={
            "merchant_name": "alice_store",
            "currency": "BTC",
            "initial_balance": "0.0001"
        }
    )
    
    await client.post(
        "/api/v1/merchants",
        json={
            "merchant_name": "bob_shop",
            "currency": "BTC",
            "initial_balance": "0"
        }
    )
    
    response = await client.post(
        "/api/v1/transfers",
        json={
            "from_merchant": "alice_store",
            "to_merchant": "bob_shop",
            "currency": "BTC",
            "amount": "0.00005"
        },
        headers={"Idempotency-Key": "test-key-1"}
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["from_merchant"] == "alice_store"
    assert data["to_merchant"] == "bob_shop"
    assert "fee" in data
    assert data["is_duplicate"] is False


@pytest.mark.asyncio
async def test_execute_transfer_insufficient_funds(client):
    await client.post(
        "/api/v1/merchants",
        json={
            "merchant_name": "alice_store",
            "currency": "BTC",
            "initial_balance": "0.00001"
        }
    )
    
    await client.post(
        "/api/v1/merchants",
        json={
            "merchant_name": "bob_shop",
            "currency": "BTC",
            "initial_balance": "0"
        }
    )
    
    response = await client.post(
        "/api/v1/transfers",
        json={
            "from_merchant": "alice_store",
            "to_merchant": "bob_shop",
            "currency": "BTC",
            "amount": "0.0001" 
        },
        headers={"Idempotency-Key": "test-key-2"}
    )
    
    assert response.status_code == 409
    assert "insufficient" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_execute_transfer_idempotency(client):
    await client.post(
        "/api/v1/merchants",
        json={
            "merchant_name": "alice_store",
            "currency": "BTC",
            "initial_balance": "0.0001"
        }
    )
    
    await client.post(
        "/api/v1/merchants",
        json={
            "merchant_name": "bob_shop",
            "currency": "BTC",
            "initial_balance": "0"
        }
    )
    
    idempotency_key = "test-key-3"
    
    response1 = await client.post(
        "/api/v1/transfers",
        json={
            "from_merchant": "alice_store",
            "to_merchant": "bob_shop",
            "currency": "BTC",
            "amount": "0.00005"
        },
        headers={"Idempotency-Key": idempotency_key}
    )
    
    assert response1.status_code == 201
    data1 = response1.json()
    
    response2 = await client.post(
        "/api/v1/transfers",
        json={
            "from_merchant": "alice_store",
            "to_merchant": "bob_shop",
            "currency": "BTC",
            "amount": "0.00005"
        },
        headers={"Idempotency-Key": idempotency_key}
    )
    
    assert response2.status_code == 201
    data2 = response2.json()
    
    assert data1["transfer_id"] == data2["transfer_id"]
    assert data2["is_duplicate"] is True


@pytest.mark.asyncio
async def test_execute_transfer_missing_idempotency_key(client):
    response = await client.post(
        "/api/v1/transfers",
        json={
            "from_merchant": "alice_store",
            "to_merchant": "bob_shop",
            "currency": "BTC",
            "amount": "0.00005"
        }
    )
    
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_transfers(client):
    await client.post(
        "/api/v1/merchants",
        json={
            "merchant_name": "alice_store",
            "currency": "BTC",
            "initial_balance": "0.0001"
        }
    )
    
    await client.post(
        "/api/v1/merchants",
        json={
            "merchant_name": "bob_shop",
            "currency": "BTC",
            "initial_balance": "0"
        }
    )
    
    for i in range(3):
        await client.post(
            "/api/v1/transfers",
            json={
                "from_merchant": "alice_store",
                "to_merchant": "bob_shop",
                "currency": "BTC",
                "amount": "0.00001"
            },
            headers={"Idempotency-Key": f"list-key-{i}"}
        )
    
    response = await client.get("/api/v1/transfers")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["transfers"]) >= 3
