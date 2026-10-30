"""
Business profile, scenario, and investment models.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import String, Date, Numeric, ForeignKey, Index, Text, JSON, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, UUIDMixin, TimestampMixin, GUID

if TYPE_CHECKING:
    from app.models.user import User


class Business(Base, UUIDMixin, TimestampMixin):
    """
    Business profile for businessman users.

    Stores the top-level business information. Revenue and expense
    records are linked through the user's standard financial records
    with business-specific income/expense types.
    """

    __tablename__ = "businesses"

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    business_name: Mapped[str] = mapped_column(String(255), nullable=False)
    business_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    industry: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    available_capital: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(precision=15, scale=2), nullable=True
    )
    currency: Mapped[str] = mapped_column(String(3), default="PKR", nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Relationships ────────────────────────────────────────────────
    user: Mapped["User"] = relationship(back_populates="businesses")
    scenarios: Mapped[List["BusinessScenario"]] = relationship(
        back_populates="business", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_businesses_user_id", "user_id"),
    )


class BusinessScenario(Base, UUIDMixin, TimestampMixin):
    """
    A user-entered business scenario for what-if analysis.

    Assumptions are stored as JSON to support flexible scenario types
    (investment, expansion, hiring, etc.). Results are populated after
    AI-assisted analysis.
    """

    __tablename__ = "business_scenarios"

    business_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    scenario_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # investment, expansion, hiring, equipment, marketing
    assumptions: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    results: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    ai_analysis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Relationships ────────────────────────────────────────────────
    business: Mapped["Business"] = relationship(back_populates="scenarios")

    __table_args__ = (
        Index("ix_business_scenarios_user_id", "user_id"),
    )


class MarketDataSnapshot(Base, UUIDMixin, TimestampMixin):
    """
    Cached market data from external providers.

    Each snapshot stores provider-sourced data with explicit timestamps
    so the UI can show data freshness.
    """

    __tablename__ = "market_data_snapshots"

    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    data_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # quote, daily, weekly, search
    data: Mapped[dict] = mapped_column(JSON, nullable=False)
    source_timestamp: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index("ix_market_data_symbol_type", "symbol", "data_type"),
    )
