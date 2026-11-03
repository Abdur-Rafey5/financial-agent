"""
Idempotent database seeding.

The application relies on a set of system-default categories so that new
users can immediately start recording money movements without having to
create categories first. This module also optionally creates a demo account
with realistic data so the product can be explored without manual setup.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.security import hash_password
from app.models.budget import Budget, BudgetCategory, BudgetPeriod
from app.models.expense import ExpenseCategory, ExpenseRecord
from app.models.goal import FinancialGoal, GoalContribution, GoalStatus
from app.models.income import IncomeCategory, IncomeRecord, IncomeType
from app.models.user import User, UserCategory, UserProfile

logger = logging.getLogger(__name__)

DEMO_EMAIL = "demo@finagent.app"
DEMO_PASSWORD = "Demo1234!"

# (name, icon, color)
DEFAULT_EXPENSE_CATEGORIES: list[tuple[str, str, str]] = [
    ("Food & Dining", "utensils", "#f97316"),
    ("Groceries", "shopping-basket", "#22c55e"),
    ("Transport", "car", "#3b82f6"),
    ("Housing & Rent", "home", "#8b5cf6"),
    ("Utilities", "zap", "#eab308"),
    ("Education", "graduation-cap", "#06b6d4"),
    ("Health", "heart-pulse", "#ef4444"),
    ("Entertainment", "clapperboard", "#ec4899"),
    ("Shopping", "shopping-bag", "#a855f7"),
    ("Subscriptions", "repeat", "#14b8a6"),
    ("Business", "briefcase", "#6366f1"),
    ("Travel", "plane", "#0ea5e9"),
    ("Other", "circle-dot", "#64748b"),
]

DEFAULT_INCOME_CATEGORIES: list[str] = [
    "Salary",
    "Allowance",
    "Freelance",
    "Business Revenue",
    "Investment",
    "Gift",
    "Other",
]


async def seed_default_categories(session: AsyncSession) -> None:
    """Create the system default income and expense categories once."""
    existing_expense = await session.scalar(
        select(func.count(ExpenseCategory.id)).where(ExpenseCategory.is_system.is_(True))
    )
    if not existing_expense:
        session.add_all(
            ExpenseCategory(
                name=name,
                icon=icon,
                color=color,
                is_system=True,
                user_id=None,
            )
            for name, icon, color in DEFAULT_EXPENSE_CATEGORIES
        )
        logger.info("Seeded %s default expense categories", len(DEFAULT_EXPENSE_CATEGORIES))

    existing_income = await session.scalar(
        select(func.count(IncomeCategory.id)).where(IncomeCategory.is_system.is_(True))
    )
    if not existing_income:
        session.add_all(
            IncomeCategory(name=name, is_system=True, user_id=None)
            for name in DEFAULT_INCOME_CATEGORIES
        )
        logger.info("Seeded %s default income categories", len(DEFAULT_INCOME_CATEGORIES))


async def seed_demo_account(session: AsyncSession) -> User | None:
    """
    Create a ready-to-explore demo account with a month of transactions.

    Returns the demo user when it was created, otherwise ``None``.
    """
    existing = await session.scalar(select(User).where(User.email == DEMO_EMAIL))
    if existing is not None:
        return None

    user = User(
        email=DEMO_EMAIL,
        hashed_password=hash_password(DEMO_PASSWORD),
        full_name="Demo Student",
        is_active=True,
    )
    session.add(user)
    await session.flush()

    session.add(
        UserProfile(
            user_id=user.id,
            category=UserCategory.STUDENT,
            currency="PKR",
            onboarding_completed=True,
            allowance_amount=Decimal("45000.00"),
            allowance_frequency="monthly",
        )
    )

    today = date.today()
    start_of_month = today.replace(day=1)

    session.add(
        IncomeRecord(
            user_id=user.id,
            amount=Decimal("45000.00"),
            currency="PKR",
            date=start_of_month,
            source="Monthly allowance",
            income_type=IncomeType.ALLOWANCE,
            frequency="monthly",
        )
    )
    session.add(
        IncomeRecord(
            user_id=user.id,
            amount=Decimal("12000.00"),
            currency="PKR",
            date=start_of_month + timedelta(days=5),
            source="Freelance design work",
            income_type=IncomeType.FREELANCE,
        )
    )

    expense_plan = [
        ("Food & Dining", 6800, "Cafe and takeout"),
        ("Groceries", 4200, "Monthly groceries"),
        ("Transport", 3100, "Ride hailing"),
        ("Education", 5500, "Online course"),
        ("Entertainment", 2400, "Movie night"),
        ("Subscriptions", 1600, "Music and cloud storage"),
        ("Shopping", 3900, "New shoes"),
        ("Utilities", 2200, "Internet and phone"),
    ]
    categories = {
        category.name: category
        for category in (
            await session.scalars(select(ExpenseCategory).where(ExpenseCategory.is_system.is_(True)))
        ).all()
    }
    for index, (name, amount, description) in enumerate(expense_plan):
        category = categories.get(name)
        session.add(
            ExpenseRecord(
                user_id=user.id,
                amount=Decimal(amount),
                currency="PKR",
                date=start_of_month + timedelta(days=index + 1),
                description=description,
                category_id=category.id if category else None,
            )
        )

    budget = Budget(
        user_id=user.id,
        name=f"Monthly budget — {start_of_month.strftime('%B %Y')}",
        period_type=BudgetPeriod.MONTHLY,
        start_date=start_of_month,
        end_date=(start_of_month + timedelta(days=32)).replace(day=1) - timedelta(days=1),
        total_limit=Decimal("40000.00"),
        currency="PKR",
    )
    session.add(budget)
    await session.flush()

    for name, limit in [("Food & Dining", 8000), ("Transport", 4000), ("Entertainment", 3000)]:
        category = categories.get(name)
        if category:
            session.add(
                BudgetCategory(
                    budget_id=budget.id,
                    category_id=category.id,
                    limit_amount=Decimal(limit),
                )
            )

    laptop = FinancialGoal(
        user_id=user.id,
        title="New laptop for development",
        description="Save for a reliable machine for AI projects.",
        target_amount=Decimal("180000.00"),
        current_amount=Decimal("52000.00"),
        currency="PKR",
        target_date=today + timedelta(days=90),
        status=GoalStatus.ACTIVE,
    )
    emergency = FinancialGoal(
        user_id=user.id,
        title="Emergency fund",
        description="Three months of essential spending.",
        target_amount=Decimal("100000.00"),
        current_amount=Decimal("25000.00"),
        currency="PKR",
        target_date=today + timedelta(days=180),
        status=GoalStatus.ACTIVE,
    )
    session.add_all([laptop, emergency])
    await session.flush()

    session.add_all(
        [
            GoalContribution(
                goal_id=laptop.id,
                amount=Decimal("20000.00"),
                date=start_of_month,
                notes="Initial transfer",
            ),
            GoalContribution(
                goal_id=laptop.id,
                amount=Decimal("32000.00"),
                date=today - timedelta(days=2),
                notes="Monthly savings",
            ),
            GoalContribution(
                goal_id=emergency.id,
                amount=Decimal("25000.00"),
                date=today - timedelta(days=7),
                notes="Emergency reserve",
            ),
        ]
    )

    await session.commit()
    logger.info("Created demo account %s", DEMO_EMAIL)

    refreshed = await session.execute(
        select(User).options(selectinload(User.profile)).where(User.id == user.id)
    )
    return refreshed.scalar_one()


async def seed_all(session: AsyncSession, *, include_demo: bool | None = None) -> None:
    """Run all configured seeding steps inside one session."""
    if settings.SEED_DEFAULT_CATEGORIES:
        await seed_default_categories(session)

    include_demo = settings.SEED_DEMO_DATA if include_demo is None else include_demo
    if include_demo:
        await seed_demo_account(session)

    await session.commit()
