"""
Deterministic proactive recommendation engine.

Every recommendation is produced by an explicit, auditable rule that runs over
the same financial snapshot the dashboard and assistant use. Gemini is *not*
involved here: numbers, thresholds and reasoning strings are computed in Python
so the user can always trace why a recommendation appeared.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai import (
    AgentEvent,
    AIRecommendation,
    RecommendationPriority,
    RecommendationType,
)
from app.models.user import User
from app.services.financial_context import build_financial_context

logger = logging.getLogger(__name__)

DEDUPE_WINDOW_DAYS = 7
DISMISSAL_WINDOW_DAYS = 30


def _as_utc(value: datetime) -> datetime:
    """SQLite returns naive datetimes; compare everything in UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@dataclass
class RecommendationDraft:
    """A recommendation produced by a rule, before persistence."""

    type: RecommendationType
    title: str
    content: str
    reasoning: str
    priority: RecommendationPriority
    source_data: dict[str, Any] = field(default_factory=dict)


def _money(value: float, currency: str) -> str:
    return f"{value:,.0f} {currency}"


def _active_goals(context: dict[str, Any]) -> list[dict[str, Any]]:
    return [goal for goal in context["goals"] if goal["status"] == "active"]


def build_drafts(context: dict[str, Any]) -> list[RecommendationDraft]:
    """Apply every rule to the snapshot and return the triggered drafts."""
    currency = context["user"]["currency"]
    month = context["month"]
    track = context["user"]["category"]
    metrics = context["metrics"]
    budgets = context["budgets"]
    drafts: list[RecommendationDraft] = []

    income = month["income"]
    expenses = month["expenses"]
    net = month["net_savings"]
    savings_rate = month["savings_rate_pct"]
    previous_expenses = month["previous_expenses"]

    # ── Budget rules ─────────────────────────────────────────────────
    overspent = [budget for budget in budgets if budget["usage_pct"] >= 100]
    for budget in overspent[:2]:
        over = budget["spent"] - budget["limit"]
        drafts.append(
            RecommendationDraft(
                type=RecommendationType.BUDGET,
                title=f"Budget exceeded: {budget['name']}",
                content=(
                    f"You have spent {_money(budget['spent'], currency)} against a "
                    f"{_money(budget['limit'], currency)} limit — {_money(over, currency)} over."
                ),
                reasoning=(
                    "Computed as recorded expenses between "
                    f"{budget['start_date']} and {budget['end_date']} divided by the budget limit "
                    f"({budget['usage_pct']}% used)."
                ),
                priority=RecommendationPriority.HIGH,
                source_data={
                    "budget_id": budget["id"],
                    "spent": budget["spent"],
                    "limit": budget["limit"],
                    "usage_pct": budget["usage_pct"],
                },
            )
        )

    near_limit = [b for b in budgets if 80 <= b["usage_pct"] < 100 and b not in overspent]
    for budget in near_limit[:2]:
        remaining = budget["limit"] - budget["spent"]
        drafts.append(
            RecommendationDraft(
                type=RecommendationType.BUDGET,
                title=f"Budget almost used: {budget['name']}",
                content=(
                    f"{budget['usage_pct']}% of this budget is used. Only "
                    f"{_money(remaining, currency)} is left for the rest of the period."
                ),
                reasoning=(
                    "The budget is above the 80% early-warning threshold "
                    f"({budget['spent']} of {budget['limit']} recorded)."
                ),
                priority=RecommendationPriority.MEDIUM,
                source_data={
                    "budget_id": budget["id"],
                    "remaining": remaining,
                    "usage_pct": budget["usage_pct"],
                },
            )
        )

    if not budgets and expenses > 0:
        drafts.append(
            RecommendationDraft(
                type=RecommendationType.BUDGET,
                title="Set a monthly budget",
                content=(
                    f"You recorded {_money(expenses, currency)} of spending this month but have "
                    "no budget. A budget makes overspending visible before it happens."
                ),
                reasoning=(
                    "Rule fired because at least one expense exists in the current month and the "
                    "user has zero budget records."
                ),
                priority=RecommendationPriority.MEDIUM,
                source_data={"expenses_this_month": expenses},
            )
        )

    # ── Cash-flow and savings rules ──────────────────────────────────
    if income > 0 and net < 0:
        drafts.append(
            RecommendationDraft(
                type=RecommendationType.SAVINGS,
                title="Spending is higher than income this month",
                content=(
                    f"Recorded income is {_money(income, currency)} and expenses are "
                    f"{_money(expenses, currency)}, leaving a deficit of "
                    f"{_money(abs(net), currency)}."
                ),
                reasoning=(
                    "Computed directly as income minus expenses for the current month; the "
                    "result is negative."
                ),
                priority=RecommendationPriority.HIGH,
                source_data={"income": income, "expenses": expenses, "net": net},
            )
        )
    elif income > 0:
        targets = {"student": 10.0, "employee": 20.0, "businessman": 15.0}
        target = targets.get(track, 15.0)
        if savings_rate < target:
            gap = round(income * target / 100 - net, 2)
            drafts.append(
                RecommendationDraft(
                    type=RecommendationType.SAVINGS,
                    title=f"Savings rate below your {target:.0f}% target",
                    content=(
                        f"You kept {savings_rate}% of income this month "
                        f"({_money(net, currency)} of {_money(income, currency)}). "
                        f"Reaching {target:.0f}% would mean saving {_money(gap, currency)} more."
                    ),
                    reasoning=(
                        f"Savings rate = net savings / income = {net} / {income} = "
                        f"{savings_rate}%. The {track} track guide is {target:.0f}% "
                        "and is a planning benchmark, not a personalised guarantee."
                    ),
                    priority=RecommendationPriority.MEDIUM,
                    source_data={
                        "savings_rate_pct": savings_rate,
                        "target_pct": target,
                        "gap": gap,
                    },
                )
            )

    # ── Spending pattern rules ───────────────────────────────────────
    change = month["expense_change_pct"]
    if previous_expenses > 0 and change >= 25 and expenses > 0:
        drafts.append(
            RecommendationDraft(
                type=RecommendationType.SPENDING,
                title=f"Spending up {change:.0f}% vs last month",
                content=(
                    f"This month's expenses are {_money(expenses, currency)} compared with "
                    f"{_money(previous_expenses, currency)} last month."
                ),
                reasoning=(
                    "Expense change = (this month - last month) / last month. The rule fires "
                    "at a 25% increase or more."
                ),
                priority=RecommendationPriority.HIGH if change >= 50 else RecommendationPriority.MEDIUM,
                source_data={
                    "expenses": expenses,
                    "previous_expenses": previous_expenses,
                    "change_pct": change,
                },
            )
        )

    top_categories = context["top_expense_categories"]
    if top_categories and expenses > 0:
        top = top_categories[0]
        if top["percentage"] >= 40:
            drafts.append(
                RecommendationDraft(
                    type=RecommendationType.SPENDING,
                    title=f"{top['name']} dominates your spending",
                    content=(
                        f"{top['name']} accounts for {top['percentage']}% of this month's "
                        f"expenses ({_money(top['amount'], currency)})."
                    ),
                    reasoning=(
                        "Category share is computed by grouping recorded expenses by category "
                        "for the current month. The rule fires at 40% or more."
                    ),
                    priority=RecommendationPriority.MEDIUM,
                    source_data={"category": top["name"], "percentage": top["percentage"]},
                )
            )

    if track == "student":
        used = metrics.get("allowance_used_pct", 0.0)
        if used >= 85 and expenses > 0:
            drafts.append(
                RecommendationDraft(
                    type=RecommendationType.SPENDING,
                    title="Most of this month's money is already spent",
                    content=(
                        f"You have used {used}% of the money recorded this month. "
                        f"About {_money(max(0.0, net), currency)} is left for the remaining "
                        f"{metrics.get('days_left_in_month', 0)} days."
                    ),
                    reasoning=(
                        "Allowance usage = expenses / income for the current month. "
                        "The remaining daily amount is the leftover divided by days left."
                    ),
                    priority=RecommendationPriority.HIGH if used >= 100 else RecommendationPriority.MEDIUM,
                    source_data=metrics,
                )
            )

    if track == "businessman":
        if net < 0:
            drafts.append(
                RecommendationDraft(
                    type=RecommendationType.BUSINESS,
                    title="Business cash flow is negative this month",
                    content=(
                        f"Business income recorded is {_money(income, currency)} while expenses "
                        f"are {_money(expenses, currency)} — a net outflow of "
                        f"{_money(abs(net), currency)}."
                    ),
                    reasoning=(
                        "Net cash flow = income - expenses for the current month. "
                        "Only recorded transactions are used."
                    ),
                    priority=RecommendationPriority.HIGH,
                    source_data={"net_cash_flow": net},
                )
            )
        has_business_revenue = any(
            row["type"] == "income" and row.get("category") == "business_revenue"
            for row in context["recent_transactions"]
        )
        if not has_business_revenue:
            drafts.append(
                RecommendationDraft(
                    type=RecommendationType.BUSINESS,
                    title="No business revenue recorded recently",
                    content=(
                        "There are no recent income entries tagged as business revenue. "
                        "Record revenue so profitability metrics stay accurate."
                    ),
                    reasoning=(
                        "The rule checks the recent transaction feed for an income entry whose "
                        "type is business_revenue and found none."
                    ),
                    priority=RecommendationPriority.LOW,
                    source_data={"recent_transactions_checked": len(context["recent_transactions"])},
                )
            )

    # ── Goal rules ───────────────────────────────────────────────────
    goals = _active_goals(context)
    for goal in goals[:3]:
        if goal["progress_pct"] >= 100 or not goal["target_date"]:
            continue
        days_left = goal["days_left"] or 0
        if days_left <= 0:
            drafts.append(
                RecommendationDraft(
                    type=RecommendationType.GOAL,
                    title=f"Goal deadline passed: {goal['title']}",
                    content=(
                        f"{goal['title']} is {goal['progress_pct']}% complete and its target date "
                        f"({goal['target_date']}) has passed."
                    ),
                    reasoning="The target date of an active goal is earlier than today.",
                    priority=RecommendationPriority.MEDIUM,
                    source_data={"goal_id": goal["id"], "progress_pct": goal["progress_pct"]},
                )
            )
            continue
        months_left = max(1.0, days_left / 30.0)
        required = round((goal["target"] - goal["current"]) / months_left, 2)
        if required > max(net, 0.0):
            drafts.append(
                RecommendationDraft(
                    type=RecommendationType.GOAL,
                    title=f"Goal needs more each month: {goal['title']}",
                    content=(
                        f"You need about {_money(required, currency)} per month to reach "
                        f"{_money(goal['target'], currency)} in {days_left} days. "
                        f"This month's actual saving was {_money(net, currency)}."
                    ),
                    reasoning=(
                        "Required monthly amount = (target - current) / months remaining, "
                        "using 30 days per month as an approximation. It exceeds the recorded "
                        "net saving for this month."
                    ),
                    priority=RecommendationPriority.MEDIUM,
                    source_data={
                        "goal_id": goal["id"],
                        "required_monthly": required,
                        "current_monthly": net,
                    },
                )
            )

    if not goals:
        drafts.append(
            RecommendationDraft(
                type=RecommendationType.GOAL,
                title="Create your first financial goal",
                content=(
                    "You have no active savings goal. Goals turn an abstract surplus into a "
                    "concrete target with a deadline."
                ),
                reasoning="Rule fired because the user has zero active goals.",
                priority=RecommendationPriority.LOW,
                source_data={"goals": len(context["goals"])},
            )
        )

    # ── Positive reinforcement / surplus rule ────────────────────────
    if income > 0 and savings_rate >= 25 and net > 0 and goals:
        drafts.append(
            RecommendationDraft(
                type=RecommendationType.INVESTMENT,
                title="Surplus available to put to work",
                content=(
                    f"You saved {_money(net, currency)} this month ({savings_rate}% of income). "
                    "Consider directing part of this surplus toward your goals or a diversified "
                    "low-cost investment, after keeping an emergency buffer."
                ),
                reasoning=(
                    "Savings rate is at or above 25% and the user has at least one active goal. "
                    "The suggested direction is generic education, not personalised investment advice."
                ),
                priority=RecommendationPriority.LOW,
                source_data={"net": net, "savings_rate_pct": savings_rate},
            )
        )

    if expenses == 0 and income > 0:
        drafts.append(
            RecommendationDraft(
                type=RecommendationType.GENERAL,
                title="No expenses recorded this month",
                content=(
                    "Income is recorded but no expenses yet. If you have already spent money, "
                    "record it so your dashboard and advice stay accurate."
                ),
                reasoning="Rule fired because the current month has income but zero expenses.",
                priority=RecommendationPriority.LOW,
                source_data={"income": income, "expenses": expenses},
            )
        )

    return drafts


