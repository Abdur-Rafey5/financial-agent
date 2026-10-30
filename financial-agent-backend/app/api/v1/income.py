"""
Income management API — full CRUD with filtering and period totals.
"""

import uuid
from datetime import date
from decimal import Decimal
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func, and_

from app.api.dependencies import CurrentUser, DbSession
from app.models.income import IncomeRecord, IncomeCategory, IncomeType, IncomeFrequency

router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────────────────
class IncomeCreate(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=15, decimal_places=2)
    currency: str = Field(default="PKR", max_length=3)
    date: date
    source: str = Field(min_length=1, max_length=255)
    income_type: str = Field(default="other")
    category_id: Optional[str] = None
    frequency: Optional[str] = None
    notes: Optional[str] = None


class IncomeUpdate(BaseModel):
    amount: Optional[Decimal] = Field(default=None, gt=0, max_digits=15, decimal_places=2)
    currency: Optional[str] = None
    date: Optional[date] = None
    source: Optional[str] = None
    income_type: Optional[str] = None
    category_id: Optional[str] = None
    frequency: Optional[str] = None
    notes: Optional[str] = None


class IncomeResponse(BaseModel):
    id: str
    amount: float
    currency: str
    date: date
    source: str
    income_type: str
    category_id: Optional[str] = None
    frequency: Optional[str] = None
    notes: Optional[str] = None
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class IncomeListResponse(BaseModel):
    items: List[IncomeResponse]
    total: int
    total_amount: float


# ── Routes ───────────────────────────────────────────────────────────────
@router.post("", response_model=IncomeResponse, status_code=status.HTTP_201_CREATED)
async def create_income(body: IncomeCreate, user: CurrentUser, db: DbSession):
    """Add a new income record."""
    record = IncomeRecord(
        user_id=user.id,
        amount=body.amount,
        currency=body.currency,
        date=body.date,
        source=body.source,
        income_type=IncomeType(body.income_type),
        category_id=uuid.UUID(body.category_id) if body.category_id else None,
        frequency=IncomeFrequency(body.frequency) if body.frequency else None,
        notes=body.notes,
    )
    db.add(record)
    await db.flush()

    return _to_response(record)


@router.get("", response_model=IncomeListResponse)
async def list_income(
    user: CurrentUser,
    db: DbSession,
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    income_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List income records with optional date and type filters."""
    query = select(IncomeRecord).where(IncomeRecord.user_id == user.id)

    if start_date:
        query = query.where(IncomeRecord.date >= start_date)
    if end_date:
        query = query.where(IncomeRecord.date <= end_date)
    if income_type:
        query = query.where(IncomeRecord.income_type == IncomeType(income_type))

    # Get total count and amount
    count_query = select(
        func.count(IncomeRecord.id),
        func.coalesce(func.sum(IncomeRecord.amount), 0),
    ).where(IncomeRecord.user_id == user.id)

    if start_date:
        count_query = count_query.where(IncomeRecord.date >= start_date)
    if end_date:
        count_query = count_query.where(IncomeRecord.date <= end_date)
    if income_type:
        count_query = count_query.where(IncomeRecord.income_type == IncomeType(income_type))

    count_result = await db.execute(count_query)
    total, total_amount = count_result.one()

    # Get paginated records
    query = query.order_by(IncomeRecord.date.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    records = result.scalars().all()

    return IncomeListResponse(
        items=[_to_response(r) for r in records],
        total=total,
        total_amount=float(total_amount),
    )


@router.get("/{income_id}", response_model=IncomeResponse)
async def get_income(income_id: str, user: CurrentUser, db: DbSession):
    """Get a specific income record."""
    record = await _get_user_income(income_id, user.id, db)
    return _to_response(record)


@router.patch("/{income_id}", response_model=IncomeResponse)
async def update_income(income_id: str, body: IncomeUpdate, user: CurrentUser, db: DbSession):
    """Update an existing income record."""
    record = await _get_user_income(income_id, user.id, db)

    if body.amount is not None:
        record.amount = body.amount
    if body.currency is not None:
        record.currency = body.currency
    if body.date is not None:
        record.date = body.date
    if body.source is not None:
        record.source = body.source
    if body.income_type is not None:
        record.income_type = IncomeType(body.income_type)
    if body.category_id is not None:
        record.category_id = uuid.UUID(body.category_id)
    if body.frequency is not None:
        record.frequency = IncomeFrequency(body.frequency)
    if body.notes is not None:
        record.notes = body.notes

    await db.flush()
    return _to_response(record)


@router.delete("/{income_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_income(income_id: str, user: CurrentUser, db: DbSession):
    """Delete an income record."""
    record = await _get_user_income(income_id, user.id, db)
    await db.delete(record)


# ── Helpers ──────────────────────────────────────────────────────────────
async def _get_user_income(income_id: str, user_id: uuid.UUID, db) -> IncomeRecord:
    """Fetch an income record, enforcing ownership."""
    try:
        rid = uuid.UUID(income_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Income record not found")

    result = await db.execute(
        select(IncomeRecord).where(
            IncomeRecord.id == rid,
            IncomeRecord.user_id == user_id,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Income record not found")
    return record


def _to_response(record: IncomeRecord) -> IncomeResponse:
    return IncomeResponse(
        id=str(record.id),
        amount=float(record.amount),
        currency=record.currency,
        date=record.date,
        source=record.source,
        income_type=record.income_type.value,
        category_id=str(record.category_id) if record.category_id else None,
        frequency=record.frequency.value if record.frequency else None,
        notes=record.notes,
        created_at=record.created_at.isoformat(),
        updated_at=record.updated_at.isoformat(),
    )
