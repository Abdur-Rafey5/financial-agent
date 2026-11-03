"""
Financial goals and goal contributions API.

``current_amount`` is always recomputed from the contribution ledger, so the
stored progress can never drift from the recorded contributions.
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
from app.models.goal import FinancialGoal, GoalContribution, GoalStatus
from app.services.events import log_event

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


class GoalCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    target_amount: Decimal = Field(gt=0, max_digits=15, decimal_places=2)
    currency: str = Field(default="PKR", min_length=3, max_length=3)
    target_date: Optional[date] = None


class GoalUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    target_amount: Optional[Decimal] = Field(default=None, gt=0, max_digits=15, decimal_places=2)
    currency: Optional[str] = Field(default=None, min_length=3, max_length=3)
    target_date: Optional[date] = None
    status: Optional[GoalStatus] = None


class GoalResponse(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    target_amount: float
    current_amount: float
    percentage_completed: float
    remaining_amount: float
    currency: str
    target_date: Optional[date] = None
    status: str
    contributions: List[ContributionResponse] = []
    created_at: str
    updated_at: str


def _build_goal_response(goal: FinancialGoal) -> GoalResponse:
    target = float(goal.target_amount)
    current = float(goal.current_amount)
    pct = round(min(100.0, (current / target) * 100), 2) if target > 0 else 0.0

    return GoalResponse(
        id=str(goal.id),
        title=goal.title,
        description=goal.description,
        target_amount=target,
        current_amount=current,
        percentage_completed=pct,
        remaining_amount=round(max(0.0, target - current), 2),
        currency=goal.currency,
        target_date=goal.target_date,
        status=goal.status.value if hasattr(goal.status, "value") else str(goal.status),
        contributions=[
            ContributionResponse(
                id=str(contribution.id),
                goal_id=str(contribution.goal_id),
                amount=float(contribution.amount),
                date=contribution.date,
                notes=contribution.notes,
                created_at=contribution.created_at.isoformat(),
            )
            for contribution in sorted(
                goal.contributions, key=lambda item: (item.date, item.created_at)
            )
        ],
        created_at=goal.created_at.isoformat(),
        updated_at=goal.updated_at.isoformat(),
    )


async def _load_goal(goal_id: uuid.UUID, user_id: uuid.UUID, db) -> FinancialGoal:
    goal = await db.scalar(
        select(FinancialGoal)
        .options(selectinload(FinancialGoal.contributions))
        .execution_options(populate_existing=True)
        .where(and_(FinancialGoal.id == goal_id, FinancialGoal.user_id == user_id))
    )
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal not found")
    return goal


async def _parse_goal_id(goal_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(goal_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Goal not found")


async def _recompute_goal(db, goal: FinancialGoal) -> None:
    """Recompute ``current_amount`` and status from contributions."""
    total = await db.scalar(
        select(func.coalesce(func.sum(GoalContribution.amount), 0)).where(
            GoalContribution.goal_id == goal.id
        )
    )
    goal.current_amount = Decimal(str(total or 0)).quantize(Decimal("0.01"))

    if goal.status != GoalStatus.CANCELLED:
        if goal.target_amount > 0 and goal.current_amount >= goal.target_amount:
            goal.status = GoalStatus.COMPLETED
        elif goal.status == GoalStatus.COMPLETED:
            goal.status = GoalStatus.ACTIVE


# ── Routes ───────────────────────────────────────────────────────────────
@router.get("", response_model=List[GoalResponse])
async def list_goals(
    user: CurrentUser,
    db: DbSession,
    status_filter: Optional[GoalStatus] = Query(None, alias="status"),
):
    """List financial goals with contribution history."""
    filters = [FinancialGoal.user_id == user.id]
    if status_filter:
        filters.append(FinancialGoal.status == status_filter)

    result = await db.execute(
        select(FinancialGoal)
        .options(selectinload(FinancialGoal.contributions))
        .where(and_(*filters))
        .order_by(FinancialGoal.created_at.desc())
    )
    return [_build_goal_response(goal) for goal in result.scalars().all()]


@router.post("", response_model=GoalResponse, status_code=status.HTTP_201_CREATED)
async def create_goal(payload: GoalCreate, user: CurrentUser, db: DbSession):
    """Create a new financial goal."""
    goal = FinancialGoal(
        user_id=user.id,
        title=payload.title.strip(),
        description=payload.description,
        target_amount=payload.target_amount,
        current_amount=Decimal("0.00"),
        currency=payload.currency.upper(),
        target_date=payload.target_date,
        status=GoalStatus.ACTIVE,
    )
    db.add(goal)
    await db.flush()

    log_event(
        db,
        user_id=user.id,
        event_type="goal_created",
        entity_type="goal",
        entity_id=goal.id,
        metadata={"target_amount": float(goal.target_amount)},
    )

    await db.commit()
    return _build_goal_response(await _load_goal(goal.id, user.id, db))


@router.get("/{goal_id}", response_model=GoalResponse)
async def get_goal(goal_id: str, user: CurrentUser, db: DbSession):
    """Get single goal details with contribution history."""
    return _build_goal_response(await _load_goal(await _parse_goal_id(goal_id), user.id, db))


@router.patch("/{goal_id}", response_model=GoalResponse)
async def update_goal(
    goal_id: str, payload: GoalUpdate, user: CurrentUser, db: DbSession
):
    """Update goal attributes or change status."""
    goal = await _load_goal(await _parse_goal_id(goal_id), user.id, db)
    fields = payload.model_fields_set

    if payload.title is not None:
        goal.title = payload.title.strip()
    if "description" in fields:
        goal.description = payload.description
    if payload.target_amount is not None:
        goal.target_amount = payload.target_amount
    if payload.currency is not None:
        goal.currency = payload.currency.upper()
    if "target_date" in fields:
        goal.target_date = payload.target_date
    if payload.status is not None:
        goal.status = payload.status

    await _recompute_goal(db, goal)
    await db.commit()
    return _build_goal_response(await _load_goal(goal.id, user.id, db))


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_goal(goal_id: str, user: CurrentUser, db: DbSession):
    """Delete a financial goal and its contributions."""
    goal = await _load_goal(await _parse_goal_id(goal_id), user.id, db)
    await db.delete(goal)
    await db.commit()


@router.post("/{goal_id}/contribute", response_model=GoalResponse)
async def contribute_to_goal(
    goal_id: str, payload: ContributionCreate, user: CurrentUser, db: DbSession
):
    """Add a manual contribution toward a goal."""
    goal = await _load_goal(await _parse_goal_id(goal_id), user.id, db)

    contribution = GoalContribution(
        goal_id=goal.id,
        amount=payload.amount,
        date=payload.date,
        notes=payload.notes,
    )
    db.add(contribution)
    await db.flush()

    await _recompute_goal(db, goal)
    log_event(
        db,
        user_id=user.id,
        event_type="goal_contribution",
        entity_type="goal",
        entity_id=goal.id,
        metadata={"amount": float(payload.amount)},
    )

    await db.commit()
    return _build_goal_response(await _load_goal(goal.id, user.id, db))


@router.delete(
    "/{goal_id}/contributions/{contribution_id}",
    response_model=GoalResponse,
)
async def delete_contribution(
    goal_id: str,
    contribution_id: str,
    user: CurrentUser,
    db: DbSession,
):
    """Remove a contribution and recompute the goal's progress."""
    goal = await _load_goal(await _parse_goal_id(goal_id), user.id, db)

    try:
        cid = uuid.UUID(contribution_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Contribution not found")

    contribution = await db.scalar(
        select(GoalContribution).where(
            GoalContribution.id == cid,
            GoalContribution.goal_id == goal.id,
        )
    )
    if contribution is None:
        raise HTTPException(status_code=404, detail="Contribution not found")

    await db.delete(contribution)
    await db.flush()
    await _recompute_goal(db, goal)
    await db.commit()
    return _build_goal_response(await _load_goal(goal.id, user.id, db))
