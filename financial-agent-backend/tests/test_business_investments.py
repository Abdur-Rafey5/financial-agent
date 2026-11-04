"""Business profitability, scenarios, investments and assistant tests."""

from datetime import date

from conftest import bearer, register_user

from app.core.config import settings
from app.services.business_rules import simulate_scenario


def today() -> str:
    return date.today().isoformat()


async def test_investments_are_honest_when_unconfigured(client, monkeypatch):
    monkeypatch.setattr(settings, "ALPHA_VANTAGE_API_KEY", "")
    # Hermetic: the developer .env may enable the keyless Yahoo fallback,
    # but this test must never touch the network.
    monkeypatch.setattr(settings, "MARKET_KEYLESS_FALLBACK", False)
    token = await register_user(client, email="invest@example.com")
    headers = bearer(token)

    status = await client.get("/api/v1/investments/status", headers=headers)
    assert status.status_code == 200
    assert status.json()["configured"] is False

    quote = await client.get("/api/v1/investments/quotes/AAPL", headers=headers)
    assert quote.status_code == 200
    assert quote.json()["available"] is False
    assert "not configured" in quote.json()["reason"]

    watchlist = await client.get("/api/v1/investments/watchlist", headers=headers)
    assert watchlist.status_code == 200
    assert watchlist.json()["configured"] is False
    assert all(item["available"] is False for item in watchlist.json()["items"])
    assert all(item["quote"] is None for item in watchlist.json()["items"])

    search = await client.get(
        "/api/v1/investments/search", headers=headers, params={"q": "apple"}
    )
    assert search.json()["available"] is False
    assert search.json()["results"] == []


async def test_status_reports_keyless_fallback_when_enabled(client, monkeypatch):
    """With the fallback flag on, status advertises Yahoo Finance (no network)."""
    monkeypatch.setattr(settings, "ALPHA_VANTAGE_API_KEY", "")
    monkeypatch.setattr(settings, "MARKET_KEYLESS_FALLBACK", True)
    token = await register_user(client, email="fallback@example.com")
    headers = bearer(token)

    status = await client.get("/api/v1/investments/status", headers=headers)
    assert status.status_code == 200
    body = status.json()
    assert body["configured"] is False
    assert body["provider"] == "Yahoo Finance"
    assert "Yahoo Finance" in body["message"]


async def test_invalid_symbol_is_rejected(client):
    token = await register_user(client, email="bad-symbol@example.com")
    response = await client.get(
        "/api/v1/investments/quotes/$BAD!", headers=bearer(token)
    )
    assert response.status_code == 422


async def test_business_profile_profitability_and_cash_flow(client):
    token = await register_user(client, email="business@example.com")
    headers = bearer(token)

    missing = await client.get("/api/v1/business/summary", headers=headers)
    assert missing.status_code == 404

    profile = await client.post(
        "/api/v1/business/profile",
        headers=headers,
        json={
            "business_name": "Rafey Traders",
            "business_type": "retail",
            "industry": "Wholesale",
            "available_capital": 200000,
            "currency": "PKR",
        },
    )
    assert profile.status_code == 201, profile.text

    income = await client.post(
        "/api/v1/income",
        headers=headers,
        json={
            "amount": 50000,
            "date": today(),
            "source": "Wholesale order",
            "income_type": "business_revenue",
        },
    )
    assert income.status_code == 201

    categories = await client.get("/api/v1/expenses/categories", headers=headers)
    business_category = next(
        item for item in categories.json() if item["name"] == "Business"
    )
    expense = await client.post(
        "/api/v1/expenses",
        headers=headers,
        json={
            "amount": 20000,
            "date": today(),
            "description": "Stock purchase",
            "category_id": business_category["id"],
        },
    )
    assert expense.status_code == 201

    summary = await client.get("/api/v1/business/summary", headers=headers)
    assert summary.status_code == 200, summary.text
    body = summary.json()
    assert body["current_month"]["revenue"] == 50000.0
    assert body["current_month"]["expenses"] == 20000.0
    assert body["current_month"]["profit"] == 30000.0
    assert body["current_month"]["margin_pct"] == 60.0
    assert body["year_to_date"]["profit"] == 30000.0
    assert len(body["monthly_trend"]) == 6

    cash = await client.get("/api/v1/business/cash-flow", headers=headers)
    assert cash.status_code == 200
    assert len(cash.json()["months"]) == 6
    assert cash.json()["months"][-1]["net_cash_flow"] == 30000.0
    assert cash.json()["runway_months"] is None

    patched = await client.patch(
        "/api/v1/business/profile",
        headers=headers,
        json={"available_capital": 250000, "description": "Updated"},
    )
    assert patched.status_code == 200
    assert patched.json()["available_capital"] == 250000.0


