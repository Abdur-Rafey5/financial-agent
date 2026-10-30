"""
Financial reports and analytics API — monthly trends, category distributions, income vs expense.
"""

from datetime import date
from typing import List, Dict, Any

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import select, func, and_

from app.api.dependencies import CurrentUser, DbSession
from app.models.income import IncomeRecord
from app.models.expense import ExpenseRecord, ExpenseCategory

router = APIRouter()


class CategoryBreakdownItem(BaseModel):
    category_id: str
    category_name: str
    amount: float
    percentage: float
    color: str


class MonthlyTrendItem(BaseModel):
    month: str
    income: float
    expense: float
    net_savings: float


class ReportAnalyticsResponse(BaseModel):
    total_income: float
    total_expenses: float
    net_savings: float
    savings_rate_pct: float
    category_breakdown: List[CategoryBreakdownItem]
    monthly_trend: List[MonthlyTrendItem]


@router.get("/analytics", response_model=ReportAnalyticsResponse)
async def get_financial_reports(
    user: CurrentUser,
    db: DbSession,
    start_date: date = Query(default=date(date.today().year, 1, 1)),
    end_date: date = Query(default=date.today()),
):
    """Generate financial breakdowns and trend analysis over a specified date range."""
    # Totals
    inc_tot = await db.execute(
        select(func.coalesce(func.sum(IncomeRecord.amount), 0)).where(
            and_(
                IncomeRecord.user_id == user.id,
                IncomeRecord.date >= start_date,
                IncomeRecord.date <= end_date,
            )
        )
    )
    total_inc = float(inc_tot.scalar_one())

    exp_tot = await db.execute(
        select(func.coalesce(func.sum(ExpenseRecord.amount), 0)).where(
            and_(
                ExpenseRecord.user_id == user.id,
                ExpenseRecord.date >= start_date,
                ExpenseRecord.date <= end_date,
            )
        )
    )
    total_exp = float(exp_tot.scalar_one())

    net_savings = total_inc - total_exp
    savings_rate = round((net_savings / total_inc * 100), 1) if total_inc > 0 else 0.0

    # Category breakdown for expenses
    cat_query = (
        select(
            ExpenseRecord.category_id,
            ExpenseCategory.name,
            ExpenseCategory.color,
            func.coalesce(func.sum(ExpenseRecord.amount), 0).label("cat_sum"),
        )
        .outerjoin(ExpenseCategory, ExpenseRecord.category_id == ExpenseCategory.id)
        .where(
            and_(
                ExpenseRecord.user_id == user.id,
                ExpenseRecord.date >= start_date,
                ExpenseRecord.date <= end_date,
            )
        )
        .group_by(ExpenseRecord.category_id, ExpenseCategory.name, ExpenseCategory.color)
        .order_by(func.sum(ExpenseRecord.amount).desc())
    )
    cat_res = await db.execute(cat_query)

    breakdown: List[CategoryBreakdownItem] = []
    default_colors = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899", "#6366f1"]
    for idx, (cid, cname, ccolor, csum) in enumerate(cat_res.all()):
        c_amt = float(csum)
        pct = round((c_amt / total_exp * 100), 1) if total_exp > 0 else 0.0
        breakdown.append(
            CategoryBreakdownItem(
                category_id=str(cid) if cid else "uncategorized",
                category_name=cname or "Uncategorized",
                amount=c_amt,
                percentage=pct,
                color=ccolor or default_colors[idx % len(default_colors)],
            )
        )

    # Monthly trends (current simplified query)
    monthly_trend = [
        MonthlyTrendItem(
            month=end_date.strftime("%b %Y"),
            income=total_inc,
            expense=total_exp,
            net_savings=net_savings,
        )
    ]

    return ReportAnalyticsResponse(
        total_income=total_inc,
        total_expenses=total_exp,
        net_savings=net_savings,
        savings_rate_pct=savings_rate,
        category_breakdown=breakdown,
        monthly_trend=monthly_trend,
    )
