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


def test_merchant_creation():
    merchant = Merchant(
        name="test_merchant",
        created_at=datetime.utcnow()
    )
    assert merchant.name == "test_merchant"
    assert merchant.created_at is not None


def test_merchant_empty_name():
    with pytest.raises(ValueError):
        Merchant(name="", created_at=datetime.utcnow())


def test_balance_creation():
    balance = Balance(
        merchant_name="test_merchant",
        currency="BTC",
        amount=Decimal("1.0")
    )
    assert balance.merchant_name == "test_merchant"
    assert balance.currency == "BTC"
    assert balance.amount == Decimal("1.0")


def test_balance_negative():
    with pytest.raises(ValueError):
        Balance(
            merchant_name="test_merchant",
            currency="BTC",
            amount=Decimal("-1.0")
        )


def test_transfer_creation():
    transfer = Transfer(
        id=None,
        from_merchant="alice",
        to_merchant="bob",
        currency="BTC",
        amount=Decimal("0.1"),
        fee=Decimal("0.001"),
        idempotency_key="test-key",
        created_at=datetime.utcnow()
    )
    assert transfer.from_merchant == "alice"
    assert transfer.to_merchant == "bob"
    assert transfer.total_debit == Decimal("0.101")


def test_transfer_same_merchant():
    with pytest.raises(ValueError):
        Transfer(
            id=None,
            from_merchant="alice",
            to_merchant="alice",
            currency="BTC",
            amount=Decimal("0.1"),
            fee=Decimal("0.001"),
            idempotency_key="test-key",
            created_at=datetime.utcnow()
        )


def test_transfer_negative_amount():
    with pytest.raises(ValueError):
        Transfer(
            id=None,
            from_merchant="alice",
            to_merchant="bob",
            currency="BTC",
            amount=Decimal("-0.1"),
            fee=Decimal("0.001"),
            idempotency_key="test-key",
            created_at=datetime.utcnow()
        )


def test_fee_calculator():
    calculator = PercentageFeeCalculator(0.1)
    
    fee = calculator.calculate_fee(Decimal("1.0"))
    assert fee == Decimal("0.001")
    
    fee = calculator.calculate_fee(Decimal("100.0"))
    assert fee == Decimal("0.1")


def test_fee_calculator_zero():
    calculator = PercentageFeeCalculator(0.1)
    
    with pytest.raises(ValueError):
        calculator.calculate_fee(Decimal("0"))


def test_fee_calculator_negative():
    calculator = PercentageFeeCalculator(0.1)
    
    with pytest.raises(ValueError):
        calculator.calculate_fee(Decimal("-1.0"))

