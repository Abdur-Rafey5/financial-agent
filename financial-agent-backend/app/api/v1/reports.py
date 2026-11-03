"""
Financial reports API — period totals, expense/income breakdowns and real
month-by-month trends.
"""

from datetime import date
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import and_, func, select

from app.api.dependencies import CurrentUser, DbSession
from app.models.expense import ExpenseCategory, ExpenseRecord
from app.models.income import IncomeRecord
from app.services.financial_context import month_bounds, shift_month

router = APIRouter()

MAX_TREND_MONTHS = 24
DEFAULT_COLORS = [
    "#6366f1",
    "#10b981",
    "#f59e0b",
    "#ef4444",
    "#8b5cf6",
    "#ec4899",
    "#06b6d4",
    "#84cc16",
    "#f97316",
    "#14b8a6",
]


class CategoryBreakdownItem(BaseModel):
    key: str
    label: str
    amount: float
    percentage: float
    color: str


class MonthlyTrendItem(BaseModel):
    month: str
    month_start: str
    income: float
    expense: float
    net_savings: float


class ReportAnalyticsResponse(BaseModel):
    start_date: str
    end_date: str
    months: int
    total_income: float
    total_expenses: float
    net_savings: float
    savings_rate_pct: float
    average_monthly_expenses: float
    top_expense_category: Optional[str] = None
    category_breakdown: List[CategoryBreakdownItem]
    income_breakdown: List[CategoryBreakdownItem]
    monthly_trend: List[MonthlyTrendItem]


def _pct(part: float, whole: float) -> float:
    if whole <= 0:
        return 0.0
    return round(part / whole * 100, 1)


@router.get("/analytics", response_model=ReportAnalyticsResponse)
async def get_financial_reports(
    user: CurrentUser,
    db: DbSession,
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
):
    """
    Financial breakdown and monthly trend for a date range.

    Defaults to the start of the current year through today. The trend is
    capped at 24 months to keep the query bounded.
    """
    today = date.today()
    end_date = end_date or today
    if start_date is None:
        start_date = date(end_date.year, 1, 1)
    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="start_date must be on or before end_date",
        )

    income_filter = and_(
        IncomeRecord.user_id == user.id,
        IncomeRecord.date >= start_date,
        IncomeRecord.date <= end_date,
    )
    expense_filter = and_(
        ExpenseRecord.user_id == user.id,
        ExpenseRecord.date >= start_date,
        ExpenseRecord.date <= end_date,
    )

    total_income = float(
        await db.scalar(
            select(func.coalesce(func.sum(IncomeRecord.amount), 0)).where(income_filter)
        )
        or 0
    )
    total_expenses = float(
        await db.scalar(
            select(func.coalesce(func.sum(ExpenseRecord.amount), 0)).where(expense_filter)
        )
        or 0
    )
    total_income = round(total_income, 2)
    total_expenses = round(total_expenses, 2)
    net_savings = round(total_income - total_expenses, 2)

    # ── Expense breakdown by category ────────────────────────────────
    category_rows = await db.execute(
        select(
            ExpenseRecord.category_id,
            ExpenseCategory.name,
            ExpenseCategory.color,
            func.coalesce(func.sum(ExpenseRecord.amount), 0).label("total"),
        )
        .outerjoin(ExpenseCategory, ExpenseRecord.category_id == ExpenseCategory.id)
        .where(expense_filter)
        .group_by(ExpenseRecord.category_id, ExpenseCategory.name, ExpenseCategory.color)
        .order_by(func.sum(ExpenseRecord.amount).desc())
    )

    category_breakdown: List[CategoryBreakdownItem] = []
    for index, (category_id, name, color, total) in enumerate(category_rows.all()):
        amount = round(float(total or 0), 2)
        category_breakdown.append(
            CategoryBreakdownItem(
                key=str(category_id) if category_id else "uncategorized",
                label=name or "Uncategorized",
                amount=amount,
                percentage=_pct(amount, total_expenses),
                color=color or DEFAULT_COLORS[index % len(DEFAULT_COLORS)],
            )
        )

    # ── Income breakdown by type ─────────────────────────────────────
    income_rows = await db.execute(
        select(
            IncomeRecord.income_type,
            func.coalesce(func.sum(IncomeRecord.amount), 0).label("total"),
        )
        .where(income_filter)
        .group_by(IncomeRecord.income_type)
        .order_by(func.sum(IncomeRecord.amount).desc())
    )
    income_breakdown = []
    for index, (income_type, total) in enumerate(income_rows.all()):
        amount = round(float(total or 0), 2)
        label = (
            income_type.value.replace("_", " ").title()
            if hasattr(income_type, "value")
            else str(income_type)
        )
        income_breakdown.append(
            CategoryBreakdownItem(
                key=income_type.value if hasattr(income_type, "value") else str(income_type),
                label=label,
                amount=amount,
                percentage=_pct(amount, total_income),
                color=DEFAULT_COLORS[index % len(DEFAULT_COLORS)],
            )
        )

    # ── Monthly trend from real aggregation ──────────────────────────
    first_month = month_bounds(start_date)[0]
    last_month = month_bounds(end_date)[0]
    month_starts = []
    cursor = first_month
    while cursor <= last_month and len(month_starts) < MAX_TREND_MONTHS:
        month_starts.append(cursor)
        cursor = shift_month(cursor, 1)

    monthly_trend: List[MonthlyTrendItem] = []
    for month_start in month_starts:
        _, month_end = month_bounds(month_start)
        income = float(
            await db.scalar(
                select(func.coalesce(func.sum(IncomeRecord.amount), 0)).where(
                    IncomeRecord.user_id == user.id,
                    IncomeRecord.date >= month_start,
                    IncomeRecord.date <= month_end,
                )
            )
            or 0
        )
        expense = float(
            await db.scalar(
                select(func.coalesce(func.sum(ExpenseRecord.amount), 0)).where(
                    ExpenseRecord.user_id == user.id,
                    ExpenseRecord.date >= month_start,
                    ExpenseRecord.date <= month_end,
                )
            )
            or 0
        )
        monthly_trend.append(
            MonthlyTrendItem(
                month=month_start.strftime("%b %Y"),
                month_start=month_start.isoformat(),
                income=round(income, 2),
                expense=round(expense, 2),
                net_savings=round(income - expense, 2),
            )
        )

    months = max(1, len(monthly_trend))
    return ReportAnalyticsResponse(
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
        months=months,
        total_income=total_income,
        total_expenses=total_expenses,
        net_savings=net_savings,
        savings_rate_pct=_pct(net_savings, total_income),
        average_monthly_expenses=round(total_expenses / months, 2),
        top_expense_category=category_breakdown[0].label if category_breakdown else None,
        category_breakdown=category_breakdown,
        income_breakdown=income_breakdown,
        monthly_trend=monthly_trend,
    )
