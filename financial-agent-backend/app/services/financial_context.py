"""
Build a compact, structured financial snapshot for a user.

The snapshot powers the dashboard, the conversational assistant prompt and
the proactive recommendation rules. Keeping the aggregation in one place
guarantees every AI surface reasons over the same numbers.
"""

from __future__ import annotations

import calendar
import uuid
from datetime import date, timedelta
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.budget import Budget, BudgetCategory
from app.models.business import Business
from app.models.expense import ExpenseCategory, ExpenseRecord
from app.models.goal import FinancialGoal, GoalStatus
from app.models.income import IncomeRecord
from app.models.user import User


def _month_bounds(reference: date) -> tuple[date, date]:
    start = reference.replace(day=1)
    last_day = calendar.monthrange(start.year, start.month)[1]
    return start, start.replace(day=last_day)


def _shift_month(reference: date, offset: int) -> date:
    month_index = reference.year * 12 + (reference.month - 1) + offset
    year, month = divmod(month_index, 12)
    return date(year, month + 1, 1)


def _safe_pct(part: float, whole: float) -> float:
    if whole <= 0:
        return 0.0
    return round(part / whole * 100, 1)


async def _sum_records(
    db: AsyncSession,
    model,
    user_id: uuid.UUID,
    start: date,
    end: date,
) -> float:
    value = await db.scalar(
        select(func.coalesce(func.sum(model.amount), 0)).where(
            and_(model.user_id == user_id, model.date >= start, model.date <= end)
        )
    )
    return round(float(value or 0), 2)


