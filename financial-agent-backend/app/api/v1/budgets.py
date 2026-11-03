"""
Budget management API — CRUD with category allocations and live spending.
"""

import uuid
from datetime import date
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, select
from sqlalchemy.orm import selectinload

from app.api.dependencies import CurrentUser, DbSession
from app.models.budget import Budget, BudgetCategory, BudgetPeriod
from app.models.expense import ExpenseRecord
from app.services.categories import resolve_expense_category
from app.services.events import log_event

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
    usage_pct: float = 0.0


class BudgetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    period_type: BudgetPeriod = BudgetPeriod.MONTHLY
    start_date: date
    end_date: date
    total_limit: Decimal = Field(gt=0, max_digits=15, decimal_places=2)
    currency: str = Field(default="PKR", min_length=3, max_length=3)
    category_allocations: Optional[List[CategoryAllocationCreate]] = None


class BudgetUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    period_type: Optional[BudgetPeriod] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    total_limit: Optional[Decimal] = Field(default=None, gt=0, max_digits=15, decimal_places=2)
    currency: Optional[str] = Field(default=None, min_length=3, max_length=3)
    category_allocations: Optional[List[CategoryAllocationCreate]] = None


class BudgetResponse(BaseModel):
    id: str
    name: str
    period_type: str
    start_date: date
    end_date: date
    total_limit: float
    total_spent: float
    remaining_amount: float
    usage_pct: float
    is_active: bool
    currency: str
    allocations: List[CategoryAllocationResponse] = []
    created_at: str
    updated_at: str


def _pct(part: float, whole: float) -> float:
    if whole <= 0:
        return 0.0
    return round(part / whole * 100, 1)


# ── Helpers ──────────────────────────────────────────────────────────────
async def _build_budget_response(
    budget: Budget, db: DbSession, user_id: uuid.UUID
) -> BudgetResponse:
    spent_res = await db.execute(
        select(func.coalesce(func.sum(ExpenseRecord.amount), 0)).where(
            and_(
                ExpenseRecord.user_id == user_id,
                ExpenseRecord.date >= budget.start_date,
                ExpenseRecord.date <= budget.end_date,
            )
        )
    )
    total_spent = round(float(spent_res.scalar_one() or 0), 2)

    allocations = []
    for allocation in budget.category_allocations:
        category_spent = await db.scalar(
            select(func.coalesce(func.sum(ExpenseRecord.amount), 0)).where(
                and_(
                    ExpenseRecord.user_id == user_id,
                    ExpenseRecord.category_id == allocation.category_id,
                    ExpenseRecord.date >= budget.start_date,
                    ExpenseRecord.date <= budget.end_date,
                )
            )
        )
        spent = round(float(category_spent or 0), 2)
        limit = float(allocation.limit_amount)
        allocations.append(
            CategoryAllocationResponse(
                id=str(allocation.id),
                category_id=str(allocation.category_id),
                category_name=allocation.category.name if allocation.category else "Uncategorized",
                limit_amount=limit,
                spent_amount=spent,
                usage_pct=_pct(spent, limit),
            )
        )

    total_limit = float(budget.total_limit)
    today = date.today()
    return BudgetResponse(
        id=str(budget.id),
        name=budget.name,
        period_type=budget.period_type.value
        if hasattr(budget.period_type, "value")
        else str(budget.period_type),
        start_date=budget.start_date,
        end_date=budget.end_date,
        total_limit=total_limit,
        total_spent=total_spent,
        remaining_amount=round(total_limit - total_spent, 2),
        usage_pct=_pct(total_spent, total_limit),
        is_active=budget.start_date <= today <= budget.end_date,
        currency=budget.currency,
        allocations=allocations,
        created_at=budget.created_at.isoformat(),
        updated_at=budget.updated_at.isoformat(),
    )


async def _load_budget(budget_id: uuid.UUID, user_id: uuid.UUID, db) -> Budget:
    budget = await db.scalar(
        select(Budget)
        .options(
            selectinload(Budget.category_allocations).selectinload(BudgetCategory.category)
        )
        .where(and_(Budget.id == budget_id, Budget.user_id == user_id))
    )
    if budget is None:
        raise HTTPException(status_code=404, detail="Budget not found")
    return budget


