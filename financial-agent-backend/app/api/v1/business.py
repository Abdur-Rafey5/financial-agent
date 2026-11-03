"""
Business profile, profitability, cash-flow and what-if scenario API.

Every number here is computed deterministically from recorded transactions or
from the assumptions the user explicitly enters. No figure is invented and the
scenario text always states which inputs produced it.
"""

import uuid
from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, select

from app.api.dependencies import CurrentUser, DbSession
from app.models.business import Business, BusinessScenario
from app.models.expense import ExpenseCategory, ExpenseRecord
from app.models.income import IncomeRecord, IncomeType
from app.services.business_rules import scenario_narrative, simulate_scenario
from app.services.financial_context import month_bounds, shift_month

router = APIRouter()

BUSINESS_CATEGORY_NAME = "Business"
TREND_MONTHS = 6


# ── Schemas ──────────────────────────────────────────────────────────────
class BusinessCreate(BaseModel):
    business_name: str = Field(min_length=1, max_length=255)
    business_type: Optional[str] = Field(default=None, max_length=100)
    industry: Optional[str] = Field(default=None, max_length=100)
    available_capital: Optional[float] = Field(default=None, ge=0)
    currency: str = Field(default="PKR", min_length=3, max_length=3)
    description: Optional[str] = None


class BusinessUpdate(BaseModel):
    business_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    business_type: Optional[str] = Field(default=None, max_length=100)
    industry: Optional[str] = Field(default=None, max_length=100)
    available_capital: Optional[float] = Field(default=None, ge=0)
    currency: Optional[str] = Field(default=None, min_length=3, max_length=3)
    description: Optional[str] = None


class BusinessResponse(BaseModel):
    id: str
    business_name: str
    business_type: Optional[str] = None
    industry: Optional[str] = None
    available_capital: Optional[float] = None
    currency: str
    description: Optional[str] = None
    created_at: str
    updated_at: str


class PeriodMetrics(BaseModel):
    start_date: str
    end_date: str
    revenue: float
    expenses: float
    profit: float
    margin_pct: float
    transaction_count: int


class BusinessSummaryResponse(BaseModel):
    business: BusinessResponse
    currency: str
    current_month: PeriodMetrics
    year_to_date: PeriodMetrics
    available_capital: float
    monthly_trend: List[Dict[str, Any]]
    revenue_basis: str
    expense_basis: str


class MonthlyCashFlowItem(BaseModel):
    month: str
    month_start: str
    revenue: float
    expenses: float
    net_cash_flow: float


class CashFlowResponse(BaseModel):
    currency: str
    months: List[MonthlyCashFlowItem]
    average_monthly_net: float
    positive_months: int
    negative_months: int
    available_capital: float
    runway_months: Optional[float] = None
    revenue_basis: str
    expense_basis: str


class ScenarioCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    scenario_type: str = Field(
        default="investment",
        max_length=50,
        description="e.g. investment, expansion, hiring, equipment, marketing",
    )
    description: Optional[str] = None
    assumptions: Dict[str, Any] = Field(default_factory=dict)


class ScenarioUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    scenario_type: Optional[str] = Field(default=None, max_length=50)
    description: Optional[str] = None
    assumptions: Optional[Dict[str, Any]] = None


class ScenarioResponse(BaseModel):
    id: str
    business_id: str
    title: str
    scenario_type: str
    description: Optional[str] = None
    assumptions: Optional[Dict[str, Any]] = None
    results: Optional[Dict[str, Any]] = None
    ai_analysis: Optional[str] = None
    created_at: str
    updated_at: str


# ── Helpers ──────────────────────────────────────────────────────────────
def _business_response(business: Business) -> BusinessResponse:
    return BusinessResponse(
        id=str(business.id),
        business_name=business.business_name,
        business_type=business.business_type,
        industry=business.industry,
        available_capital=float(business.available_capital)
        if business.available_capital is not None
        else None,
        currency=business.currency,
        description=business.description,
        created_at=business.created_at.isoformat(),
        updated_at=business.updated_at.isoformat(),
    )


