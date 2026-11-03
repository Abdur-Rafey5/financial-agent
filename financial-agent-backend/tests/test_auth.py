"""Authentication, demo account and health endpoint tests."""

from conftest import TEST_PASSWORD, bearer, register_user


async def test_health_reports_database(client):
    response = await client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["database"] == "ok"


async def test_register_login_and_me(client):
    token = await register_user(client, email="alice@example.com")
    headers = bearer(token)

    me = await client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == "alice@example.com"
    assert me.json()["has_profile"] is False

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "alice@example.com", "password": TEST_PASSWORD},
    )
    assert login.status_code == 200
    assert login.json()["access_token"]


async def test_duplicate_registration_and_bad_password(client):
    await register_user(client, email="bob@example.com")

    duplicate = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "bob@example.com",
            "password": TEST_PASSWORD,
            "full_name": "Bob",
        },
    )
    assert duplicate.status_code == 409

    wrong = await client.post(
        "/api/v1/auth/login",
        json={"email": "bob@example.com", "password": "WrongPassword1!"},
    )
    assert wrong.status_code == 401


async def test_protected_route_requires_token(client):
    response = await client.get("/api/v1/dashboard/summary")
    assert response.status_code in (401, 403)


async def test_demo_login_creates_seeded_account(client):
    credentials = await client.get("/api/v1/auth/demo/credentials")
    assert credentials.status_code == 200
    assert credentials.json()["email"] == "demo@finagent.app"

    response = await client.post("/api/v1/auth/demo")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["user"]["has_profile"] is True

    summary = await client.get(
        "/api/v1/dashboard/summary", headers=bearer(body["access_token"])
    )
    assert summary.status_code == 200
    assert summary.json()["category"] == "student"
