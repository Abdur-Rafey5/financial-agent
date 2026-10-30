"""
Business profile and financial scenario analysis API.
"""

import uuid
from decimal import Decimal
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, and_

from app.api.dependencies import CurrentUser, DbSession
from app.models.business import Business, BusinessScenario

router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────────────────
class BusinessCreate(BaseModel):
    business_name: str = Field(min_length=1, max_length=255)
    business_type: Optional[str] = None
    industry: Optional[str] = None
    available_capital: Optional[Decimal] = Field(default=None, ge=0)
    currency: str = Field(default="PKR", max_length=3)
    description: Optional[str] = None


class BusinessUpdate(BaseModel):
    business_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    business_type: Optional[str] = None
    industry: Optional[str] = None
    available_capital: Optional[Decimal] = Field(default=None, ge=0)
    currency: Optional[str] = None
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

    model_config = {"from_attributes": True}


class ScenarioCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    scenario_type: str = Field(description="e.g. investment, expansion, hiring, equipment, marketing")
    description: Optional[str] = None
    assumptions: Dict[str, Any] = Field(default_factory=dict)


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

    model_config = {"from_attributes": True}


# ── Business Routes ──────────────────────────────────────────────────────
@router.get("/profile", response_model=Optional[BusinessResponse])
async def get_business_profile(user: CurrentUser, db: DbSession):
    """Get the current businessman's registered business profile."""
    res = await db.execute(select(Business).where(Business.user_id == user.id))
    b = res.scalar_one_or_none()
    if not b:
        return None
    return BusinessResponse(
        id=str(b.id),
        business_name=b.business_name,
        business_type=b.business_type,
        industry=b.industry,
        available_capital=float(b.available_capital) if b.available_capital is not None else None,
        currency=b.currency,
        description=b.description,
        created_at=b.created_at.isoformat(),
        updated_at=b.updated_at.isoformat(),
    )


@router.post("/profile", response_model=BusinessResponse, status_code=status.HTTP_201_CREATED)
async def create_or_update_business_profile(payload: BusinessCreate, user: CurrentUser, db: DbSession):
    """Create or update the user's business profile."""
    res = await db.execute(select(Business).where(Business.user_id == user.id))
    b = res.scalar_one_or_none()
    if b:
        b.business_name = payload.business_name
        b.business_type = payload.business_type
        b.industry = payload.industry
        b.available_capital = payload.available_capital
        b.currency = payload.currency.upper()
        b.description = payload.description
    else:
        b = Business(
            user_id=user.id,
            business_name=payload.business_name,
            business_type=payload.business_type,
            industry=payload.industry,
            available_capital=payload.available_capital,
            currency=payload.currency.upper(),
            description=payload.description,
        )
        db.add(b)

    await db.commit()
    await db.refresh(b)
    return BusinessResponse(
        id=str(b.id),
        business_name=b.business_name,
        business_type=b.business_type,
        industry=b.industry,
        available_capital=float(b.available_capital) if b.available_capital is not None else None,
        currency=b.currency,
        description=b.description,
        created_at=b.created_at.isoformat(),
        updated_at=b.updated_at.isoformat(),
    )


# ── Scenario Routes ──────────────────────────────────────────────────────
@router.get("/scenarios", response_model=List[ScenarioResponse])
async def list_scenarios(user: CurrentUser, db: DbSession):
    """List what-if scenarios created for the user's business."""
    res = await db.execute(
        select(BusinessScenario)
        .where(BusinessScenario.user_id == user.id)
        .order_by(BusinessScenario.created_at.desc())
    )
    scenarios = res.scalars().all()
    return [
        ScenarioResponse(
            id=str(s.id),
            business_id=str(s.business_id),
            title=s.title,
            scenario_type=s.scenario_type,
            description=s.description,
            assumptions=s.assumptions,
            results=s.results,
            ai_analysis=s.ai_analysis,
            created_at=s.created_at.isoformat(),
            updated_at=s.updated_at.isoformat(),
        )
        for s in scenarios
    ]


@router.post("/scenarios", response_model=ScenarioResponse, status_code=status.HTTP_201_CREATED)
async def create_scenario(payload: ScenarioCreate, user: CurrentUser, db: DbSession):
    """Create a new business what-if scenario with automated deterministic ROI calculations."""
    res = await db.execute(select(Business).where(Business.user_id == user.id))
    b = res.scalar_one_or_none()
    if not b:
        raise HTTPException(
            status_code=400,
            detail="You must create a business profile before running scenarios.",
        )

    # Deterministic simulation based on assumptions
    initial_cost = float(payload.assumptions.get("initial_cost", 0))
    expected_monthly_return = float(payload.assumptions.get("expected_monthly_return", 0))
    monthly_operating_cost = float(payload.assumptions.get("monthly_operating_cost", 0))
    horizon_months = int(payload.assumptions.get("horizon_months", 12))

    net_monthly = expected_monthly_return - monthly_operating_cost
    total_net = (net_monthly * horizon_months) - initial_cost
    roi = round((total_net / initial_cost * 100), 2) if initial_cost > 0 else 0.0
    break_even_months = (
        round(initial_cost / net_monthly, 1) if net_monthly > 0 and initial_cost > 0 else None
    )

    calc_results = {
        "initial_cost": initial_cost,
        "horizon_months": horizon_months,
        "net_monthly_profit": net_monthly,
        "projected_total_profit": total_net,
        "projected_roi_pct": roi,
        "break_even_months": break_even_months,
    }

    scenario = BusinessScenario(
        business_id=b.id,
        user_id=user.id,
        title=payload.title,
        scenario_type=payload.scenario_type,
        description=payload.description,
        assumptions=payload.assumptions,
        results=calc_results,
        ai_analysis=f"Projected {roi}% return over {horizon_months} months with break-even at {break_even_months or 'N/A'} months.",
    )
    db.add(scenario)
    await db.commit()
    await db.refresh(scenario)

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


@router.delete("/scenarios/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scenario(scenario_id: str, user: CurrentUser, db: DbSession):
    """Delete a business scenario."""
    try:
        sid = uuid.UUID(scenario_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid scenario_id")

    res = await db.execute(
        select(BusinessScenario).where(
            and_(BusinessScenario.id == sid, BusinessScenario.user_id == user.id)
        )
    )
    s = res.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Scenario not found")

    await db.delete(s)
    await db.commit()