def _scenario_response(scenario: BusinessScenario) -> ScenarioResponse:
    return ScenarioResponse(
        id=str(scenario.id),
        business_id=str(scenario.business_id),
        title=scenario.title,
        scenario_type=scenario.scenario_type,
        description=scenario.description,
        assumptions=scenario.assumptions,
        results=scenario.results,
        ai_analysis=scenario.ai_analysis,
        created_at=scenario.created_at.isoformat(),
        updated_at=scenario.updated_at.isoformat(),
    )


def _pct(part: float, whole: float) -> float:
    if whole <= 0:
        return 0.0
    return round(part / whole * 100, 1)


async def _get_business(user_id: uuid.UUID, db) -> Optional[Business]:
    return await db.scalar(select(Business).where(Business.user_id == user_id))


def _business_revenue_filter(user_id: uuid.UUID, start: date, end: date):
    return and_(
        IncomeRecord.user_id == user_id,
        IncomeRecord.income_type == IncomeType.BUSINESS_REVENUE,
        IncomeRecord.date >= start,
        IncomeRecord.date <= end,
    )


def _business_expense_filter(user_id: uuid.UUID, start: date, end: date):
    return and_(
        ExpenseRecord.user_id == user_id,
        ExpenseRecord.date >= start,
        ExpenseRecord.date <= end,
        ExpenseRecord.category_id.in_(
            select(ExpenseCategory.id).where(
                ExpenseCategory.name == BUSINESS_CATEGORY_NAME,
                (
                    ExpenseCategory.is_system.is_(True)
                    | (ExpenseCategory.user_id == user_id)
                ),
            )
        ),
    )


async def _period_metrics(
    db, user_id: uuid.UUID, start: date, end: date
) -> PeriodMetrics:
    revenue = float(
        await db.scalar(
            select(func.coalesce(func.sum(IncomeRecord.amount), 0)).where(
                _business_revenue_filter(user_id, start, end)
            )
        )
        or 0
    )
    expenses = float(
        await db.scalar(
            select(func.coalesce(func.sum(ExpenseRecord.amount), 0)).where(
                _business_expense_filter(user_id, start, end)
            )
        )
        or 0
    )
    count = int(
        await db.scalar(
            select(func.count(IncomeRecord.id)).where(
                _business_revenue_filter(user_id, start, end)
            )
        )
        or 0
    ) + int(
        await db.scalar(
            select(func.count(ExpenseRecord.id)).where(
                _business_expense_filter(user_id, start, end)
            )
        )
        or 0
    )

    revenue = round(revenue, 2)
    expenses = round(expenses, 2)
    profit = round(revenue - expenses, 2)
    return PeriodMetrics(
        start_date=start.isoformat(),
        end_date=end.isoformat(),
        revenue=revenue,
        expenses=expenses,
        profit=profit,
        margin_pct=_pct(profit, revenue),
        transaction_count=count,
    )


