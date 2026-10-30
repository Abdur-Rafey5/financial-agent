"""
Dashboard aggregation API — category-specific summaries for Student, Employee, Businessman.
"""

from datetime import date, timedelta
from typing import Dict, Any, List

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select, func, and_

from app.api.dependencies import CurrentUser, DbSession
from app.models.income import IncomeRecord
from app.models.expense import ExpenseRecord, ExpenseCategory
from app.models.budget import Budget
from app.models.goal import FinancialGoal
from app.models.business import Business

router = APIRouter()


class DashboardSummaryResponse(BaseModel):
    category: str
    currency: str
    total_income_this_month: float
    total_expenses_this_month: float
    net_savings_this_month: float
    savings_rate_pct: float
    recent_transactions: List[Dict[str, Any]]
    active_goals_count: int
    active_budgets_count: int
    category_metrics: Dict[str, Any]


@router.get("/summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(user: CurrentUser, db: DbSession):
    """Aggregate financial snapshot tailored to the user category (Student, Employee, Businessman)."""
    today = date.today()
    start_of_month = date(today.year, today.month, 1)

    # Total income this month
    inc_res = await db.execute(
        select(func.coalesce(func.sum(IncomeRecord.amount), 0)).where(
            and_(
                IncomeRecord.user_id == user.id,
                IncomeRecord.date >= start_of_month,
                IncomeRecord.date <= today,
            )
        )
    )
    month_income = float(inc_res.scalar_one())

    # Total expenses this month
    exp_res = await db.execute(
        select(func.coalesce(func.sum(ExpenseRecord.amount), 0)).where(
            and_(
                ExpenseRecord.user_id == user.id,
                ExpenseRecord.date >= start_of_month,
                ExpenseRecord.date <= today,
            )
        )
    )
    month_expenses = float(exp_res.scalar_one())

    net_savings = month_income - month_expenses
    savings_rate = round((net_savings / month_income * 100), 1) if month_income > 0 else 0.0

    # Recent transactions (mix of income and expense)
    recent_inc = await db.execute(
        select(IncomeRecord)
        .where(IncomeRecord.user_id == user.id)
        .order_by(IncomeRecord.date.desc())
        .limit(5)
    )
    recent_exp = await db.execute(
        select(ExpenseRecord)
        .where(ExpenseRecord.user_id == user.id)
        .order_by(ExpenseRecord.date.desc())
        .limit(5)
    )

    transactions = []
    for inc in recent_inc.scalars().all():
        transactions.append({
            "id": str(inc.id),
            "type": "income",
            "source": inc.source,
            "amount": float(inc.amount),
            "date": inc.date.isoformat(),
        })
    for exp in recent_exp.scalars().all():
        transactions.append({
            "id": str(exp.id),
            "type": "expense",
            "source": exp.description,
            "amount": float(exp.amount),
            "date": exp.date.isoformat(),
        })
    transactions.sort(key=lambda x: x["date"], reverse=True)
    transactions = transactions[:8]

    # Goals & Budgets count
    goals_res = await db.execute(
        select(func.count(FinancialGoal.id)).where(
            and_(FinancialGoal.user_id == user.id, FinancialGoal.status == "active")
        )
    )
    active_goals_count = goals_res.scalar_one()

    budgets_res = await db.execute(
        select(func.count(Budget.id)).where(
            and_(Budget.user_id == user.id, Budget.end_date >= today)
        )
    )
    active_budgets_count = budgets_res.scalar_one()

    # Category-specific extra metrics
    user_cat = user.category.value if hasattr(user.category, "value") else str(user.category)
    category_metrics: Dict[str, Any] = {}

    if user_cat == "student":
        # Student specific: daily burn rate, allowance remaining
        days_in_month = (date(today.year + (today.month // 12), ((today.month % 12) + 1), 1) - start_of_month).days
        days_remaining = max(1, days_in_month - today.day)
        remaining_allowance = max(0.0, month_income - month_expenses)
        safe_daily_spend = round(remaining_allowance / days_remaining, 2)
        category_metrics = {
            "days_remaining_in_month": days_remaining,
            "safe_daily_budget": safe_daily_spend,
            "allowance_spent_pct": round((month_expenses / month_income * 100), 1) if month_income > 0 else 0.0,
        }
    elif user_cat == "employee":
        # Employee specific: 50/30/20 budget breakdown estimate
        category_metrics = {
            "disposable_income": net_savings,
            "recommended_savings_goal": round(month_income * 0.2, 2),
            "savings_goal_met": net_savings >= (month_income * 0.2),
        }
    elif user_cat == "businessman":
        # Businessman specific: business summary & cash flow
        biz_res = await db.execute(select(Business).where(Business.user_id == user.id))
        biz = biz_res.scalar_one_or_none()
        category_metrics = {
            "business_name": biz.business_name if biz else None,
            "available_capital": float(biz.available_capital) if biz and biz.available_capital else 0.0,
            "gross_margin_pct": round((net_savings / month_income * 100), 1) if month_income > 0 else 0.0,
            "net_cash_flow": net_savings,
        }

    return DashboardSummaryResponse(
        category=user_cat,
        currency="PKR",
        total_income_this_month=month_income,
        total_expenses_this_month=month_expenses,
        net_savings_this_month=net_savings,
        savings_rate_pct=savings_rate,
        recent_transactions=transactions,
        active_goals_count=active_goals_count,
        active_budgets_count=active_budgets_count,
        category_metrics=category_metrics,
    )
