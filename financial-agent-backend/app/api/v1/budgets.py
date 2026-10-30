"""
Budget management API — full CRUD with category allocations and actual spending tracking.
"""

import uuid
from datetime import date
from decimal import Decimal
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func, and_
from sqlalchemy.orm import selectinload

from app.api.dependencies import CurrentUser, DbSession
from app.models.budget import Budget, BudgetCategory, BudgetPeriod
from app.models.expense import ExpenseRecord, ExpenseCategory

router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────────────────
class CategoryAllocationCreate(BaseModel):
    category_id: str
    limit_amount: Decimal = Field(gt=0, max_digits=15, decimal_places=2)


class CategoryAllocationResponse(BaseModel):
    id: str
    category_id: str
    category_name: Optional[str] = None
    limit_amount: float
    spent_amount: float = 0.0

    model_config = {"from_attributes": True}


class BudgetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    period_type: BudgetPeriod = BudgetPeriod.MONTHLY
    start_date: date
    end_date: date
    total_limit: Decimal = Field(gt=0, max_digits=15, decimal_places=2)
    currency: str = Field(default="PKR", max_length=3)
    category_allocations: Optional[List[CategoryAllocationCreate]] = None


class BudgetUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    period_type: Optional[BudgetPeriod] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    total_limit: Optional[Decimal] = Field(default=None, gt=0, max_digits=15, decimal_places=2)
    currency: Optional[str] = None
    category_allocations: Optional[List[CategoryAllocationCreate]] = None


class BudgetResponse(BaseModel):
    id: str
    name: str
    period_type: str
    start_date: date
    end_date: date
    total_limit: float
    total_spent: float
    currency: str
    allocations: List[CategoryAllocationResponse] = []
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


# ── Helper ───────────────────────────────────────────────────────────────
async def _build_budget_response(budget: Budget, db: DbSession, user_id: uuid.UUID) -> BudgetResponse:
    # Calculate total spent in budget date range
    spent_res = await db.execute(
        select(func.coalesce(func.sum(ExpenseRecord.amount), 0)).where(
            and_(
                ExpenseRecord.user_id == user_id,
                ExpenseRecord.date >= budget.start_date,
                ExpenseRecord.date <= budget.end_date,
            )
        )
    )
    total_spent = float(spent_res.scalar_one())

    # Build allocations with per-category spending
    allocations = []
    for alloc in budget.category_allocations:
        cat_spent_res = await db.execute(
            select(func.coalesce(func.sum(ExpenseRecord.amount), 0)).where(
                and_(
                    ExpenseRecord.user_id == user_id,
                    ExpenseRecord.category_id == alloc.category_id,
                    ExpenseRecord.date >= budget.start_date,
                    ExpenseRecord.date <= budget.end_date,
                )
            )
        )
        cat_spent = float(cat_spent_res.scalar_one())
        cat_name = alloc.category.name if alloc.category else "Uncategorized"
        allocations.append(
            CategoryAllocationResponse(
                id=str(alloc.id),
                category_id=str(alloc.category_id),
                category_name=cat_name,
                limit_amount=float(alloc.limit_amount),
                spent_amount=cat_spent,
            )
        )

    return BudgetResponse(
        id=str(budget.id),
        name=budget.name,
        period_type=budget.period_type.value if hasattr(budget.period_type, "value") else str(budget.period_type),
        start_date=budget.start_date,
        end_date=budget.end_date,
        total_limit=float(budget.total_limit),
        total_spent=total_spent,
        currency=budget.currency,
        allocations=allocations,
        created_at=budget.created_at.isoformat(),
        updated_at=budget.updated_at.isoformat(),
    )


# ── Routes ───────────────────────────────────────────────────────────────
@router.get("", response_model=List[BudgetResponse])
async def list_budgets(user: CurrentUser, db: DbSession):
    """List all budgets for current user with spending progress."""
    result = await db.execute(
        select(Budget)
        .options(selectinload(Budget.category_allocations).selectinload(BudgetCategory.category))
        .where(Budget.user_id == user.id)
        .order_by(Budget.start_date.desc())
    )
    budgets = result.scalars().all()
    return [await _build_budget_response(b, db, user.id) for b in budgets]