def _resolve_scenario_inputs(
    assumptions: Dict[str, Any],
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    clean = dict(assumptions or {})
    try:
        results = simulate_scenario(clean)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    return clean, results


async def _load_scenario(
    scenario_id: str, user_id: uuid.UUID, db
) -> BusinessScenario:
    try:
        sid = uuid.UUID(scenario_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Scenario not found")

    scenario = await db.scalar(
        select(BusinessScenario).where(
            and_(BusinessScenario.id == sid, BusinessScenario.user_id == user_id)
        )
    )
    if scenario is None:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return scenario


# ── Profile Routes ───────────────────────────────────────────────────────
@router.get("/profile", response_model=Optional[BusinessResponse])
async def get_business_profile(user: CurrentUser, db: DbSession):
    """Return the businessman's profile, or ``null`` when not created yet."""
    business = await _get_business(user.id, db)
    return _business_response(business) if business else None


@router.post(
    "/profile", response_model=BusinessResponse, status_code=status.HTTP_201_CREATED
)
async def create_or_update_business_profile(
    payload: BusinessCreate, user: CurrentUser, db: DbSession
):
    """Create or replace the user's business profile."""
    business = await _get_business(user.id, db)
    if business:
        business.business_name = payload.business_name.strip()
        business.business_type = payload.business_type
        business.industry = payload.industry
        business.available_capital = payload.available_capital
        business.currency = payload.currency.upper()
        business.description = payload.description
    else:
        business = Business(
            user_id=user.id,
            business_name=payload.business_name.strip(),
            business_type=payload.business_type,
            industry=payload.industry,
            available_capital=payload.available_capital,
            currency=payload.currency.upper(),
            description=payload.description,
        )
        db.add(business)

    await db.commit()
    await db.refresh(business)
    return _business_response(business)


@router.patch("/profile", response_model=BusinessResponse)
async def update_business_profile(
    payload: BusinessUpdate, user: CurrentUser, db: DbSession
):
    """Partially update the business profile."""
    business = await _get_business(user.id, db)
    if business is None:
        raise HTTPException(status_code=404, detail="Business profile not found")

    fields = payload.model_fields_set
    if payload.business_name is not None:
        business.business_name = payload.business_name.strip()
    if "business_type" in fields:
        business.business_type = payload.business_type
    if "industry" in fields:
        business.industry = payload.industry
    if "available_capital" in fields:
        business.available_capital = payload.available_capital
    if payload.currency is not None:
        business.currency = payload.currency.upper()
    if "description" in fields:
        business.description = payload.description

    await db.commit()
    await db.refresh(business)
    return _business_response(business)


# ── Analytics Routes ─────────────────────────────────────────────────────
@router.get("/summary", response_model=BusinessSummaryResponse)
async def get_business_summary(user: CurrentUser, db: DbSession):
    """
    Profitability for the current month and year to date.

    Revenue counts income entries recorded as ``business_revenue``. Business
    expenses count entries in the ``Business`` expense category. The response
    states both bases so the figures are auditable.
    """
    business = await _get_business(user.id, db)
    if business is None:
        raise HTTPException(
            status_code=404,
            detail="Create a business profile to see profitability metrics",
        )

    today = date.today()
    month_start, month_end = month_bounds(today)
    year_start = date(today.year, 1, 1)

    current_month = await _period_metrics(db, user.id, month_start, month_end)
    year_to_date = await _period_metrics(db, user.id, year_start, today)

    trend: List[Dict[str, Any]] = []
    for offset in range(-(TREND_MONTHS - 1), 1):
        start, end = month_bounds(shift_month(month_start, offset))
        metrics = await _period_metrics(db, user.id, start, end)
        trend.append(
            {
                "month": start.strftime("%b %Y"),
                "month_start": start.isoformat(),
                "revenue": metrics.revenue,
                "expenses": metrics.expenses,
                "profit": metrics.profit,
            }
        )

    return BusinessSummaryResponse(
        business=_business_response(business),
        currency=business.currency,
        current_month=current_month,
        year_to_date=year_to_date,
        available_capital=float(business.available_capital or 0),
        monthly_trend=trend,
        revenue_basis="Income records with income_type = business_revenue",
        expense_basis="Expense records in the Business category",
    )


@router.get("/cash-flow", response_model=CashFlowResponse)
async def get_business_cash_flow(
    user: CurrentUser,
    db: DbSession,
    months: int = Query(6, ge=1, le=24),
):
    """Monthly business cash flow plus a deterministic runway estimate."""
    business = await _get_business(user.id, db)
    if business is None:
        raise HTTPException(
            status_code=404, detail="Create a business profile to see cash flow"
        )

    today = date.today()
    month_start, _ = month_bounds(today)

    series: List[MonthlyCashFlowItem] = []
    for offset in range(-(months - 1), 1):
        start, end = month_bounds(shift_month(month_start, offset))
        metrics = await _period_metrics(db, user.id, start, end)
        series.append(
            MonthlyCashFlowItem(
                month=start.strftime("%b %Y"),
                month_start=start.isoformat(),
                revenue=metrics.revenue,
                expenses=metrics.expenses,
                net_cash_flow=metrics.profit,
            )
        )

    nets = [item.net_cash_flow for item in series]
    average = round(sum(nets) / len(nets), 2) if nets else 0.0
    capital = float(business.available_capital or 0)
    runway = None
    if average < 0 and capital > 0:
        runway = round(capital / abs(average), 1)

    return CashFlowResponse(
        currency=business.currency,
        months=series,
        average_monthly_net=average,
        positive_months=sum(1 for value in nets if value > 0),
        negative_months=sum(1 for value in nets if value < 0),
        available_capital=capital,
        runway_months=runway,
        revenue_basis="Income records with income_type = business_revenue",
        expense_basis="Expense records in the Business category",
    )


# ── Scenario Routes ──────────────────────────────────────────────────────
@router.get("/scenarios", response_model=List[ScenarioResponse])
async def list_scenarios(user: CurrentUser, db: DbSession):
    """List the user's what-if scenarios, newest first."""
    result = await db.execute(
        select(BusinessScenario)
        .where(BusinessScenario.user_id == user.id)
        .order_by(BusinessScenario.created_at.desc())
    )
    return [_scenario_response(scenario) for scenario in result.scalars().all()]


@router.post(
    "/scenarios", response_model=ScenarioResponse, status_code=status.HTTP_201_CREATED
)
async def create_scenario(
    payload: ScenarioCreate, user: CurrentUser, db: DbSession
):
    """Create a scenario and compute its deterministic projection."""
    business = await _get_business(user.id, db)
    if business is None:
        raise HTTPException(
            status_code=400,
            detail="Create a business profile before running scenarios",
        )

    assumptions, results = _resolve_scenario_inputs(payload.assumptions)
    scenario = BusinessScenario(
        business_id=business.id,
        user_id=user.id,
        title=payload.title.strip(),
        description=payload.description,
        scenario_type=payload.scenario_type.strip().lower(),
        assumptions=assumptions,
        results=results,
        ai_analysis=scenario_narrative(payload.title.strip(), results),
    )
    db.add(scenario)
    await db.commit()
    await db.refresh(scenario)
    return _scenario_response(scenario)


@router.get("/scenarios/{scenario_id}", response_model=ScenarioResponse)
async def get_scenario(scenario_id: str, user: CurrentUser, db: DbSession):
    """Fetch one scenario."""
    return _scenario_response(await _load_scenario(scenario_id, user.id, db))


@router.patch("/scenarios/{scenario_id}", response_model=ScenarioResponse)
async def update_scenario(
    scenario_id: str, payload: ScenarioUpdate, user: CurrentUser, db: DbSession
):
    """Update a scenario and recompute its projection from the new assumptions."""
    scenario = await _load_scenario(scenario_id, user.id, db)

    if payload.title is not None:
        scenario.title = payload.title.strip()
    if payload.scenario_type is not None:
        scenario.scenario_type = payload.scenario_type.strip().lower()
    if "description" in payload.model_fields_set:
        scenario.description = payload.description
    if payload.assumptions is not None:
        assumptions, results = _resolve_scenario_inputs(payload.assumptions)
        scenario.assumptions = assumptions
        scenario.results = results
        scenario.ai_analysis = scenario_narrative(scenario.title, results)

    await db.commit()
    await db.refresh(scenario)
    return _scenario_response(scenario)


@router.delete("/scenarios/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scenario(scenario_id: str, user: CurrentUser, db: DbSession):
    """Delete a scenario."""
    scenario = await _load_scenario(scenario_id, user.id, db)
    await db.delete(scenario)
    await db.commit()