def _validate_dates(start: date, end: date) -> None:
    if end < start:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="end_date must be on or after start_date",
        )


async def _validate_allocations(
    db, user_id: uuid.UUID, allocations: List[CategoryAllocationCreate]
) -> List[tuple[uuid.UUID, Decimal]]:
    seen: set[uuid.UUID] = set()
    resolved: List[tuple[uuid.UUID, Decimal]] = []
    for allocation in allocations:
        category_id = await resolve_expense_category(db, user_id, allocation.category_id)
        if category_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="category_id is required for allocations",
            )
        if category_id in seen:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Duplicate category allocation",
            )
        seen.add(category_id)
        resolved.append((category_id, allocation.limit_amount))
    return resolved


# ── Routes ───────────────────────────────────────────────────────────────
@router.get("", response_model=List[BudgetResponse])
async def list_budgets(
    user: CurrentUser,
    db: DbSession,
    active_only: bool = Query(False),
):
    """List budgets with live spending progress."""
    query = (
        select(Budget)
        .options(
            selectinload(Budget.category_allocations).selectinload(BudgetCategory.category)
        )
        .where(Budget.user_id == user.id)
        .order_by(Budget.start_date.desc())
    )
    if active_only:
        today = date.today()
        query = query.where(Budget.start_date <= today, Budget.end_date >= today)

    result = await db.execute(query)
    return [await _build_budget_response(budget, db, user.id) for budget in result.scalars().all()]


@router.post("", response_model=BudgetResponse, status_code=status.HTTP_201_CREATED)
async def create_budget(payload: BudgetCreate, user: CurrentUser, db: DbSession):
    """Create a new budget with optional category allocations."""
    _validate_dates(payload.start_date, payload.end_date)
    allocations = await _validate_allocations(
        db, user.id, payload.category_allocations or []
    )

    budget = Budget(
        user_id=user.id,
        name=payload.name.strip(),
        period_type=payload.period_type,
        start_date=payload.start_date,
        end_date=payload.end_date,
        total_limit=payload.total_limit,
        currency=payload.currency.upper(),
    )
    db.add(budget)
    await db.flush()

    for category_id, limit_amount in allocations:
        db.add(
            BudgetCategory(
                budget_id=budget.id,
                category_id=category_id,
                limit_amount=limit_amount,
            )
        )

    log_event(
        db,
        user_id=user.id,
        event_type="budget_created",
        entity_type="budget",
        entity_id=budget.id,
        metadata={"total_limit": float(budget.total_limit)},
    )

    await db.commit()
    return await _build_budget_response(await _load_budget(budget.id, user.id, db), db, user.id)


@router.get("/{budget_id}", response_model=BudgetResponse)
async def get_budget(budget_id: str, user: CurrentUser, db: DbSession):
    """Get single budget details with allocation progress."""
    try:
        bid = uuid.UUID(budget_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Budget not found")
    budget = await _load_budget(bid, user.id, db)
    return await _build_budget_response(budget, db, user.id)


@router.patch("/{budget_id}", response_model=BudgetResponse)
async def update_budget(
    budget_id: str, payload: BudgetUpdate, user: CurrentUser, db: DbSession
):
    """Update a budget and optionally replace its category allocations."""
    try:
        bid = uuid.UUID(budget_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Budget not found")

    budget = await _load_budget(bid, user.id, db)

    new_start = payload.start_date or budget.start_date
    new_end = payload.end_date or budget.end_date
    _validate_dates(new_start, new_end)

    if payload.name is not None:
        budget.name = payload.name.strip()
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
        resolved = await _validate_allocations(db, user.id, payload.category_allocations)
        for allocation in list(budget.category_allocations):
            await db.delete(allocation)
        await db.flush()
        for category_id, limit_amount in resolved:
            db.add(
                BudgetCategory(
                    budget_id=budget.id,
                    category_id=category_id,
                    limit_amount=limit_amount,
                )
            )

    await db.commit()
    return await _build_budget_response(await _load_budget(budget.id, user.id, db), db, user.id)


@router.delete("/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_budget(budget_id: str, user: CurrentUser, db: DbSession):
    """Delete a budget."""
    try:
        bid = uuid.UUID(budget_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Budget not found")

    budget = await _load_budget(bid, user.id, db)
    await db.delete(budget)
    await db.commit()
