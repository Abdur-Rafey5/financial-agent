"""
Dashboard aggregation API.

The whole summary is derived from :mod:`app.services.financial_context`, the
same snapshot the assistant and recommendation engine use, so every surface
shows identical numbers.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import func, select

from app.api.dependencies import CurrentUser, DbSession
from app.models.ai import AIRecommendation
from app.services.financial_context import build_financial_context

router = APIRouter()


class DashboardSummaryResponse(BaseModel):
    category: str
    currency: str
    period_start: str
    period_end: str
    total_income_this_month: float
    total_expenses_this_month: float
    net_savings_this_month: float
    savings_rate_pct: float
    previous_month_expenses: float
    expense_change_pct: float
    top_expense_categories: List[Dict[str, Any]]
    recent_transactions: List[Dict[str, Any]]
    active_goals_count: int
    active_budgets_count: int
    unread_recommendations_count: int
    category_metrics: Dict[str, Any]
    goals: List[Dict[str, Any]]
    budgets: List[Dict[str, Any]]
    trend: List[Dict[str, Any]]
    business: Optional[Dict[str, Any]] = None


@router.get("/summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(user: CurrentUser, db: DbSession):
    """Aggregate a category-aware financial snapshot for the dashboard."""
    context = await build_financial_context(db, user)

    unread = await db.scalar(
        select(func.count(AIRecommendation.id)).where(
            AIRecommendation.user_id == user.id,
            AIRecommendation.is_read.is_(False),
            AIRecommendation.is_dismissed.is_(False),
        )
    )

    goals = context["goals"]
    budgets = context["budgets"]

    return DashboardSummaryResponse(
        category=context["user"]["category"],
        currency=context["user"]["currency"],
        period_start=context["period"]["month_start"],
        period_end=context["period"]["month_end"],
        total_income_this_month=context["month"]["income"],
        total_expenses_this_month=context["month"]["expenses"],
        net_savings_this_month=context["month"]["net_savings"],
        savings_rate_pct=context["month"]["savings_rate_pct"],
        previous_month_expenses=context["month"]["previous_expenses"],
        expense_change_pct=context["month"]["expense_change_pct"],
        top_expense_categories=context["top_expense_categories"],
        recent_transactions=context["recent_transactions"],
        active_goals_count=sum(1 for goal in goals if goal["status"] == "active"),
        active_budgets_count=sum(1 for budget in budgets if budget["is_active"]),
        unread_recommendations_count=int(unread or 0),
        category_metrics=context["metrics"],
        goals=goals,
        budgets=budgets,
        trend=context["trend"],
        business=context["business"],
    )
