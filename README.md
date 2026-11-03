# FinAgent — AI-Powered Financial Assistant

An AI-powered financial management platform built for **Students**, **Employees** and
**Businessmen**. FinAgent turns raw income and expense data into budgets, goals,
cash-flow insight and grounded, explainable guidance — while keeping all financial
arithmetic deterministic and in the backend.

The product ships as a monorepo:

| Path | Stack | Purpose |
| --- | --- | --- |
| `financial-agent-backend` | FastAPI, SQLAlchemy (async), Alembic | REST API (`/api/v1`), auth, domain logic, AI + market integrations |
| `financial-agent-frontend` | Next.js 16 (App Router), React 19, TypeScript, Tailwind v4 | Landing, auth, onboarding and dashboards |

---

## The three user tracks

1. **Students** — allowance tracking and a *safe daily spend* figure so money lasts the
   whole month, plus small savings goals.
2. **Employees** — salary planning with savings targets and category budgets that adapt
   to real spending.
3. **Businessmen** — profitability, cash-flow runway and **what-if scenarios** to model a
   decision (cost, expected return, operating cost, horizon) before committing capital.

A single grounded AI assistant serves all three tracks.

---

## Architecture

```
Next.js 16 (App Router)  ──REST / JWT──▶  FastAPI  ──SQLAlchemy (async)──▶  PostgreSQL
        │                                     │
        │                                     ├─ Google Gemini (explain facts)
        │                                     └─ Alpha Vantage (market data, cached)
```

- **Backend:** FastAPI application with async SQLAlchemy. The app factory lives in
  `app/main.py`; routers are mounted under `/api/v1/*`.
- **Database:** PostgreSQL in production/Docker, **SQLite** (`aiosqlite`) for local
  development and tests. Schema is managed with **Alembic** (`alembic/versions/`), and
  tables are also created on startup for convenience.
- **Frontend:** Next.js 16 App Router with a typed API client in `src/lib/api.ts`.

---

## Key backend features

- **JWT auth** with **Argon2id** password hashing (`argon2-cffi`) and `python-jose` tokens.
- **Income & expense CRUD** with category management and seeded system categories.
- **Budgets** with per-category allocations and usage tracking.
- **Goals** with contributions and progress tracking.
- **Reports / analytics** over configurable date ranges and month windows.
- **Grounded AI assistant** — Google Gemini generates the natural-language answer, but the
  numbers are computed deterministically first. When no API key is configured or the
  provider fails, the assistant falls back to a deterministic, grounded summary.
- **Proactive recommendations** with explicit `reasoning` explaining *why* each suggestion
  is made.
- **Business profitability** (current month + year-to-date) and **what-if scenario**
  modelling (ROI, break-even month, projected profit).
- **Market data** from an **Alpha Vantage** adapter, cached in the database with a TTL.
  Every response carries the provider name and the timestamp of the underlying data, and
  **prices are never fabricated** — when no API key is configured, quotes are reported as
  unavailable.

### Determinism principle

