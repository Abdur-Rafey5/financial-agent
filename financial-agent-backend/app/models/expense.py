"""
Expense record and expense category models.
"""

import uuid
from datetime import date
from decimal import Decimal
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Date, Numeric, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, UUIDMixin, TimestampMixin, GUID

if TYPE_CHECKING:
    from app.models.user import User


class ExpenseCategory(Base, UUIDMixin, TimestampMixin):
    """User-customizable or system-default expense categories."""

    __tablename__ = "expense_categories"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,  # NULL = system default category
    )
    is_system: Mapped[bool] = mapped_column(default=False, nullable=False)
    icon: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    color: Mapped[Optional[str]] = mapped_column(String(7), nullable=True)  # hex color

    __table_args__ = (
        Index("ix_expense_categories_user_id", "user_id"),
    )


class ExpenseRecord(Base, UUIDMixin, TimestampMixin):
    """A single expense entry for a user."""

    __tablename__ = "expense_records"

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
    category_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("expense_categories.id", ondelete="SET NULL"),
        nullable=True,
    )
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Relationships ────────────────────────────────────────────────
    user: Mapped["User"] = relationship(back_populates="expense_records")
    category: Mapped[Optional["ExpenseCategory"]] = relationship()

    __table_args__ = (
        Index("ix_expense_records_user_date", "user_id", "date"),
        Index("ix_expense_records_user_category", "user_id", "category_id"),
    )
