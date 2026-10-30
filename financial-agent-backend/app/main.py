"""
FastAPI application entry point.

Creates the app, registers middleware, exception handlers, and routes.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.exceptions import AppException


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    from app.core.database import engine, Base
    import app.models  # ensure models are loaded
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Shutdown: cleanup resources
    await engine.dispose()


def create_app() -> FastAPI:
    """Application factory."""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="AI-Powered Financial Agent — manage finances with intelligent assistance",
        docs_url="/api/docs" if settings.DEBUG else None,
        redoc_url="/api/redoc" if settings.DEBUG else None,
        lifespan=lifespan,
    )

    # ── CORS ─────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Exception Handlers ───────────────────────────────────────────
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": True,
                "message": exc.message,
                "detail": exc.detail,
            },
        )

    # ── Routes ───────────────────────────────────────────────────────
    from app.api.v1 import auth, users, income, expenses, budgets, goals
    from app.api.v1 import dashboard, reports, assistant, recommendations
    from app.api.v1 import investments, business

    app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
    app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])
    app.include_router(income.router, prefix="/api/v1/income", tags=["Income"])
    app.include_router(expenses.router, prefix="/api/v1/expenses", tags=["Expenses"])
    app.include_router(budgets.router, prefix="/api/v1/budgets", tags=["Budgets"])
    app.include_router(goals.router, prefix="/api/v1/goals", tags=["Goals"])
    app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["Dashboard"])
    app.include_router(reports.router, prefix="/api/v1/reports", tags=["Reports"])
    app.include_router(assistant.router, prefix="/api/v1/assistant", tags=["AI Assistant"])
    app.include_router(recommendations.router, prefix="/api/v1/recommendations", tags=["Recommendations"])
    app.include_router(investments.router, prefix="/api/v1/investments", tags=["Investments"])
    app.include_router(business.router, prefix="/api/v1/business", tags=["Business"])

    # ── Health Check ─────────────────────────────────────────────────
    @app.get("/api/health", tags=["Health"])
    async def health_check():
        return {"status": "healthy", "version": settings.APP_VERSION}

    return app


app = create_app()
