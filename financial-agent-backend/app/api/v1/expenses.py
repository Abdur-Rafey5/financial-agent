"""
Expense management API — CRUD, custom categories, filtering and search.
"""

import uuid
from datetime import date
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import selectinload

from app.api.dependencies import CurrentUser, DbSession
from app.models.budget import BudgetCategory
from app.models.expense import ExpenseCategory, ExpenseRecord
from app.services.categories import resolve_expense_category
from app.services.events import log_event

router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────────────────
class CategoryResponse(BaseModel):
    id: str
    name: str
    is_system: bool
    icon: Optional[str] = None
    color: Optional[str] = None


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    icon: Optional[str] = Field(default=None, max_length=50)
    color: Optional[str] = Field(default=None, max_length=7)


class ExpenseCreate(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=15, decimal_places=2)
    currency: str = Field(default="PKR", min_length=3, max_length=3)
    date: date
    description: str = Field(min_length=1, max_length=500)
    category_id: Optional[str] = None
    notes: Optional[str] = None


class ExpenseUpdate(BaseModel):
    amount: Optional[Decimal] = Field(default=None, gt=0, max_digits=15, decimal_places=2)
    currency: Optional[str] = Field(default=None, min_length=3, max_length=3)
    date: Optional[date] = None
    description: Optional[str] = Field(default=None, min_length=1, max_length=500)
    category_id: Optional[str] = None
    notes: Optional[str] = None


class ExpenseResponse(BaseModel):
    id: str
    amount: float
    currency: str
    date: date
    description: str
    category_id: Optional[str] = None
    category_name: Optional[str] = None
    notes: Optional[str] = None
    created_at: str
    updated_at: str


class ExpenseListResponse(BaseModel):
    items: List[ExpenseResponse]
    total: int
    total_amount: float


# ── Category Routes ──────────────────────────────────────────────────────
@router.get("/categories", response_model=List[CategoryResponse])
async def list_categories(user: CurrentUser, db: DbSession):
    """List system default categories plus user-created custom categories."""
    result = await db.execute(
        select(ExpenseCategory)
        .where(
            or_(ExpenseCategory.is_system.is_(True), ExpenseCategory.user_id == user.id)
        )
        .order_by(ExpenseCategory.is_system.desc(), ExpenseCategory.name.asc())
    )
    return [_category_response(category) for category in result.scalars().all()]


