"""
Budget and budget category allocation models.
"""

import enum
import uuid
from datetime import date
from decimal import Decimal
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import String, Date, Numeric, ForeignKey, Index, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, UUIDMixin, TimestampMixin, GUID

if TYPE_CHECKING:
    from app.models.user import User


class BudgetPeriod(str, enum.Enum):
    """Supported budget period types."""
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"
    CUSTOM = "custom"


class Budget(Base, UUIDMixin, TimestampMixin):
    """
    A budget defines a spending limit for a period.

    Users can set an overall limit and optionally allocate limits
    to specific expense categories.
    """

    __tablename__ = "budgets"

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    period_type: Mapped[BudgetPeriod] = mapped_column(
        Enum(BudgetPeriod, name="budget_period", create_constraint=True),
        default=BudgetPeriod.MONTHLY,
        nullable=False,
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_limit: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2), nullable=False
    )
    currency: Mapped[str] = mapped_column(String(3), default="PKR", nullable=False)

    # ── Relationships ────────────────────────────────────────────────
    user: Mapped["User"] = relationship(back_populates="budgets")
    category_allocations: Mapped[List["BudgetCategory"]] = relationship(
        back_populates="budget", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_budgets_user_period", "user_id", "start_date", "end_date"),
    )


class BudgetCategory(Base, UUIDMixin, TimestampMixin):
    """Category-level spending limit within a budget."""

    __tablename__ = "budget_categories"

    budget_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("budgets.id", ondelete="CASCADE"),
        nullable=False,
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("expense_categories.id", ondelete="CASCADE"),
        nullable=False,
    )
    limit_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2), nullable=False
    )

    # ── Relationships ────────────────────────────────────────────────
    budget: Mapped["Budget"] = relationship(back_populates="category_allocations")
    category: Mapped["ExpenseCategory"] = relationship()


from app.models.expense import ExpenseCategory  # noqa: E402
