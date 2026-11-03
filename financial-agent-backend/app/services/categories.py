"""Category resolution helpers shared by the finance endpoints."""

from __future__ import annotations

import uuid
from typing import Optional, Type

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.expense import ExpenseCategory
from app.models.income import IncomeCategory


async def resolve_expense_category(
    db: AsyncSession,
    user_id: uuid.UUID,
    category_id: Optional[str],
) -> Optional[uuid.UUID]:
    """
    Validate an expense category id.

    Accepts a system category or one owned by the user. Raises 422 for
    malformed ids and for categories the user cannot use.
    """
    return await _resolve(db, ExpenseCategory, user_id, category_id, "expense category")


async def resolve_income_category(
    db: AsyncSession,
    user_id: uuid.UUID,
    category_id: Optional[str],
) -> Optional[uuid.UUID]:
    """Validate an income category id (system or user-owned)."""
    return await _resolve(db, IncomeCategory, user_id, category_id, "income category")


async def _resolve(
    db: AsyncSession,
    model: Type[ExpenseCategory] | Type[IncomeCategory],
    user_id: uuid.UUID,
    category_id: Optional[str],
    label: str,
) -> Optional[uuid.UUID]:
    if category_id in (None, ""):
        return None

    try:
        cid = uuid.UUID(str(category_id))
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid {label} id",
        )

    category = await db.scalar(
        select(model).where(
            model.id == cid,
            or_(model.is_system.is_(True), model.user_id == user_id),
        )
    )
    if category is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{label.capitalize()} not found",
        )
    return category.id
