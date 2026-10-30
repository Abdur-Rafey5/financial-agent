# AI-Powered Financial Agent

An autonomous web-based financial intelligence and wealth management system engineered for **Students**, **Employees**, and **Business Owners**. Powered by **FastAPI**, **PostgreSQL**, **Google Gemini 1.5**, and **Next.js 16 (App Router)**.

---

## Architecture Overview

```
                      ┌───────────────────────────────────────┐
                      │    Next.js 16 (TypeScript / Tailwind) │
                      │   - Category Onboarding               │
                      │   - Dynamic Tailored Dashboards       │
                      │   - Real-time AI Chat Interface       │
                      │   - US Stock Market Watchlist         │
                      └──────────────────┬────────────────────┘
                                         │ REST API / JWT
                                         ▼
                      ┌───────────────────────────────────────┐
                      │    FastAPI Application Backend        │
                      │   - Argon2id & JWT Auth Engine        │
                      │   - Student, Employee, Biz Handlers   │
                      │   - Gemini AI Financial Advisor       │
                      │   - Alpha Vantage Market Integration  │
                      └──────────────────┬────────────────────┘
                                         │ SQLAlchemy (Async)
                                         ▼
                      ┌───────────────────────────────────────┐
                      │       PostgreSQL 16 Database          │
                      │   - Users & Category Profiles         │
                      │   - Incomes, Expenses, & Budgets      │
                      │   - Financial Goals & Scenarios       │
                      └───────────────────────────────────────┘
```

---

## User Modes & Capabilities

1. **🎓 Student Track:**
   - Pocket money allowance budgeting.
   - Dynamic **Daily Safe Spend** calculations to prevent running out of money before month end.
   - Micro-savings goal tracking.

2. **💼 Employee Track:**
   - Monthly net salary allocations.
   - Automatic adherence checking against the **50/30/20** wealth principle (50% Needs, 30% Wants, 20% Automated Savings).
   - Category-wise expense tracking and audit-trailed goal milestones.

3. **🏢 Businessman Track:**
   - Management-level financial overview.
   - Gross margin, operating capital, and net cash flow runway analysis.
   - **What-If Scenario Simulation**: Automated ROI and break-even projection modeling for investments, hiring, and expansion.

4. **🤖 AI & Market Intelligence:**
   - **Google Gemini 1.5** domain-tailored conversational assistant providing continuous guidance.
   - **US Stock Market Watchlist** powered by Alpha Vantage real-time quotes with offline simulated fallbacks.

---

## Quickstart (Local Development)

### Prerequisites
- Python 3.11+
- Node.js 20+ & npm
- PostgreSQL or Docker

### 1. Docker Compose (Full Stack)
```bash
docker compose up --build
```
- Frontend UI: `http://localhost:3000`
- Backend API Docs: `http://localhost:8000/api/docs`

### 2. Manual Setup

#### Backend Setup:
```bash
cd financial-agent-backend
python -m venv venv
venv\Scripts\activate   # Windows
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

#### Frontend Setup:
```bash
cd financial-agent-frontend
npm install
npm run dev
```

---

## Running Test Suite
```bash
cd financial-agent-backend
python -m unittest tests/test_financial_calculations.py
```
