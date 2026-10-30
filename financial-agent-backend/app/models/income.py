"""
Income record and income category models.
"""

import enum
import uuid
from datetime import date
from decimal import Decimal
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Date, Numeric, ForeignKey, Index, Enum, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, UUIDMixin, TimestampMixin, GUID

if TYPE_CHECKING:
    from app.models.user import User


class IncomeType(str, enum.Enum):
    """Types of income."""
    SALARY = "salary"
    ALLOWANCE = "allowance"
    FREELANCE = "freelance"
    BUSINESS_REVENUE = "business_revenue"
    INVESTMENT = "investment"
    GIFT = "gift"
    REFUND = "refund"
    OTHER = "other"


class IncomeFrequency(str, enum.Enum):
    """Frequency for recurring income."""
    ONE_TIME = "one_time"
    DAILY = "daily"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


class IncomeCategory(Base, UUIDMixin, TimestampMixin):
    """User-customizable or system-default income categories."""

    __tablename__ = "income_categories"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,  # NULL = system default category
    )
    is_system: Mapped[bool] = mapped_column(default=False, nullable=False)

    __table_args__ = (
        Index("ix_income_categories_user_id", "user_id"),
    )


class IncomeRecord(Base, UUIDMixin, TimestampMixin):
    """A single income entry for a user."""

    __tablename__ = "income_records"

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2), nullable=False
    )
    currency: Mapped[str] = mapped_column(String(3), default="PKR", nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    income_type: Mapped[IncomeType] = mapped_column(
        Enum(IncomeType, name="income_type", create_constraint=True),
        default=IncomeType.OTHER,
        nullable=False,
    )
    category_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("income_categories.id", ondelete="SET NULL"),
        nullable=True,
    )
    frequency: Mapped[Optional[IncomeFrequency]] = mapped_column(
        Enum(IncomeFrequency, name="income_frequency", create_constraint=True),
        nullable=True,
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Relationships ────────────────────────────────────────────────
    user: Mapped["User"] = relationship(back_populates="income_records")
    category: Mapped[Optional["IncomeCategory"]] = relationship()

    __table_args__ = (
        Index("ix_income_records_user_date", "user_id", "date"),
    )