async def build_financial_context(
    db: AsyncSession,
    user: User,
    *,
    today: date | None = None,
) -> dict[str, Any]:
    """Aggregate income, expenses, budgets, goals and business data."""
    today = today or date.today()
    month_start, month_end = _month_bounds(today)
    previous_start, previous_end = _month_bounds(_shift_month(month_start, -1))

    month_income = await _sum_records(db, IncomeRecord, user.id, month_start, month_end)
    month_expenses = await _sum_records(db, ExpenseRecord, user.id, month_start, month_end)
    previous_income = await _sum_records(db, IncomeRecord, user.id, previous_start, previous_end)
    previous_expenses = await _sum_records(db, ExpenseRecord, user.id, previous_start, previous_end)

    net_savings = round(month_income - month_expenses, 2)
    savings_rate = _safe_pct(net_savings, month_income)

    # ── Top expense categories ───────────────────────────────────────
    category_rows = await db.execute(
        select(
            ExpenseCategory.name,
            ExpenseCategory.color,
            func.coalesce(func.sum(ExpenseRecord.amount), 0).label("total"),
        )
        .outerjoin(ExpenseCategory, ExpenseRecord.category_id == ExpenseCategory.id)
        .where(
            and_(
                ExpenseRecord.user_id == user.id,
                ExpenseRecord.date >= month_start,
                ExpenseRecord.date <= month_end,
            )
        )
        .group_by(ExpenseCategory.name, ExpenseCategory.color)
        .order_by(func.sum(ExpenseRecord.amount).desc())
        .limit(6)
    )
    top_categories = [
        {
            "name": name or "Uncategorized",
            "color": color or "#64748b",
            "amount": round(float(total or 0), 2),
            "percentage": _safe_pct(float(total or 0), month_expenses),
        }
        for name, color, total in category_rows.all()
    ]

    # ── Budgets ──────────────────────────────────────────────────────
    budget_result = await db.execute(
        select(Budget)
        .options(
            selectinload(Budget.category_allocations).selectinload(BudgetCategory.category)
        )
        .where(Budget.user_id == user.id)
        .order_by(Budget.end_date.desc())
    )
    budgets = []
    for budget in budget_result.scalars().all():
        spent = await _sum_records(db, ExpenseRecord, user.id, budget.start_date, budget.end_date)
        limit = float(budget.total_limit)
        allocations = []
        for allocation in budget.category_allocations:
            allocated_spend = await db.scalar(
                select(func.coalesce(func.sum(ExpenseRecord.amount), 0)).where(
                    and_(
                        ExpenseRecord.user_id == user.id,
                        ExpenseRecord.category_id == allocation.category_id,
                        ExpenseRecord.date >= budget.start_date,
                        ExpenseRecord.date <= budget.end_date,
                    )
                )
            )
            allocations.append(
                {
                    "category": allocation.category.name if allocation.category else "Uncategorized",
                    "limit": float(allocation.limit_amount),
                    "spent": round(float(allocated_spend or 0), 2),
                }
            )
        budgets.append(
            {
                "id": str(budget.id),
                "name": budget.name,
                "start_date": budget.start_date.isoformat(),
                "end_date": budget.end_date.isoformat(),
                "limit": limit,
                "spent": spent,
                "remaining": round(limit - spent, 2),
                "usage_pct": _safe_pct(spent, limit),
                "is_active": budget.start_date <= today <= budget.end_date,
                "allocations": allocations,
            }
        )

    # ── Goals ────────────────────────────────────────────────────────
    goal_result = await db.execute(
        select(FinancialGoal)
        .where(FinancialGoal.user_id == user.id)
        .order_by(FinancialGoal.created_at.desc())
    )
    goals = []
    for goal in goal_result.scalars().all():
        target = float(goal.target_amount)
        current = float(goal.current_amount)
        days_left = (goal.target_date - today).days if goal.target_date else None
        goals.append(
            {
                "id": str(goal.id),
                "title": goal.title,
                "target": target,
                "current": current,
                "progress_pct": min(100.0, _safe_pct(current, target)),
                "status": goal.status.value if hasattr(goal.status, "value") else str(goal.status),
                "target_date": goal.target_date.isoformat() if goal.target_date else None,
                "days_left": days_left,
            }
        )

    # ── Six month trend ──────────────────────────────────────────────
    trend = []
    for offset in range(-5, 1):
        start, end = _month_bounds(_shift_month(month_start, offset))
        income = await _sum_records(db, IncomeRecord, user.id, start, end)
        expenses = await _sum_records(db, ExpenseRecord, user.id, start, end)
        trend.append(
            {
                "month": start.strftime("%b %Y"),
                "income": income,
                "expenses": expenses,
                "net": round(income - expenses, 2),
            }
        )

    # ── Recent transactions ──────────────────────────────────────────
    recent_income = (
        await db.scalars(
            select(IncomeRecord)
            .where(IncomeRecord.user_id == user.id)
            .order_by(IncomeRecord.date.desc(), IncomeRecord.created_at.desc())
            .limit(8)
        )
    ).all()
    recent_expenses = (
        await db.scalars(
            select(ExpenseRecord)
            .where(ExpenseRecord.user_id == user.id)
            .order_by(ExpenseRecord.date.desc(), ExpenseRecord.created_at.desc())
            .limit(8)
        )
    ).all()

    transactions = [
        {
            "id": str(record.id),
            "type": "income",
            "description": record.source,
            "amount": float(record.amount),
            "date": record.date.isoformat(),
            "category": record.income_type.value if hasattr(record.income_type, "value") else None,
        }
        for record in recent_income
    ] + [
        {
            "id": str(record.id),
            "type": "expense",
            "description": record.description,
            "amount": float(record.amount),
            "date": record.date.isoformat(),
            "category": None,
        }
        for record in recent_expenses
    ]
    transactions.sort(key=lambda item: item["date"], reverse=True)

    # ── Business (businessman track) ─────────────────────────────────
    business = await db.scalar(select(Business).where(Business.user_id == user.id))
    business_data = None
    if business:
        business_data = {
            "name": business.business_name,
            "type": business.business_type,
            "industry": business.industry,
            "available_capital": float(business.available_capital or 0),
            "currency": business.currency,
        }

    profile = user.profile
    category = (
        profile.category.value
        if profile and hasattr(profile.category, "value")
        else str(profile.category) if profile else "employee"
    )
    currency = profile.currency if profile else "PKR"

    metrics: dict[str, Any] = {}
    if category == "student":
        days_left = max(1, month_end.day - today.day + 1)
        metrics = {
            "days_left_in_month": days_left,
            "safe_daily_spend": round(max(0.0, net_savings) / days_left, 2),
            "allowance_used_pct": _safe_pct(month_expenses, month_income),
        }
    elif category == "employee":
        metrics = {
            "recommended_savings_20pct": round(month_income * 0.2, 2),
            "savings_target_met": net_savings >= month_income * 0.2,
            "disposable_income": net_savings,
        }
    elif category == "businessman":
        metrics = {
            "net_cash_flow": net_savings,
            "gross_margin_pct": _safe_pct(net_savings, month_income),
            "available_capital": business_data["available_capital"] if business_data else 0.0,
        }

    return {
        "user": {
            "id": str(user.id),
            "name": user.full_name,
            "email": user.email,
            "category": category,
            "currency": currency,
        },
        "period": {
            "month_start": month_start.isoformat(),
            "month_end": month_end.isoformat(),
            "today": today.isoformat(),
        },
        "month": {
            "income": month_income,
            "expenses": month_expenses,
            "net_savings": net_savings,
            "savings_rate_pct": savings_rate,
            "previous_income": previous_income,
            "previous_expenses": previous_expenses,
            "expense_change_pct": _safe_pct(month_expenses - previous_expenses, previous_expenses)
            if previous_expenses
            else 0.0,
        },
        "top_expense_categories": top_categories,
        "budgets": budgets,
        "goals": goals,
        "trend": trend,
        "recent_transactions": transactions[:10],
        "business": business_data,
        "metrics": metrics,
    }


