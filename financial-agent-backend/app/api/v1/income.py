"""
Income management API — CRUD, categories, filtering and period totals.

Invalid enum values are rejected with 422 by Pydantic before any SQL runs.
"""

import uuid
from datetime import date
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select

from app.api.dependencies import CurrentUser, DbSession
from app.models.income import (
    IncomeCategory,
    IncomeFrequency,
    IncomeRecord,
    IncomeType,
)
from app.services.categories import resolve_income_category
from app.services.events import log_event

router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────────────────
class IncomeCategoryResponse(BaseModel):
    id: str
    name: str
    is_system: bool


class IncomeCategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class IncomeCreate(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=15, decimal_places=2)
    currency: str = Field(default="PKR", min_length=3, max_length=3)
    date: date
    source: str = Field(min_length=1, max_length=255)
    income_type: IncomeType = IncomeType.OTHER
    category_id: Optional[str] = None
    frequency: Optional[IncomeFrequency] = None
    notes: Optional[str] = None


class IncomeUpdate(BaseModel):
    amount: Optional[Decimal] = Field(default=None, gt=0, max_digits=15, decimal_places=2)
    currency: Optional[str] = Field(default=None, min_length=3, max_length=3)
    date: Optional[date] = None
    source: Optional[str] = Field(default=None, min_length=1, max_length=255)
    income_type: Optional[IncomeType] = None
    category_id: Optional[str] = None
    frequency: Optional[IncomeFrequency] = None
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


class IncomeListResponse(BaseModel):
    items: List[IncomeResponse]
    total: int
    total_amount: float


# ── Category Routes ──────────────────────────────────────────────────────
@router.get("/categories", response_model=List[IncomeCategoryResponse])
async def list_income_categories(user: CurrentUser, db: DbSession):
    """List system defaults plus the user's custom income categories."""
    result = await db.execute(
        select(IncomeCategory)
        .where(
            or_(IncomeCategory.is_system.is_(True), IncomeCategory.user_id == user.id)
        )
        .order_by(IncomeCategory.name.asc())
    )
    return [
        IncomeCategoryResponse(id=str(category.id), name=category.name, is_system=category.is_system)
        for category in result.scalars().all()
    ]


@router.post(
    "/categories",
    response_model=IncomeCategoryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_income_category(
    payload: IncomeCategoryCreate, user: CurrentUser, db: DbSession
):
    """Create a custom income category for the current user."""
    name = payload.name.strip()
    existing = await db.scalar(
        select(IncomeCategory).where(
            func.lower(IncomeCategory.name) == name.lower(),
            or_(IncomeCategory.is_system.is_(True), IncomeCategory.user_id == user.id),
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An income category with that name already exists",
        )

    category = IncomeCategory(user_id=user.id, name=name, is_system=False)
    db.add(category)
    await db.flush()
    return IncomeCategoryResponse(
        id=str(category.id), name=category.name, is_system=category.is_system
    )


# ── Record Routes ────────────────────────────────────────────────────────
@router.post("", response_model=IncomeResponse, status_code=status.HTTP_201_CREATED)
async def create_income(body: IncomeCreate, user: CurrentUser, db: DbSession):
    """Add a new income record."""
    category_id = await resolve_income_category(db, user.id, body.category_id)

    record = IncomeRecord(
        user_id=user.id,
        amount=body.amount,
        currency=body.currency.upper(),
        date=body.date,
        source=body.source.strip(),
        income_type=body.income_type,
        category_id=category_id,
        frequency=body.frequency,
        notes=body.notes,
    )
    db.add(record)
    await db.flush()

    log_event(
        db,
        user_id=user.id,
        event_type="income_created",
        entity_type="income",
        entity_id=record.id,
        metadata={"amount": float(record.amount), "income_type": record.income_type.value},
    )

    await db.commit()
    await db.refresh(record)
    return _to_response(record)


@router.get("", response_model=IncomeListResponse)
async def list_income(
    user: CurrentUser,
    db: DbSession,
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    income_type: Optional[IncomeType] = Query(None),
    category_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None, max_length=255),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List income records with optional date, type, category and text filters."""
    filters = [IncomeRecord.user_id == user.id]
    if start_date:
        filters.append(IncomeRecord.date >= start_date)
    if end_date:
        filters.append(IncomeRecord.date <= end_date)
    if income_type:
        filters.append(IncomeRecord.income_type == income_type)
    if category_id:
        try:
            filters.append(IncomeRecord.category_id == uuid.UUID(category_id))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid category id",
            )
    if search:
        filters.append(IncomeRecord.source.ilike(f"%{search.strip()}%"))

    totals = await db.execute(
        select(func.count(IncomeRecord.id), func.coalesce(func.sum(IncomeRecord.amount), 0)).where(
            and_(*filters)
        )
    )
    total, total_amount = totals.one()

    result = await db.execute(
        select(IncomeRecord)
        .where(and_(*filters))
        .order_by(IncomeRecord.date.desc(), IncomeRecord.created_at.desc())
        .limit(limit)
        .offset(offset)
    )

    return IncomeListResponse(
        items=[_to_response(record) for record in result.scalars().all()],
        total=int(total),
        total_amount=round(float(total_amount or 0), 2),
    )


@router.get("/{income_id}", response_model=IncomeResponse)
async def get_income(income_id: str, user: CurrentUser, db: DbSession):
    """Get a specific income record."""
    record = await _get_user_income(income_id, user.id, db)
    return _to_response(record)


@router.patch("/{income_id}", response_model=IncomeResponse)
async def update_income(
    income_id: str, body: IncomeUpdate, user: CurrentUser, db: DbSession
):
    """Update an existing income record."""
    record = await _get_user_income(income_id, user.id, db)
    fields = body.model_fields_set

    if body.amount is not None:
        record.amount = body.amount
    if body.currency is not None:
        record.currency = body.currency.upper()
    if body.date is not None:
        record.date = body.date
    if body.source is not None:
        record.source = body.source.strip()
    if body.income_type is not None:
        record.income_type = body.income_type
    if "category_id" in fields:
        record.category_id = await resolve_income_category(db, user.id, body.category_id)
    if "frequency" in fields:
        record.frequency = body.frequency
    if "notes" in fields:
        record.notes = body.notes

    log_event(
        db,
        user_id=user.id,
        event_type="income_updated",
        entity_type="income",
        entity_id=record.id,
        metadata={"amount": float(record.amount)},
    )

    await db.commit()
    await db.refresh(record)
    return _to_response(record)


@router.delete("/{income_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_income(income_id: str, user: CurrentUser, db: DbSession):
    """Delete an income record."""
    record = await _get_user_income(income_id, user.id, db)
    log_event(
        db,
        user_id=user.id,
        event_type="income_deleted",
        entity_type="income",
        entity_id=record.id,
        metadata={"amount": float(record.amount)},
    )
    await db.delete(record)
    await db.commit()


# ── Helpers ──────────────────────────────────────────────────────────────
async def _get_user_income(income_id: str, user_id: uuid.UUID, db) -> IncomeRecord:
    """Fetch an income record, enforcing ownership."""
    try:
        rid = uuid.UUID(income_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Income record not found")

    record = await db.scalar(
        select(IncomeRecord).where(
            IncomeRecord.id == rid,
            IncomeRecord.user_id == user_id,
        )
    )
    if record is None:
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
