"""
Proactive recommendations API.

Recommendations are produced by the deterministic rules engine in
:mod:`app.services.recommendations`. This router only exposes them: it never
lets the language model invent a recommendation.
"""

import uuid
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import and_, func, select, update

from app.api.dependencies import CurrentUser, DbSession
from app.models.ai import AIRecommendation, RecommendationPriority, RecommendationType
from app.services.recommendations import generate_recommendations

router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────────────────
class RecommendationResponse(BaseModel):
    id: str
    type: str
    title: str
    content: str
    reasoning: Optional[str] = None
    priority: str
    is_read: bool
    is_dismissed: bool
    source_data: Optional[dict] = None
    created_at: str


class RecommendationListResponse(BaseModel):
    items: List[RecommendationResponse]
    total: int
    unread_count: int


class GenerateResponse(BaseModel):
    created: int
    items: List[RecommendationResponse]


def _to_response(record: AIRecommendation) -> RecommendationResponse:
    return RecommendationResponse(
        id=str(record.id),
        type=record.type.value if hasattr(record.type, "value") else str(record.type),
        title=record.title,
        content=record.content,
        reasoning=record.reasoning,
        priority=record.priority.value
        if hasattr(record.priority, "value")
        else str(record.priority),
        is_read=record.is_read,
        is_dismissed=record.is_dismissed,
        source_data=record.source_data,
        created_at=record.created_at.isoformat(),
    )


async def _get_recommendation(
    recommendation_id: str, user_id: uuid.UUID, db
) -> AIRecommendation:
    try:
        rid = uuid.UUID(recommendation_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    record = await db.scalar(
        select(AIRecommendation).where(
            and_(AIRecommendation.id == rid, AIRecommendation.user_id == user_id)
        )
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return record


# ── Routes ───────────────────────────────────────────────────────────────
@router.get("", response_model=RecommendationListResponse)
async def list_recommendations(
    user: CurrentUser,
    db: DbSession,
    unread_only: bool = Query(False),
    type_filter: Optional[RecommendationType] = Query(None, alias="type"),
    priority: Optional[RecommendationPriority] = Query(None),
):
    """List active recommendations, newest first."""
    filters = [
        AIRecommendation.user_id == user.id,
        AIRecommendation.is_dismissed.is_(False),
    ]
    if unread_only:
        filters.append(AIRecommendation.is_read.is_(False))
    if type_filter:
        filters.append(AIRecommendation.type == type_filter)
    if priority:
        filters.append(AIRecommendation.priority == priority)

    result = await db.execute(
        select(AIRecommendation)
        .where(and_(*filters))
        .order_by(AIRecommendation.created_at.desc())
    )
    records = result.scalars().all()

    unread = await db.scalar(
        select(func.count(AIRecommendation.id)).where(
            AIRecommendation.user_id == user.id,
            AIRecommendation.is_read.is_(False),
            AIRecommendation.is_dismissed.is_(False),
        )
    )
    return RecommendationListResponse(
        items=[_to_response(record) for record in records],
        total=len(records),
        unread_count=int(unread or 0),
    )


@router.post("/generate", response_model=GenerateResponse)
async def generate(
    user: CurrentUser,
    db: DbSession,
    force: bool = Query(False, description="Skip the duplicate window check"),
):
    """
    Run the rules engine and persist any new recommendations.

    Idempotent by design: titles produced within the last 7 days (or dismissed
    within 30 days) are not duplicated.
    """
    created = await generate_recommendations(db, user, force=force)
    return GenerateResponse(
        created=len(created),
        items=[_to_response(record) for record in created],
    )


@router.patch("/read-all", response_model=RecommendationListResponse)
async def mark_all_read(user: CurrentUser, db: DbSession):
    """Mark every visible, unread recommendation as read."""
    await db.execute(
        update(AIRecommendation)
        .where(
            AIRecommendation.user_id == user.id,
            AIRecommendation.is_read.is_(False),
            AIRecommendation.is_dismissed.is_(False),
        )
        .values(is_read=True)
    )
    await db.commit()

    result = await db.execute(
        select(AIRecommendation)
        .where(
            AIRecommendation.user_id == user.id,
            AIRecommendation.is_dismissed.is_(False),
        )
        .order_by(AIRecommendation.created_at.desc())
    )
    records = result.scalars().all()
    return RecommendationListResponse(
        items=[_to_response(record) for record in records],
        total=len(records),
        unread_count=0,
    )


@router.patch("/{recommendation_id}/read", response_model=RecommendationResponse)
async def mark_as_read(recommendation_id: str, user: CurrentUser, db: DbSession):
    """Mark one recommendation as read."""
    record = await _get_recommendation(recommendation_id, user.id, db)
    record.is_read = True
    await db.commit()
    await db.refresh(record)
    return _to_response(record)


@router.patch("/{recommendation_id}/dismiss", status_code=status.HTTP_204_NO_CONTENT)
async def dismiss_recommendation(
    recommendation_id: str, user: CurrentUser, db: DbSession
):
    """Dismiss a recommendation so the rules engine will not recreate it soon."""
    record = await _get_recommendation(recommendation_id, user.id, db)
    record.is_dismissed = True
    record.is_read = True
    await db.commit()