def month_bounds(reference: date) -> tuple[date, date]:
    """Public helper: first and last day of the month containing ``reference``."""
    return _month_bounds(reference)


def shift_month(reference: date, offset: int) -> date:
    """Public helper: first day of the month ``offset`` months away."""
    return _shift_month(reference, offset)


def context_to_prompt(context: dict[str, Any]) -> str:
    """Render the snapshot as compact plain text for an LLM prompt."""
    month = context["month"]
    user = context["user"]
    lines = [
        f"User: {user['name']} ({user['category']} track, currency {user['currency']})",
        f"Current month: {context['period']['month_start']} to {context['period']['month_end']}",
        f"Income this month: {month['income']:.2f}",
        f"Expenses this month: {month['expenses']:.2f}",
        f"Net savings: {month['net_savings']:.2f} ({month['savings_rate_pct']}% savings rate)",
        f"Previous month expenses: {month['previous_expenses']:.2f}",
    ]

    if context["top_expense_categories"]:
        lines.append("Top expense categories:")
        for item in context["top_expense_categories"]:
            lines.append(f"- {item['name']}: {item['amount']:.2f} ({item['percentage']}%)")

    if context["budgets"]:
        lines.append("Budgets:")
        for budget in context["budgets"][:4]:
            lines.append(
                f"- {budget['name']}: spent {budget['spent']:.2f} of "
                f"{budget['limit']:.2f} ({budget['usage_pct']}%)"
            )

    if context["goals"]:
        lines.append("Goals:")
        for goal in context["goals"][:4]:
            lines.append(
                f"- {goal['title']}: {goal['progress_pct']}% complete, "
                f"target {goal['target']:.2f}, status {goal['status']}"
            )

    if context["business"]:
        business = context["business"]
        lines.append(
            f"Business: {business['name']} ({business['industry'] or business['type'] or 'unspecified'}), "
            f"available capital {business['available_capital']:.2f}"
        )

    if context["metrics"]:
        metrics = ", ".join(f"{key}={value}" for key, value in context["metrics"].items())
        lines.append(f"Track metrics: {metrics}")

    return "\n".join(lines)
