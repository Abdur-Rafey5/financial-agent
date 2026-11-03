"""Dashboard, report and recommendation API tests."""

import calendar
from datetime import date

from conftest import bearer, register_user


def month_bounds() -> tuple[str, str]:
    today = date.today()
    start = today.replace(day=1)
    last_day = calendar.monthrange(start.year, start.month)[1]
    end = start.replace(day=last_day)
    return start.isoformat(), end.isoformat()


async def seed_finances(client, headers) -> None:
    income = await client.post(
        "/api/v1/income",
        headers=headers,
        json={
            "amount": 100000,
            "date": date.today().isoformat(),
            "source": "Salary",
            "income_type": "salary",
        },
    )
    assert income.status_code == 201, income.text

    categories = await client.get("/api/v1/expenses/categories", headers=headers)
    food = next(item for item in categories.json() if item["name"] == "Food & Dining")
    expense = await client.post(
        "/api/v1/expenses",
        headers=headers,
        json={
            "amount": 30000,
            "date": date.today().isoformat(),
            "description": "Groceries and dining",
            "category_id": food["id"],
        },
    )
    assert expense.status_code == 201, expense.text


async def test_dashboard_summary_uses_recorded_data(client):
    token = await register_user(client, email="dash@example.com")
    headers = bearer(token)
    await seed_finances(client, headers)

    response = await client.get("/api/v1/dashboard/summary", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total_income_this_month"] == 100000.0
    assert body["total_expenses_this_month"] == 30000.0
    assert body["net_savings_this_month"] == 70000.0
    assert body["savings_rate_pct"] == 70.0
    assert body["top_expense_categories"][0]["name"] == "Food & Dining"
    assert body["top_expense_categories"][0]["percentage"] == 100.0
    assert len(body["trend"]) == 6
    assert body["unread_recommendations_count"] == 0


async def test_reports_analytics_aggregation(client):
    token = await register_user(client, email="reports@example.com")
    headers = bearer(token)
    await seed_finances(client, headers)

    start, end = month_bounds()
    response = await client.get(
        "/api/v1/reports/analytics",
        headers=headers,
        params={"start_date": start, "end_date": end},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total_income"] == 100000.0
    assert body["total_expenses"] == 30000.0
    assert body["net_savings"] == 70000.0
    assert body["savings_rate_pct"] == 70.0
    assert body["top_expense_category"] == "Food & Dining"
    assert body["category_breakdown"][0]["amount"] == 30000.0
    assert body["income_breakdown"][0]["amount"] == 100000.0
    assert len(body["monthly_trend"]) == 1
    assert body["monthly_trend"][0]["net_savings"] == 70000.0


async def test_reports_reject_inverted_range(client):
    token = await register_user(client, email="reports-invalid@example.com")
    response = await client.get(
        "/api/v1/reports/analytics",
        headers=bearer(token),
        params={"start_date": "2026-05-01", "end_date": "2026-04-01"},
    )
    assert response.status_code == 422


async def test_recommendations_are_generated_once(client):
    token = await register_user(client, email="recs@example.com")
    headers = bearer(token)
    await seed_finances(client, headers)

    first = await client.post("/api/v1/recommendations/generate", headers=headers)
    assert first.status_code == 200, first.text
    assert first.json()["created"] >= 2
    titles = {item["title"] for item in first.json()["items"]}
    assert "Set a monthly budget" in titles
    assert "Create your first financial goal" in titles

    second = await client.post("/api/v1/recommendations/generate", headers=headers)
    assert second.json()["created"] == 0

    listing = await client.get("/api/v1/recommendations", headers=headers)
    body = listing.json()
    assert body["total"] >= 2
    assert body["unread_count"] == body["total"]

    recommendation = body["items"][0]
    marked = await client.patch(
        f"/api/v1/recommendations/{recommendation['id']}/read", headers=headers
    )
    assert marked.status_code == 200
    assert marked.json()["is_read"] is True

    dismissed = await client.patch(
        f"/api/v1/recommendations/{recommendation['id']}/dismiss", headers=headers
    )
    assert dismissed.status_code == 204

    after = await client.get("/api/v1/recommendations", headers=headers)
    assert after.json()["total"] == body["total"] - 1
