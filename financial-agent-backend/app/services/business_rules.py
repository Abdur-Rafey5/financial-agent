"""
Deterministic business scenario modelling.

These functions contain no randomness and no language-model involvement: the
same assumptions always produce the same projection, which makes the numbers
auditable and unit-testable.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def _as_number(value: Any, label: str, *, allow_zero: bool = True) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"assumptions.{label} must be a number")
    if number < 0 or (not allow_zero and number == 0):
        requirement = "zero or greater" if allow_zero else "positive"
        raise ValueError(f"assumptions.{label} must be {requirement}")
    return number


def simulate_scenario(assumptions: Dict[str, Any] | None) -> Dict[str, Any]:
    """
    Project a what-if scenario month by month.

    Inputs (all optional except the initial cost):
      initial_cost              one-off upfront investment
      expected_monthly_return   revenue added per month
      monthly_operating_cost    recurring cost added per month
      horizon_months            projection length (default 12, capped at 120)
      monthly_growth_pct        month-over-month growth of the return (default 0)
    """
    assumptions = assumptions or {}
    initial_cost = _as_number(assumptions.get("initial_cost", 0), "initial_cost")
    expected_return = _as_number(
        assumptions.get("expected_monthly_return", 0), "expected_monthly_return"
    )
    operating_cost = _as_number(
        assumptions.get("monthly_operating_cost", 0), "monthly_operating_cost"
    )
    growth = _as_number(
        assumptions.get("monthly_growth_pct", 0), "monthly_growth_pct"
    )
    horizon = int(
        _as_number(assumptions.get("horizon_months", 12), "horizon_months")
    )
    horizon = max(1, min(horizon, 120))

    monthly: List[Dict[str, Any]] = []
    cumulative = -initial_cost
    break_even_month: Optional[int] = None
    revenue_total = 0.0
    cost_total = initial_cost

    for month in range(1, horizon + 1):
        gross = expected_return * ((1 + growth / 100.0) ** (month - 1))
        net = gross - operating_cost
        cumulative += net
        revenue_total += gross
        cost_total += operating_cost
        if break_even_month is None and cumulative >= 0:
            break_even_month = month
        monthly.append(
            {
                "month": month,
                "gross_return": round(gross, 2),
                "operating_cost": round(operating_cost, 2),
                "net": round(net, 2),
                "cumulative": round(cumulative, 2),
            }
        )

    net_profit = round(cumulative, 2)
    roi = round(net_profit / initial_cost * 100, 2) if initial_cost > 0 else None

    return {
        "initial_cost": round(initial_cost, 2),
        "horizon_months": horizon,
        "monthly_growth_pct": growth,
        "projected_revenue": round(revenue_total, 2),
        "projected_costs": round(cost_total, 2),
        "projected_net_profit": net_profit,
        "projected_roi_pct": roi,
        "break_even_month": break_even_month,
        "monthly_projection": monthly,
    }


def scenario_narrative(title: str, results: Dict[str, Any]) -> str:
    """Deterministic explanation of what the projection does and does not mean."""
    roi = results["projected_roi_pct"]
    break_even = results["break_even_month"]
    horizon = results["horizon_months"]

    parts = [
        f"'{title}' modelled over {horizon} months using only the assumptions you entered.",
        f"Projected net profit is {results['projected_net_profit']:,.2f}.",
    ]
    if roi is None:
        parts.append(
            "No upfront cost was entered, so ROI is not defined; the net profit "
            "figure is still the sum of monthly net returns."
        )
    else:
        parts.append(f"Projected return on the upfront cost is {roi:.2f}%.")
    if break_even is None:
        parts.append(
            "The cumulative result does not break even within the horizon, so the "
            "scenario should be reconsidered or extended."
        )
    else:
        parts.append(f"Cumulative cash turns positive in month {break_even}.")
    parts.append(
        "These are projections derived from your inputs, not guarantees or market data."
    )
    return " ".join(parts)
