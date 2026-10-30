"""
Financial goal and goal contribution models.
"""

import enum
import uuid
from datetime import date
from decimal import Decimal
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import String, Date, Numeric, ForeignKey, Index, Enum, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, UUIDMixin, TimestampMixin, GUID

if TYPE_CHECKING:
    from app.models.user import User


class GoalStatus(str, enum.Enum):
    """Goal lifecycle states."""
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class FinancialGoal(Base, UUIDMixin, TimestampMixin):
    """
    A financial goal with a target amount and optional deadline.

    Progress is tracked through explicit GoalContribution records
    to maintain a clear audit trail.
    """

    __tablename__ = "financial_goals"

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    target_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2), nullable=False
    )
    current_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2), default=Decimal("0.00"), nullable=False
    )
    currency: Mapped[str] = mapped_column(String(3), default="PKR", nullable=False)
    target_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[GoalStatus] = mapped_column(
        Enum(GoalStatus, name="goal_status", create_constraint=True),
        default=GoalStatus.ACTIVE,
        nullable=False,
    )

    # ── Relationships ────────────────────────────────────────────────
    user: Mapped["User"] = relationship(back_populates="financial_goals")
    contributions: Mapped[List["GoalContribution"]] = relationship(
        back_populates="goal", cascade="all, delete-orphan",
        order_by="GoalContribution.date.desc()",
    )

    __table_args__ = (
        Index("ix_financial_goals_user_status", "user_id", "status"),
    )


class GoalContribution(Base, UUIDMixin, TimestampMixin):
    """
    A single contribution (progress entry) toward a financial goal.

    Each contribution represents money actually saved or a user-entered
    progress amount. The goal's current_amount is the sum of all
    contributions.
    """

    __tablename__ = "goal_contributions"

    goal_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("financial_goals.id", ondelete="CASCADE"),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2), nullable=False
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Relationships ────────────────────────────────────────────────
    goal: Mapped["FinancialGoal"] = relationship(back_populates="contributions")

    __table_args__ = (
        Index("ix_goal_contributions_goal_date", "goal_id", "date"),
    )
