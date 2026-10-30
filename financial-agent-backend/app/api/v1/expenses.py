"""
Expense management API — full CRUD with category filtering, date ranges, and pagination.
"""

import uuid
from datetime import date
from decimal import Decimal
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func, and_

from app.api.dependencies import CurrentUser, DbSession
from app.models.expense import ExpenseRecord, ExpenseCategory

router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────────────────
class CategoryResponse(BaseModel):
    id: str
    name: str
    is_system: bool
    icon: Optional[str] = None
    color: Optional[str] = None

    model_config = {"from_attributes": True}


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    icon: Optional[str] = None
    color: Optional[str] = Field(default=None, max_length=7)


class ExpenseCreate(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=15, decimal_places=2)
    currency: str = Field(default="PKR", max_length=3)
    date: date
    description: str = Field(min_length=1, max_length=500)
    category_id: Optional[str] = None
    notes: Optional[str] = None


class ExpenseUpdate(BaseModel):
    amount: Optional[Decimal] = Field(default=None, gt=0, max_digits=15, decimal_places=2)
    currency: Optional[str] = None
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
    notes: Optional[str] = None
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class ExpenseListResponse(BaseModel):
    items: List[ExpenseResponse]
    total: int
    total_amount: float


# ── Category Routes ──────────────────────────────────────────────────────
@router.get("/categories", response_model=List[CategoryResponse])
async def list_categories(user: CurrentUser, db: DbSession):
    """List system default categories plus user-created custom categories."""
    result = await db.execute(
        select(ExpenseCategory).where(
            (ExpenseCategory.is_system == True) | (ExpenseCategory.user_id == user.id)  # noqa: E712
        ).order_by(ExpenseCategory.name.asc())
    )
    categories = result.scalars().all()
    return [
        CategoryResponse(
            id=str(c.id),
            name=c.name,
            is_system=c.is_system,
            icon=c.icon,
            color=c.color,
        )
        for c in categories
    ]


@router.post("/categories", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(payload: CategoryCreate, user: CurrentUser, db: DbSession):
    """Create a user custom category."""
    cat = ExpenseCategory(
        user_id=user.id,
        name=payload.name,
        is_system=False,
        icon=payload.icon,
        color=payload.color,
    )
    db.add(cat)
    await db.commit()
    await db.refresh(cat)
    return CategoryResponse(
        id=str(cat.id),
        name=cat.name,
        is_system=cat.is_system,
        icon=cat.icon,
        color=cat.color,
    )


# ── Expense Record Routes ────────────────────────────────────────────────
@router.get("", response_model=ExpenseListResponse)
async def list_expenses(
    user: CurrentUser,
    db: DbSession,
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    category_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List user expenses with optional date range and category filters."""
    filters = [ExpenseRecord.user_id == user.id]
    if start_date:
        filters.append(ExpenseRecord.date >= start_date)
    if end_date:
        filters.append(ExpenseRecord.date <= end_date)
    if category_id:
        try:
            cat_uuid = uuid.UUID(category_id)
            filters.append(ExpenseRecord.category_id == cat_uuid)
        except ValueError:
            pass

    # Total count and sum
    total_q = select(func.count(ExpenseRecord.id), func.coalesce(func.sum(ExpenseRecord.amount), 0)).where(and_(*filters))
    total_res = await db.execute(total_q)
    total_count, total_sum = total_res.first()

    # Query items
    items_q = (
        select(ExpenseRecord)
        .where(and_(*filters))
        .order_by(ExpenseRecord.date.desc(), ExpenseRecord.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    items_res = await db.execute(items_q)
    records = items_res.scalars().all()

    return ExpenseListResponse(
        items=[
            ExpenseResponse(
                id=str(r.id),
                amount=float(r.amount),
                currency=r.currency,
                date=r.date,
                description=r.description,
                category_id=str(r.category_id) if r.category_id else None,
                notes=r.notes,
                created_at=r.created_at.isoformat(),
                updated_at=r.updated_at.isoformat(),
            )
            for r in records
        ],
        total=total_count,
        total_amount=float(total_sum),
    )


@router.post("", response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED)
async def create_expense(payload: ExpenseCreate, user: CurrentUser, db: DbSession):
    """Create a new expense record."""
    cat_uuid = None
    if payload.category_id:
        try:
            cat_uuid = uuid.UUID(payload.category_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid category_id format")

    expense = ExpenseRecord(
        user_id=user.id,
        amount=payload.amount,
        currency=payload.currency.upper(),
        date=payload.date,
        description=payload.description,
        category_id=cat_uuid,
        notes=payload.notes,
    )
    db.add(expense)
    await db.commit()
    await db.refresh(expense)

    return ExpenseResponse(
        id=str(expense.id),
        amount=float(expense.amount),
        currency=expense.currency,
        date=expense.date,
        description=expense.description,
        category_id=str(expense.category_id) if expense.category_id else None,
        notes=expense.notes,
        created_at=expense.created_at.isoformat(),
        updated_at=expense.updated_at.isoformat(),
    )


@router.get("/{expense_id}", response_model=ExpenseResponse)
async def get_expense(expense_id: str, user: CurrentUser, db: DbSession):
    """Get a specific expense record by ID."""
    try:
        eid = uuid.UUID(expense_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid expense_id format")

    res = await db.execute(
        select(ExpenseRecord).where(
            and_(ExpenseRecord.id == eid, ExpenseRecord.user_id == user.id)
        )
    )
    expense = res.scalar_one_or_none()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense record not found")

    return ExpenseResponse(
        id=str(expense.id),
        amount=float(expense.amount),
        currency=expense.currency,
        date=expense.date,
        description=expense.description,
        category_id=str(expense.category_id) if expense.category_id else None,
        notes=expense.notes,
        created_at=expense.created_at.isoformat(),
        updated_at=expense.updated_at.isoformat(),
    )


@router.patch("/{expense_id}", response_model=ExpenseResponse)
async def update_expense(
    expense_id: str, payload: ExpenseUpdate, user: CurrentUser, db: DbSession
):
    """Update an existing expense record."""
    try:
        eid = uuid.UUID(expense_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid expense_id format")

    res = await db.execute(
        select(ExpenseRecord).where(
            and_(ExpenseRecord.id == eid, ExpenseRecord.user_id == user.id)
        )
    )
    expense = res.scalar_one_or_none()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense record not found")

    if payload.amount is not None:
        expense.amount = payload.amount
    if payload.currency is not None:
        expense.currency = payload.currency.upper()
    if payload.date is not None:
        expense.date = payload.date
    if payload.description is not None:
        expense.description = payload.description
    if payload.category_id is not None:
        try:
            expense.category_id = uuid.UUID(payload.category_id) if payload.category_id else None
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid category_id format")
    if payload.notes is not None:
        expense.notes = payload.notes

    await db.commit()
    await db.refresh(expense)

    return ExpenseResponse(
        id=str(expense.id),
        amount=float(expense.amount),
        currency=expense.currency,
        date=expense.date,
        description=expense.description,
        category_id=str(expense.category_id) if expense.category_id else None,
        notes=expense.notes,
        created_at=expense.created_at.isoformat(),
        updated_at=expense.updated_at.isoformat(),
    )


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_expense(expense_id: str, user: CurrentUser, db: DbSession):
    """Delete an expense record."""
    try:
        eid = uuid.UUID(expense_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid expense_id format")

    res = await db.execute(
        select(ExpenseRecord).where(
            and_(ExpenseRecord.id == eid, ExpenseRecord.user_id == user.id)
        )
    )
    expense = res.scalar_one_or_none()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense record not found")

    await db.delete(expense)
    await db.commit()
