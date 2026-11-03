"""Onboarding, income and expense CRUD tests."""

from datetime import date

from conftest import bearer, register_user


def today() -> str:
    return date.today().isoformat()


async def onboard(client, headers, category: str = "student"):
    response = await client.post(
        "/api/v1/users/onboarding",
        headers=headers,
        json={
            "category": category,
            "currency": "PKR",
            "allowance_amount": 45000,
            "allowance_frequency": "monthly",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_onboarding_creates_profile(client):
    token = await register_user(client, email="onboard@example.com")
    headers = bearer(token)

    profile = await onboard(client, headers)
    assert profile["category"] == "student"
    assert profile["onboarding_completed"] is True
    assert profile["allowance_amount"] == 45000.0

    fetched = await client.get("/api/v1/users/me", headers=headers)
    assert fetched.json()["category"] == "student"


async def test_onboarding_rejects_invalid_category(client):
    token = await register_user(client, email="invalid-cat@example.com")
    response = await client.post(
        "/api/v1/users/onboarding",
        headers=bearer(token),
        json={"category": "astronaut", "currency": "PKR"},
    )
    assert response.status_code == 422


async def test_income_categories_and_allowance_record(client):
    token = await register_user(client, email="income@example.com")
    headers = bearer(token)

    categories = await client.get("/api/v1/income/categories", headers=headers)
    assert categories.status_code == 200
    names = {item["name"] for item in categories.json()}
    assert {"Salary", "Allowance", "Business Revenue"} <= names

    create = await client.post(
        "/api/v1/income",
        headers=headers,
        json={
            "amount": 45000,
            "currency": "PKR",
            "date": today(),
            "source": "Monthly allowance",
            "income_type": "allowance",
            "frequency": "monthly",
        },
    )
    assert create.status_code == 201, create.text
    income_id = create.json()["id"]
    assert create.json()["income_type"] == "allowance"

    listing = await client.get("/api/v1/income", headers=headers)
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["total_amount"] == 45000.0

    updated = await client.patch(
        f"/api/v1/income/{income_id}",
        headers=headers,
        json={"amount": 47000, "notes": "adjusted"},
    )
    assert updated.status_code == 200
    assert updated.json()["amount"] == 47000.0

    deleted = await client.delete(f"/api/v1/income/{income_id}", headers=headers)
    assert deleted.status_code == 204


async def test_income_rejects_invalid_type(client):
    token = await register_user(client, email="bad-income@example.com")
    response = await client.post(
        "/api/v1/income",
        headers=bearer(token),
        json={
            "amount": 100,
            "date": today(),
            "source": "Bad",
            "income_type": "not-a-type",
        },
    )
    assert response.status_code == 422


async def test_expense_categories_and_crud(client):
    token = await register_user(client, email="expense@example.com")
    headers = bearer(token)

    categories = await client.get("/api/v1/expenses/categories", headers=headers)
    assert categories.status_code == 200
    food = next(item for item in categories.json() if item["name"] == "Food & Dining")

    create = await client.post(
        "/api/v1/expenses",
        headers=headers,
        json={
            "amount": 1200,
            "currency": "PKR",
            "date": today(),
            "description": "Lunch",
            "category_id": food["id"],
        },
    )
    assert create.status_code == 201, create.text
    expense = create.json()
    assert expense["category_name"] == "Food & Dining"

    listing = await client.get("/api/v1/expenses", headers=headers)
    assert listing.json()["total"] == 1
    assert listing.json()["total_amount"] == 1200.0

    search = await client.get(
        "/api/v1/expenses", headers=headers, params={"search": "lun"}
    )
    assert search.json()["total"] == 1

    updated = await client.patch(
        f"/api/v1/expenses/{expense['id']}",
        headers=headers,
        json={"amount": 1500, "category_id": None},
    )
    assert updated.status_code == 200
    assert updated.json()["amount"] == 1500.0
    assert updated.json()["category_name"] is None

    deleted = await client.delete(
        f"/api/v1/expenses/{expense['id']}", headers=headers
    )
    assert deleted.status_code == 204


async def test_expense_rejects_foreign_category(client):
    owner_token = await register_user(client, email="cat-owner@example.com")
    owner_headers = bearer(owner_token)
    created = await client.post(
        "/api/v1/expenses/categories",
        headers=owner_headers,
        json={"name": "Private Category"},
    )
    assert created.status_code == 201
    private_id = created.json()["id"]

    other_token = await register_user(client, email="cat-other@example.com")
    response = await client.post(
        "/api/v1/expenses",
        headers=bearer(other_token),
        json={
            "amount": 10,
            "date": today(),
            "description": "Nope",
            "category_id": private_id,
        },
    )
    assert response.status_code == 422


async def test_records_are_scoped_to_owner(client):
    first_token = await register_user(client, email="owner@example.com")
    first_headers = bearer(first_token)
    created = await client.post(
        "/api/v1/expenses",
        headers=first_headers,
        json={"amount": 99, "date": today(), "description": "Private"},
    )
    expense_id = created.json()["id"]

    second_token = await register_user(client, email="intruder@example.com")
    response = await client.get(
        f"/api/v1/expenses/{expense_id}", headers=bearer(second_token)
    )
    assert response.status_code == 404
