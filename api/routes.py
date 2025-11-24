from fastapi import APIRouter, Depends, HTTPException, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession
from decimal import Decimal
import logging

from infrastructure.database import get_db
from domain.exceptions import (
    MerchantNotFoundError,
    InsufficientFundsError,
    InvalidTransferError
)
from api.schemas import (
    CreateMerchantRequest,
    MerchantResponse,
    BalanceResponse,
    TransferRequest,
    TransferResponse,
    ErrorResponse,
    TransferListResponse,
    TransferListItem
)
from api.dependencies import (
    get_create_merchant_use_case,
    get_get_merchant_use_case,
    get_get_balance_use_case,
    get_execute_transfer_use_case,
    get_list_transfers_use_case
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/merchants",
    response_model=MerchantResponse,
    status_code=201,
    responses={
        400: {"model": ErrorResponse},
        409: {"model": ErrorResponse}
    }
)
async def create_merchant(
    request: CreateMerchantRequest,
    session: AsyncSession = Depends(get_db)
):
    try:
        use_case = await get_create_merchant_use_case(session)
        merchant = await use_case.execute(
            merchant_name=request.merchant_name,
            currency=request.currency,
            initial_balance=Decimal(request.initial_balance)
        )
        
        get_use_case = await get_get_merchant_use_case(session)
        result = await get_use_case.execute(request.merchant_name)
        
        logger.info(f"Created merchant: {request.merchant_name}")
        return MerchantResponse(**result)
    
    except ValueError as e:
        logger.warning(f"Invalid request: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating merchant: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/merchants/{merchant_name}",
    response_model=MerchantResponse,
    responses={404: {"model": ErrorResponse}}
)
async def get_merchant(
    merchant_name: str,
    session: AsyncSession = Depends(get_db)
):
    try:
        use_case = await get_get_merchant_use_case(session)
        result = await use_case.execute(merchant_name)
        return MerchantResponse(**result)
    
    except MerchantNotFoundError as e:
        logger.warning(f"Merchant not found: {merchant_name}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting merchant: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/merchants/{merchant_name}/balance",
    response_model=BalanceResponse,
    responses={404: {"model": ErrorResponse}}
)
async def get_merchant_balance(
    merchant_name: str,
    currency: str = Query(None, description="Optional currency filter"),
    session: AsyncSession = Depends(get_db)
):
    try:
        use_case = await get_get_balance_use_case(session)
        result = await use_case.execute(merchant_name, currency)
        return BalanceResponse(**result)
    
    except MerchantNotFoundError as e:
        logger.warning(f"Merchant not found: {merchant_name}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting balance: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/transfers",
    response_model=TransferResponse,
    status_code=201,
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse}
    }
)
async def execute_transfer(
    request: TransferRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    session: AsyncSession = Depends(get_db)
):
    if not idempotency_key or not idempotency_key.strip():
        logger.warning("Missing or empty Idempotency-Key header")
        raise HTTPException(
            status_code=400,
            detail="Idempotency-Key header is required"
        )
    
    idempotency_key = idempotency_key.strip()
    
    from infrastructure.repositories import IdempotencyRepository
    idempotency_repo = IdempotencyRepository(session)
    stored_response = await idempotency_repo.get(idempotency_key)
    
    if stored_response:
        logger.info(f"Duplicate request detected for idempotency_key: {idempotency_key}")
        stored_response['is_duplicate'] = True
        stored_response['message'] = f"This Idempotency-Key '{idempotency_key}' was already used. Returning previous transfer result."
        return TransferResponse(**stored_response)
    
    try:
        use_case = await get_execute_transfer_use_case(session)
        result = await use_case.execute(
            from_merchant=request.from_merchant,
            to_merchant=request.to_merchant,
            currency=request.currency,
            amount=Decimal(request.amount),
            idempotency_key=idempotency_key
        )
        
        result['is_duplicate'] = False
        result['message'] = "Transfer executed successfully"
        
        logger.info(
            f"Transfer executed: {request.from_merchant} -> "
            f"{request.to_merchant}, {request.amount} {request.currency}, "
            f"fee: {result['fee']}, idempotency_key: {idempotency_key}"
        )
        
        return TransferResponse(**result)
    
    except MerchantNotFoundError as e:
        logger.warning(f"Merchant not found: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except InsufficientFundsError as e:
        logger.warning(f"Insufficient funds: {str(e)}")
        raise HTTPException(status_code=409, detail=str(e))
    except InvalidTransferError as e:
        logger.warning(f"Invalid transfer: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        logger.warning(f"Invalid request: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error executing transfer: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/transfers",
    response_model=TransferListResponse,
    responses={400: {"model": ErrorResponse}}
)
async def list_transfers(
    from_merchant: str = Query(None, description="Filter by sender"),
    to_merchant: str = Query(None, description="Filter by receiver"),
    currency: str = Query(None, description="Filter by currency"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    session: AsyncSession = Depends(get_db)
):
    try:
        use_case = await get_list_transfers_use_case(session)
        transfers = await use_case.execute(
            from_merchant=from_merchant,
            to_merchant=to_merchant,
            currency=currency,
            limit=limit,
            offset=offset
        )
        
        return TransferListResponse(
            transfers=[TransferListItem(**t) for t in transfers],
            total=len(transfers)
        )
    
    except Exception as e:
        logger.error(f"Error listing transfers: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