async def generate_recommendations(
    db: AsyncSession,
    user: User,
    *,
    force: bool = False,
) -> list[AIRecommendation]:
    """
    Evaluate rules and persist new recommendations.

    Duplicate titles from the last :data:`DEDUPE_WINDOW_DAYS` days are skipped,
    and recommendations dismissed within :data:`DISMISSAL_WINDOW_DAYS` days are
    not resurrected. Agent events for this user are marked processed.
    """
    context = await build_financial_context(db, user)
    drafts = build_drafts(context)

    now = datetime.now(timezone.utc)
    recent_cutoff = now - timedelta(days=DEDUPE_WINDOW_DAYS)
    dismissed_cutoff = now - timedelta(days=DISMISSAL_WINDOW_DAYS)

    rows = await db.execute(
        select(AIRecommendation.title, AIRecommendation.is_dismissed, AIRecommendation.created_at)
        .where(
            AIRecommendation.user_id == user.id,
            AIRecommendation.created_at >= dismissed_cutoff,
        )
    )
    existing: dict[str, list[Any]] = {}
    for title, is_dismissed, created_at in rows.all():
        existing.setdefault(title, []).append((is_dismissed, _as_utc(created_at)))

    created: list[AIRecommendation] = []
    for draft in drafts:
        prior = existing.get(draft.title, [])
        duplicate = any(
            (not dismissed and created_at >= recent_cutoff) or dismissed
            for dismissed, created_at in prior
        )
        if duplicate:
            continue

        record = AIRecommendation(
            user_id=user.id,
            type=draft.type,
            title=draft.title,
            content=draft.content,
            reasoning=draft.reasoning,
            priority=draft.priority,
            is_read=False,
            is_dismissed=False,
            source_data=draft.source_data,
        )
        db.add(record)
        created.append(record)

    await db.execute(
        update(AgentEvent)
        .where(AgentEvent.user_id == user.id, AgentEvent.processed.is_(False))
        .values(processed=True)
    )
    await db.commit()

    for record in created:
        await db.refresh(record)

    logger.info("Generated %s new recommendations for %s", len(created), user.email)
    return created
