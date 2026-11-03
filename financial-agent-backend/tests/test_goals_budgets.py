"""Goal and budget behaviour tests, including the original create-goal 500 regression."""

from datetime import date, timedelta

from conftest import bearer, register_user


def today() -> date:
    return date.today()


async def test_goal_create_contribute_and_recompute(client):
    token = await register_user(client, email="goal@example.com")
    headers = bearer(token)

    # Regression: POST /goals used to raise MissingGreenlet while serialising
    # goal.contributions on a freshly created instance.
    created = await client.post(
        "/api/v1/goals",
        headers=headers,
        json={
            "title": "New laptop",
            "target_amount": 100000,
            "currency": "PKR",
            "target_date": (today() + timedelta(days=90)).isoformat(),
        },
    )
    assert created.status_code == 201, created.text
    goal = created.json()
    assert goal["current_amount"] == 0.0
    assert goal["contributions"] == []
    goal_id = goal["id"]

    first = await client.post(
        f"/api/v1/goals/{goal_id}/contribute",
        headers=headers,
        json={"amount": 40000, "date": today().isoformat()},
    )
    assert first.status_code == 200, first.text
    assert first.json()["current_amount"] == 40000.0
    assert first.json()["percentage_completed"] == 40.0
    assert first.json()["status"] == "active"

    second = await client.post(
        f"/api/v1/goals/{goal_id}/contribute",
        headers=headers,
        json={"amount": 60000, "date": today().isoformat()},
    )
    assert second.json()["status"] == "completed"
    assert second.json()["percentage_completed"] == 100.0
    contribution_id = next(
        item["id"]
        for item in second.json()["contributions"]
        if item["amount"] == 60000.0
    )

    removed = await client.delete(
        f"/api/v1/goals/{goal_id}/contributions/{contribution_id}", headers=headers
    )
    assert removed.status_code == 200
    assert removed.json()["current_amount"] == 40000.0
    assert removed.json()["status"] == "active"


async def test_goal_validation_and_delete(client):
    token = await register_user(client, email="goal-delete@example.com")
    headers = bearer(token)

    invalid = await client.post(
        "/api/v1/goals",
        headers=headers,
        json={"title": "Zero", "target_amount": 0},
    )
    assert invalid.status_code == 422

    created = await client.post(
        "/api/v1/goals",
        headers=headers,
        json={"title": "Emergency fund", "target_amount": 50000},
    )
    goal_id = created.json()["id"]
    deleted = await client.delete(f"/api/v1/goals/{goal_id}", headers=headers)
    assert deleted.status_code == 204

    listing = await client.get("/api/v1/goals", headers=headers)
    assert listing.json() == []


async def test_budget_allocations_and_usage(client):
    token = await register_user(client, email="budget@example.com")
    headers = bearer(token)

    categories = await client.get("/api/v1/expenses/categories", headers=headers)
    food = next(item for item in categories.json() if item["name"] == "Food & Dining")

    start = today().replace(day=1)
    end = (start + timedelta(days=32)).replace(day=1) - timedelta(days=1)

    created = await client.post(
        "/api/v1/budgets",
        headers=headers,
        json={
            "name": "November budget",
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "total_limit": 50000,
            "currency": "PKR",
            "category_allocations": [
                {"category_id": food["id"], "limit_amount": 10000}
            ],
        },
    )
    assert created.status_code == 201, created.text
    budget = created.json()
    assert budget["allocations"][0]["category_name"] == "Food & Dining"
    assert budget["remaining_amount"] == 50000.0

    await client.post(
        "/api/v1/expenses",
        headers=headers,
        json={
            "amount": 2500,
            "date": today().isoformat(),
            "description": "Dinner",
            "category_id": food["id"],
        },
    )

    listing = await client.get("/api/v1/budgets", headers=headers)
    spent = listing.json()[0]
    assert spent["total_spent"] == 2500.0
    assert spent["allocations"][0]["spent_amount"] == 2500.0
    assert spent["allocations"][0]["usage_pct"] == 25.0


async def test_budget_validation(client):
    token = await register_user(client, email="budget-invalid@example.com")
    headers = bearer(token)

    reversed_dates = await client.post(
        "/api/v1/budgets",
        headers=headers,
        json={
            "name": "Bad",
            "start_date": today().isoformat(),
            "end_date": (today() - timedelta(days=1)).isoformat(),
            "total_limit": 100,
        },
    )
    assert reversed_dates.status_code == 422

    categories = await client.get("/api/v1/expenses/categories", headers=headers)
    food = next(item for item in categories.json() if item["name"] == "Food & Dining")

    duplicate = await client.post(
        "/api/v1/budgets",
        headers=headers,
        json={
            "name": "Duplicate",
            "start_date": today().replace(day=1).isoformat(),
            "end_date": today().isoformat(),
            "total_limit": 100,
            "category_allocations": [
                {"category_id": food["id"], "limit_amount": 50},
                {"category_id": food["id"], "limit_amount": 50},
            ],
        },
    )
    assert duplicate.status_code == 422
