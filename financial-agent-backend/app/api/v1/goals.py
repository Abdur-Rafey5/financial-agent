"""
Financial goals and goal contributions API.
"""

import uuid
from datetime import date
from decimal import Decimal
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload

from app.api.dependencies import CurrentUser, DbSession
from app.models.goal import FinancialGoal, GoalContribution, GoalStatus

router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────────────────
class ContributionCreate(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=15, decimal_places=2)
    date: date
    notes: Optional[str] = None


class ContributionResponse(BaseModel):
    id: str
    goal_id: str
    amount: float
    date: date
    notes: Optional[str] = None
    created_at: str

    model_config = {"from_attributes": True}


class GoalCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    target_amount: Decimal = Field(gt=0, max_digits=15, decimal_places=2)
    currency: str = Field(default="PKR", max_length=3)
    target_date: Optional[date] = None


class GoalUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    target_amount: Optional[Decimal] = Field(default=None, gt=0, max_digits=15, decimal_places=2)
    currency: Optional[str] = None
    target_date: Optional[date] = None
    status: Optional[GoalStatus] = None


class GoalResponse(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    target_amount: float
    current_amount: float
    percentage_completed: float
    currency: str
    target_date: Optional[date] = None
    status: str
    contributions: List[ContributionResponse] = []
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


def _build_goal_response(goal: FinancialGoal) -> GoalResponse:
    pct = 0.0
    if float(goal.target_amount) > 0:
        pct = round(min(100.0, (float(goal.current_amount) / float(goal.target_amount)) * 100), 2)

    return GoalResponse(
        id=str(goal.id),
        title=goal.title,
        description=goal.description,
        target_amount=float(goal.target_amount),
        current_amount=float(goal.current_amount),
        percentage_completed=pct,
        currency=goal.currency,
        target_date=goal.target_date,
        status=goal.status.value if hasattr(goal.status, "value") else str(goal.status),
        contributions=[
            ContributionResponse(
                id=str(c.id),
                goal_id=str(c.goal_id),
                amount=float(c.amount),
                date=c.date,
                notes=c.notes,
                created_at=c.created_at.isoformat(),
            )
            for c in (goal.contributions or [])
        ],
        created_at=goal.created_at.isoformat(),
        updated_at=goal.updated_at.isoformat(),
    )


# ── Routes ───────────────────────────────────────────────────────────────
@router.get("", response_model=List[GoalResponse])
async def list_goals(
    user: CurrentUser,
    db: DbSession,
    status_filter: Optional[GoalStatus] = Query(None, alias="status"),
):
    """List financial goals with contributions."""
    filters = [FinancialGoal.user_id == user.id]
    if status_filter:
        filters.append(FinancialGoal.status == status_filter)

    res = await db.execute(
        select(FinancialGoal)
        .options(selectinload(FinancialGoal.contributions))
        .where(and_(*filters))
        .order_by(FinancialGoal.created_at.desc())
    )
    goals = res.scalars().all()
    return [_build_goal_response(g) for g in goals]


@router.post("", response_model=GoalResponse, status_code=status.HTTP_201_CREATED)
async def create_goal(payload: GoalCreate, user: CurrentUser, db: DbSession):
    """Create a new financial goal."""
    goal = FinancialGoal(
        user_id=user.id,
        title=payload.title,
        description=payload.description,
        target_amount=payload.target_amount,
        current_amount=Decimal("0.00"),
        currency=payload.currency.upper(),
        target_date=payload.target_date,
        status=GoalStatus.ACTIVE,
    )
    db.add(goal)
    await db.commit()
    await db.refresh(goal)
    goal.contributions = []
    return _build_goal_response(goal)


@router.get("/{goal_id}", response_model=GoalResponse)
async def get_goal(goal_id: str, user: CurrentUser, db: DbSession):
    """Get single goal details with contribution history."""
    try:
        gid = uuid.UUID(goal_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid goal_id")

    res = await db.execute(
        select(FinancialGoal)
        .options(selectinload(FinancialGoal.contributions))
        .where(and_(FinancialGoal.id == gid, FinancialGoal.user_id == user.id))
    )
    goal = res.scalar_one_or_none()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")

    return _build_goal_response(goal)


@router.patch("/{goal_id}", response_model=GoalResponse)
async def update_goal(goal_id: str, payload: GoalUpdate, user: CurrentUser, db: DbSession):
    """Update goal attributes or change status."""
    try:
        gid = uuid.UUID(goal_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid goal_id")

    res = await db.execute(
        select(FinancialGoal)
        .options(selectinload(FinancialGoal.contributions))
        .where(and_(FinancialGoal.id == gid, FinancialGoal.user_id == user.id))
    )
    goal = res.scalar_one_or_none()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")

    if payload.title is not None:
        goal.title = payload.title
    if payload.description is not None:
        goal.description = payload.description
    if payload.target_amount is not None:
        goal.target_amount = payload.target_amount
    if payload.currency is not None:
        goal.currency = payload.currency.upper()
    if payload.target_date is not None:
        goal.target_date = payload.target_date
    if payload.status is not None:
        goal.status = payload.status

    await db.commit()
    await db.refresh(goal)
    return _build_goal_response(goal)


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_goal(goal_id: str, user: CurrentUser, db: DbSession):
    """Delete a financial goal and its contributions."""
    try:
        gid = uuid.UUID(goal_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid goal_id")

    res = await db.execute(
        select(FinancialGoal).where(and_(FinancialGoal.id == gid, FinancialGoal.user_id == user.id))
    )
    goal = res.scalar_one_or_none()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")

    await db.delete(goal)
    await db.commit()


@router.post("/{goal_id}/contribute", response_model=GoalResponse)
async def contribute_to_goal(
    goal_id: str, payload: ContributionCreate, user: CurrentUser, db: DbSession
):
    """Add a manual contribution toward a goal."""
    try:
        gid = uuid.UUID(goal_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid goal_id")

    res = await db.execute(
        select(FinancialGoal)
        .options(selectinload(FinancialGoal.contributions))
        .where(and_(FinancialGoal.id == gid, FinancialGoal.user_id == user.id))
    )
    goal = res.scalar_one_or_none()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")

    contribution = GoalContribution(
        goal_id=goal.id,
        amount=payload.amount,
        date=payload.date,
        notes=payload.notes,
    )
    db.add(contribution)

    # Update goal's current_amount
    goal.current_amount = goal.current_amount + payload.amount
    if goal.current_amount >= goal.target_amount:
        goal.status = GoalStatus.COMPLETED

    await db.commit()

    # Reload goal
    res = await db.execute(
        select(FinancialGoal)
        .options(selectinload(FinancialGoal.contributions))
        .where(FinancialGoal.id == goal.id)
    )
    return _build_goal_response(res.scalar_one())