@router.post(
    "/categories", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED
)
async def create_category(payload: CategoryCreate, user: CurrentUser, db: DbSession):
    """Create a user custom category."""
    name = payload.name.strip()
    existing = await db.scalar(
        select(ExpenseCategory).where(
            func.lower(ExpenseCategory.name) == name.lower(),
            or_(ExpenseCategory.is_system.is_(True), ExpenseCategory.user_id == user.id),
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An expense category with that name already exists",
        )

    category = ExpenseCategory(
        user_id=user.id,
        name=name,
        is_system=False,
        icon=payload.icon,
        color=payload.color,
    )
    db.add(category)
    await db.flush()
    return _category_response(category)


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(category_id: str, user: CurrentUser, db: DbSession):
    """Delete one of the current user's custom categories."""
    try:
        cid = uuid.UUID(category_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Category not found")

    category = await db.scalar(
        select(ExpenseCategory).where(
            ExpenseCategory.id == cid,
            ExpenseCategory.user_id == user.id,
            ExpenseCategory.is_system.is_(False),
        )
    )
    if category is None:
        raise HTTPException(
            status_code=404,
            detail="Custom category not found (system categories cannot be deleted)",
        )

    # Remove budget allocations explicitly so behaviour is identical on
    # SQLite (where FK cascades are optional) and PostgreSQL.
    allocations = await db.scalars(
        select(BudgetCategory).where(BudgetCategory.category_id == category.id)
    )
    for allocation in allocations.all():
        await db.delete(allocation)

    await db.delete(category)
    await db.commit()


# ── Record Routes ────────────────────────────────────────────────────────
@router.get("", response_model=ExpenseListResponse)
async def list_expenses(
    user: CurrentUser,
    db: DbSession,
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    category_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None, max_length=255),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List expenses with optional date range, category and text filters."""
    filters = [ExpenseRecord.user_id == user.id]
    if start_date:
        filters.append(ExpenseRecord.date >= start_date)
    if end_date:
        filters.append(ExpenseRecord.date <= end_date)
    if category_id:
        try:
            filters.append(ExpenseRecord.category_id == uuid.UUID(category_id))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid category id",
            )
    if search:
        filters.append(ExpenseRecord.description.ilike(f"%{search.strip()}%"))

    totals = await db.execute(
        select(
            func.count(ExpenseRecord.id),
            func.coalesce(func.sum(ExpenseRecord.amount), 0),
        ).where(and_(*filters))
    )
    total_count, total_sum = totals.one()

    result = await db.execute(
        select(ExpenseRecord)
        .options(selectinload(ExpenseRecord.category))
        .where(and_(*filters))
        .order_by(ExpenseRecord.date.desc(), ExpenseRecord.created_at.desc())
        .offset(offset)
        .limit(limit)
    )

    return ExpenseListResponse(
        items=[_to_response(record) for record in result.scalars().all()],
        total=int(total_count),
        total_amount=round(float(total_sum or 0), 2),
    )


@router.post("", response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED)
async def create_expense(payload: ExpenseCreate, user: CurrentUser, db: DbSession):
    """Create a new expense record."""
    category_id = await resolve_expense_category(db, user.id, payload.category_id)

    expense = ExpenseRecord(
        user_id=user.id,
        amount=payload.amount,
        currency=payload.currency.upper(),
        date=payload.date,
        description=payload.description.strip(),
        category_id=category_id,
        notes=payload.notes,
    )
    db.add(expense)
    await db.flush()

    log_event(
        db,
        user_id=user.id,
        event_type="expense_created",
        entity_type="expense",
        entity_id=expense.id,
        metadata={
            "amount": float(expense.amount),
            "category_id": str(expense.category_id) if expense.category_id else None,
        },
    )

    await db.commit()
    loaded = await _load_expense(expense.id, user.id, db)
    return _to_response(loaded)


@router.get("/{expense_id}", response_model=ExpenseResponse)
async def get_expense(expense_id: str, user: CurrentUser, db: DbSession):
    """Get a specific expense record by ID."""
    expense = await _get_expense(expense_id, user.id, db)
    return _to_response(expense)


@router.patch("/{expense_id}", response_model=ExpenseResponse)
async def update_expense(
    expense_id: str, payload: ExpenseUpdate, user: CurrentUser, db: DbSession
):
    """Update an existing expense record."""
    expense = await _get_expense(expense_id, user.id, db)
    fields = payload.model_fields_set

    if payload.amount is not None:
        expense.amount = payload.amount
    if payload.currency is not None:
        expense.currency = payload.currency.upper()
    if payload.date is not None:
        expense.date = payload.date
    if payload.description is not None:
        expense.description = payload.description.strip()
    if "category_id" in fields:
        expense.category_id = await resolve_expense_category(
            db, user.id, payload.category_id
        )
    if "notes" in fields:
        expense.notes = payload.notes

    log_event(
        db,
        user_id=user.id,
        event_type="expense_updated",
        entity_type="expense",
        entity_id=expense.id,
        metadata={"amount": float(expense.amount)},
    )

    await db.commit()
    loaded = await _load_expense(expense.id, user.id, db)
    return _to_response(loaded)


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_expense(expense_id: str, user: CurrentUser, db: DbSession):
    """Delete an expense record."""
    expense = await _get_expense(expense_id, user.id, db)
    log_event(
        db,
        user_id=user.id,
        event_type="expense_deleted",
        entity_type="expense",
        entity_id=expense.id,
        metadata={"amount": float(expense.amount)},
    )
    await db.delete(expense)
    await db.commit()


# ── Helpers ──────────────────────────────────────────────────────────────
async def _load_expense(expense_id, user_id: uuid.UUID, db) -> ExpenseRecord:
    record = await db.scalar(
        select(ExpenseRecord)
        .options(selectinload(ExpenseRecord.category))
        .execution_options(populate_existing=True)
        .where(ExpenseRecord.id == expense_id, ExpenseRecord.user_id == user_id)
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Expense record not found")
    return record


async def _get_expense(expense_id: str, user_id: uuid.UUID, db) -> ExpenseRecord:
    try:
        eid = uuid.UUID(expense_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Expense record not found")
    return await _load_expense(eid, user_id, db)


def _category_response(category: ExpenseCategory) -> CategoryResponse:
    return CategoryResponse(
        id=str(category.id),
        name=category.name,
        is_system=category.is_system,
        icon=category.icon,
        color=category.color,
    )


def _to_response(record: ExpenseRecord) -> ExpenseResponse:
    return ExpenseResponse(
        id=str(record.id),
        amount=float(record.amount),
        currency=record.currency,
        date=record.date,
        description=record.description,
        category_id=str(record.category_id) if record.category_id else None,
        category_name=record.category.name if record.category else None,
        notes=record.notes,
        created_at=record.created_at.isoformat(),
        updated_at=record.updated_at.isoformat(),
    )
