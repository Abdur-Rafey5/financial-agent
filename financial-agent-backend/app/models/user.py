"""
User and profile models.

A user has exactly one profile which stores their selected category
(Student, Employee, Businessman) and category-specific fields.
"""

import enum
import uuid
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import String, Boolean, Enum, Numeric, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, UUIDMixin, TimestampMixin, GUID


class UserCategory(str, enum.Enum):
    """The three supported user categories."""
    STUDENT = "student"
    EMPLOYEE = "employee"
    BUSINESSMAN = "businessman"


class User(Base, UUIDMixin, TimestampMixin):
    """Registered user account."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    hashed_password: Mapped[str] = mapped_column(String(512), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # ── Relationships ────────────────────────────────────────────────
    profile: Mapped[Optional["UserProfile"]] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    income_records: Mapped[List["IncomeRecord"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    expense_records: Mapped[List["ExpenseRecord"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    budgets: Mapped[List["Budget"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    financial_goals: Mapped[List["FinancialGoal"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    businesses: Mapped[List["Business"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    ai_conversations: Mapped[List["AIConversation"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    ai_recommendations: Mapped[List["AIRecommendation"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class UserProfile(Base, UUIDMixin, TimestampMixin):
    """
    Category-specific profile information.

    The category determines which dashboard and workflows apply.
    Category-specific fields (allowance, salary) are nullable so a
    single table can serve all three categories.
    """

    __tablename__ = "user_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    category: Mapped[UserCategory] = mapped_column(
        Enum(UserCategory, name="user_category", create_constraint=True),
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(String(3), default="PKR", nullable=False)
    onboarding_completed: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    # ── Student-specific ─────────────────────────────────────────────
    allowance_amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(precision=15, scale=2), nullable=True
    )
    allowance_frequency: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True
    )  # weekly, monthly, etc.

    # ── Employee-specific ────────────────────────────────────────────
    monthly_salary: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(precision=15, scale=2), nullable=True
    )
    employer_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # ── Relationships ────────────────────────────────────────────────
    user: Mapped["User"] = relationship(back_populates="profile")


# Forward references for relationships defined in other model files
# These are resolved at import time via app/models/__init__.py
from app.models.income import IncomeRecord  # noqa: E402
from app.models.expense import ExpenseRecord  # noqa: E402
from app.models.budget import Budget  # noqa: E402
from app.models.goal import FinancialGoal  # noqa: E402
from app.models.business import Business  # noqa: E402
from app.models.ai import AIConversation, AIRecommendation  # noqa: E402
