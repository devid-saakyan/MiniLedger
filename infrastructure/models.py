from sqlalchemy import Column, Integer, String, Numeric, DateTime, Index, Text, JSON
from sqlalchemy.sql import func
from infrastructure.database import Base


class MerchantModel(Base):
    __tablename__ = "merchants"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    __table_args__ = (
        Index('idx_merchant_name', 'name'),
    )


class BalanceModel(Base):
    __tablename__ = "balances"
    
    id = Column(Integer, primary_key=True, index=True)
    merchant_name = Column(String(255), nullable=False, index=True)
    currency = Column(String(10), nullable=False, index=True)
    amount = Column(Numeric(20, 8), nullable=False, default=0)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        Index('idx_merchant_currency', 'merchant_name', 'currency', unique=True),
    )


class TransferModel(Base):
    __tablename__ = "transfers"
    
    id = Column(Integer, primary_key=True, index=True)
    from_merchant = Column(String(255), nullable=False, index=True)
    to_merchant = Column(String(255), nullable=False, index=True)
    currency = Column(String(10), nullable=False, index=True)
    amount = Column(Numeric(20, 8), nullable=False)
    fee = Column(Numeric(20, 8), nullable=False)
    idempotency_key = Column(String(255), unique=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    __table_args__ = (
        Index('idx_idempotency_key', 'idempotency_key', unique=True),
        Index('idx_transfer_filters', 'from_merchant', 'to_merchant', 'currency'),
    )


class IdempotencyKeyModel(Base):
    __tablename__ = "idempotency_keys"
    
    id = Column(Integer, primary_key=True, index=True)
    idempotency_key = Column(String(255), unique=True, nullable=False, index=True)
    transfer_id = Column(Integer, nullable=False)
    response_data = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    __table_args__ = (
        Index('idx_idempotency_key_unique', 'idempotency_key', unique=True),
    )