async def test_scenario_projection_is_deterministic_and_editable(client):
    token = await register_user(client, email="scenario@example.com")
    headers = bearer(token)

    await client.post(
        "/api/v1/business/profile",
        headers=headers,
        json={"business_name": "Scenario Co", "available_capital": 100000},
    )

    created = await client.post(
        "/api/v1/business/scenarios",
        headers=headers,
        json={
            "title": "New delivery van",
            "scenario_type": "investment",
            "assumptions": {
                "initial_cost": 100000,
                "expected_monthly_return": 25000,
                "monthly_operating_cost": 5000,
                "horizon_months": 12,
            },
        },
    )
    assert created.status_code == 201, created.text
    scenario = created.json()
    assert scenario["results"]["projected_net_profit"] == 140000.0
    assert scenario["results"]["projected_roi_pct"] == 140.0
    assert scenario["results"]["break_even_month"] == 5
    assert "not guarantees" in scenario["ai_analysis"]

    updated = await client.patch(
        f"/api/v1/business/scenarios/{scenario['id']}",
        headers=headers,
        json={
            "assumptions": {
                "initial_cost": 100000,
                "expected_monthly_return": 25000,
                "monthly_operating_cost": 5000,
                "horizon_months": 6,
            }
        },
    )
    assert updated.status_code == 200
    assert updated.json()["results"]["projected_net_profit"] == 20000.0
    assert updated.json()["results"]["projected_roi_pct"] == 20.0

    invalid = await client.post(
        "/api/v1/business/scenarios",
        headers=headers,
        json={
            "title": "Broken",
            "assumptions": {"initial_cost": "not-a-number"},
        },
    )
    assert invalid.status_code == 422

    deleted = await client.delete(
        f"/api/v1/business/scenarios/{scenario['id']}", headers=headers
    )
    assert deleted.status_code == 204


async def test_assistant_fallback_is_grounded(client, monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    token = await register_user(client, email="assistant@example.com")
    headers = bearer(token)

    await client.post(
        "/api/v1/income",
        headers=headers,
        json={
            "amount": 50000,
            "date": today(),
            "source": "Salary",
            "income_type": "salary",
        },
    )

    response = await client.post(
        "/api/v1/assistant/chat",
        headers=headers,
        json={"message": "How am I doing this month?"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ai_generated"] is False
    assert "50000.00" in body["message"]["content"]
    assert "facts from your recorded data" in body["message"]["content"]

    conversations = await client.get(
        "/api/v1/assistant/conversations", headers=headers
    )
    assert conversations.json()[0]["message_count"] == 2

    conversation_id = body["conversation_id"]
    detail = await client.get(
        f"/api/v1/assistant/conversations/{conversation_id}", headers=headers
    )
    assert [message["role"] for message in detail.json()["messages"]] == [
        "user",
        "assistant",
    ]

    deleted = await client.delete(
        f"/api/v1/assistant/conversations/{conversation_id}", headers=headers
    )
    assert deleted.status_code == 204


def test_simulate_scenario_matches_expected_math():
    result = simulate_scenario(
        {
            "initial_cost": 100000,
            "expected_monthly_return": 25000,
            "monthly_operating_cost": 5000,
            "horizon_months": 12,
        }
    )
    assert result["projected_net_profit"] == 140000.0
    assert result["projected_roi_pct"] == 140.0
    assert result["break_even_month"] == 5
    assert len(result["monthly_projection"]) == 12