Financial arithmetic is performed in the backend (services such as
`app/services/financial_context.py` and `app/services/business_rules.py`). The LLM is used
**only to explain** those already-computed facts and to distinguish **facts** (drawn from
the user's data) from **estimates** (projections). The model never invents numbers.

---

## Getting started

### Prerequisites

- Python 3.11+ (the backend Docker image uses 3.12)
- Node.js 20+ and npm
- PostgreSQL 16, or Docker for the full stack

### Backend

```bash
cd financial-agent-backend
python -m venv venv
venv\Scripts\activate            # Windows
# source venv/bin/activate       # macOS / Linux
pip install -r requirements.txt

cp .env.example .env             # Windows: copy .env.example .env
# edit .env — see variables below

uvicorn app.main:app --reload
```

The API is served at `http://localhost:8000`, interactive docs at
`http://localhost:8000/api/docs` (only when `DEBUG=true`), and a health probe at
`http://localhost:8000/api/health`.

**Environment variables** (`.env.example`):

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` / `DATABASE_URL_SYNC` | Async + sync DB URLs. Default to local SQLite; set both to PostgreSQL for production. |
| `JWT_SECRET_KEY` | Secret used to sign JWT access tokens. |
| `GEMINI_API_KEY` | Google Gemini key. Leave empty for the deterministic fallback. |
| `ALPHA_VANTAGE_API_KEY` | Market data key. Leave empty to report quotes as unavailable. |
| `CORS_ORIGINS` | Comma-separated allowed origins (default `http://localhost:3000,http://localhost:8080`). |
| `SEED_DEFAULT_CATEGORIES` | Seed the system category catalogue on startup (default `true`). |
| `SEED_DEMO_DATA` | Create the demo account on startup (default `false`; Docker sets it to `true`). |

**Migrations**

```bash
alembic upgrade head
```

**Tests**

```bash
pytest
```

Test configuration lives in `pytest.ini` (`testpaths = tests`); suites cover auth,
finance, goals/budgets, dashboard/reports, business/investments and financial
calculations.

### Frontend

```bash
cd financial-agent-frontend
npm install
npm run dev
```

The UI is served at `http://localhost:3000`. Point it at the API with:

```
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

That is the default value in `src/lib/api.ts`, so no configuration is required for local
development. Other scripts: `npm run build`, `npm run start`, `npm run lint`.

### Docker Compose

A `docker-compose.yml` at the repository root starts PostgreSQL, the backend and the
frontend together:

```bash
docker compose up --build
```

- Frontend: `http://localhost:3000`
- Backend API docs: `http://localhost:8000/api/docs`
- The backend container runs `alembic upgrade head` before `uvicorn`, and seeds default
  categories plus the demo account (`SEED_DEMO_DATA=true`).

---

## Seed data

- **Default categories** are seeded automatically on startup when
  `SEED_DEFAULT_CATEGORIES=true` (income and expense categories such as *Food & Dining*,
  *Transport*, *Salary*, *Allowance*).
- **Demo account** — `demo@finagent.app` / `Demo1234!` — is created on startup when
  `SEED_DEMO_DATA=true` (enabled in Docker), and on first use of the demo login endpoint.
  It comes with a month of sample income, expenses, a budget and two goals.
  The landing and login screens expose the credentials via `GET /api/v1/auth/demo/credentials`
  and offer a one-click demo sign-in via `POST /api/v1/auth/demo`.

---

## API overview

All routes are prefixed with `/api/v1`. Requests are authenticated with a
`Bearer <token>` header.

| Group | Base path | Highlights |
| --- | --- | --- |
| Auth | `/auth` | `POST /register`, `POST /login`, `POST /demo`, `GET /demo/credentials`, `POST /logout`, `GET /me` |
| Users | `/users` | `GET /me`, `PATCH /me`, `POST /onboarding` (and `POST /me/onboarding`) |
| Dashboard | `/dashboard` | `GET /summary` |
| Income | `/income` | `GET/POST /categories`, list/create/get/update/delete records |
| Expenses | `/expenses` | `GET/POST /categories`, list/create/get/update/delete records |
| Budgets | `/budgets` | list, create, get, update, delete with category allocations |
| Goals | `/goals` | list, create, update, delete, `POST /{id}/contribute`, delete contribution |
| Reports | `/reports` | `GET /analytics` |
| Assistant | `/assistant` | `POST /chat`, `GET /conversations`, `GET /conversations/{id}`, `DELETE /conversations/{id}` |
| Recommendations | `/recommendations` | `GET /`, `POST /generate`, `PATCH /read-all`, `PATCH /{id}/read`, `PATCH /{id}/dismiss` |
| Investments | `/investments` | `GET /status`, `GET /quotes/{symbol}`, `GET /watchlist`, `GET /search` |
| Business | `/business` | `GET/POST/PATCH /profile`, `GET /summary`, `GET /cash-flow`, scenarios CRUD |

Meta routes: `GET /` (service info) and `GET /api/health` (health probe).

---

## Repository layout

```
financial-agent/
├── docker-compose.yml
├── financial-agent-backend/
│   ├── alembic/            # migrations
│   ├── app/
│   │   ├── api/v1/         # route modules
│   │   ├── core/           # config, database, security, seed
│   │   ├── models/         # SQLAlchemy models
│   │   ├── services/       # financial context, AI, market data, rules
│   │   └── main.py         # application factory
│   ├── tests/
│   ├── .env.example
│   ├── alembic.ini
│   └── requirements.txt
└── financial-agent-frontend/
    └── src/
        ├── app/            # landing, login, register, onboarding, dashboard
        ├── components/     # UI primitives and shell
        └── lib/            # typed API client, types, formatting
```
