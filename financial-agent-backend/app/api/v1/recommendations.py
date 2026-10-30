"""
Proactive AI financial recommendations API endpoints.
"""

import uuid
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, and_

from app.api.dependencies import CurrentUser, DbSession
from app.models.ai import AIRecommendation, RecommendationPriority, RecommendationType

router = APIRouter()


class RecommendationResponse(BaseModel):
    id: str
    type: str
    title: str
    content: str
    reasoning: Optional[str] = None
    priority: str
    is_read: bool
    is_dismissed: bool
    created_at: str

    model_config = {"from_attributes": True}


@router.get("", response_model=List[RecommendationResponse])
async def list_recommendations(
    user: CurrentUser,
    db: DbSession,
    unread_only: bool = Query(False),
):
    """Get AI recommendations for the authenticated user."""
    filters = [AIRecommendation.user_id == user.id, AIRecommendation.is_dismissed == False]  # noqa: E712
    if unread_only:
        filters.append(AIRecommendation.is_read == False)  # noqa: E712

    res = await db.execute(
        select(AIRecommendation)
        .where(and_(*filters))
        .order_by(AIRecommendation.created_at.desc())
    )
    recs = res.scalars().all()
    return [
        RecommendationResponse(
            id=str(r.id),
            type=r.type.value if hasattr(r.type, "value") else str(r.type),
            title=r.title,
            content=r.content,
            reasoning=r.reasoning,
            priority=r.priority.value if hasattr(r.priority, "value") else str(r.priority),
            is_read=r.is_read,
            is_dismissed=r.is_dismissed,
            created_at=r.created_at.isoformat(),
        )
        for r in recs
    ]


@router.patch("/{recommendation_id}/read", response_model=RecommendationResponse)
async def mark_as_read(recommendation_id: str, user: CurrentUser, db: DbSession):
    """Mark a recommendation as read."""
    try:
        rid = uuid.UUID(recommendation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid recommendation_id")

    res = await db.execute(
        select(AIRecommendation).where(
            and_(AIRecommendation.id == rid, AIRecommendation.user_id == user.id)
        )
    )
    rec = res.scalar_one_or_none()
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    rec.is_read = True
    await db.commit()
    await db.refresh(rec)

    return RecommendationResponse(
        id=str(rec.id),
        type=rec.type.value if hasattr(rec.type, "value") else str(rec.type),
        title=rec.title,
        content=rec.content,
        reasoning=rec.reasoning,
        priority=rec.priority.value if hasattr(rec.priority, "value") else str(rec.priority),
        is_read=rec.is_read,
        is_dismissed=rec.is_dismissed,
        created_at=rec.created_at.isoformat(),
    )


@router.patch("/{recommendation_id}/dismiss", status_code=status.HTTP_204_NO_CONTENT)
async def dismiss_recommendation(recommendation_id: str, user: CurrentUser, db: DbSession):
    """Dismiss a recommendation so it won't appear again."""
    try:
        rid = uuid.UUID(recommendation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid recommendation_id")

    res = await db.execute(
        select(AIRecommendation).where(
            and_(AIRecommendation.id == rid, AIRecommendation.user_id == user.id)
        )
    )
    rec = res.scalar_one_or_none()
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    rec.is_dismissed = True
    await db.commit()