@router.post("", response_model=BudgetResponse, status_code=status.HTTP_201_CREATED)
async def create_budget(payload: BudgetCreate, user: CurrentUser, db: DbSession):
    """Create a new budget with optional category allocations."""
    budget = Budget(
        user_id=user.id,
        name=payload.name,
        period_type=payload.period_type,
        start_date=payload.start_date,
        end_date=payload.end_date,
        total_limit=payload.total_limit,
        currency=payload.currency.upper(),
    )
    db.add(budget)
    await db.flush()

    if payload.category_allocations:
        for alloc in payload.category_allocations:
            try:
                cid = uuid.UUID(alloc.category_id)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid category ID: {alloc.category_id}")
            bc = BudgetCategory(
                budget_id=budget.id,
                category_id=cid,
                limit_amount=alloc.limit_amount,
            )
            db.add(bc)

    await db.commit()
    # Reload with relations
    res = await db.execute(
        select(Budget)
        .options(selectinload(Budget.category_allocations).selectinload(BudgetCategory.category))
        .where(Budget.id == budget.id)
    )
    loaded = res.scalar_one()
    return await _build_budget_response(loaded, db, user.id)


@router.get("/{budget_id}", response_model=BudgetResponse)
async def get_budget(budget_id: str, user: CurrentUser, db: DbSession):
    """Get single budget details with allocation progress."""
    try:
        bid = uuid.UUID(budget_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid budget_id")

    res = await db.execute(
        select(Budget)
        .options(selectinload(Budget.category_allocations).selectinload(BudgetCategory.category))
        .where(and_(Budget.id == bid, Budget.user_id == user.id))
    )
    budget = res.scalar_one_or_none()
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")

    return await _build_budget_response(budget, db, user.id)


@router.patch("/{budget_id}", response_model=BudgetResponse)
async def update_budget(budget_id: str, payload: BudgetUpdate, user: CurrentUser, db: DbSession):
    """Update a budget and its category allocations."""
    try:
        bid = uuid.UUID(budget_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid budget_id")

    res = await db.execute(
        select(Budget)
        .options(selectinload(Budget.category_allocations).selectinload(BudgetCategory.category))
        .where(and_(Budget.id == bid, Budget.user_id == user.id))
    )
    budget = res.scalar_one_or_none()
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")

    if payload.name is not None:
        budget.name = payload.name
    if payload.period_type is not None:
        budget.period_type = payload.period_type
    if payload.start_date is not None:
        budget.start_date = payload.start_date
    if payload.end_date is not None:
        budget.end_date = payload.end_date
    if payload.total_limit is not None:
        budget.total_limit = payload.total_limit
    if payload.currency is not None:
        budget.currency = payload.currency.upper()

    if payload.category_allocations is not None:
        # Replace existing category allocations
        for old_alloc in list(budget.category_allocations):
            await db.delete(old_alloc)
        budget.category_allocations.clear()

        for alloc in payload.category_allocations:
            try:
                cid = uuid.UUID(alloc.category_id)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid category ID: {alloc.category_id}")
            bc = BudgetCategory(
                budget_id=budget.id,
                category_id=cid,
                limit_amount=alloc.limit_amount,
            )
            db.add(bc)

    await db.commit()
    res = await db.execute(
        select(Budget)
        .options(selectinload(Budget.category_allocations).selectinload(BudgetCategory.category))
        .where(Budget.id == budget.id)
    )
    loaded = res.scalar_one()
    return await _build_budget_response(loaded, db, user.id)


@router.delete("/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_budget(budget_id: str, user: CurrentUser, db: DbSession):
    """Delete a budget."""
    try:
        bid = uuid.UUID(budget_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid budget_id")

    res = await db.execute(
        select(Budget).where(and_(Budget.id == bid, Budget.user_id == user.id))
    )
    budget = res.scalar_one_or_none()
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")

    await db.delete(budget)
    await db.commit()
