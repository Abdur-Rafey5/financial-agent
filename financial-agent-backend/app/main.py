"""
FastAPI application entry point.

Creates the app, registers middleware, exception handlers and routes, and
seeds the system category catalogue on startup.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import settings
from app.core.exceptions import AppException
from app.services import market_data

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create tables and seed reference data before serving requests."""
    from app.core.database import Base, async_session_factory, engine
    from app.core.seed import seed_all
    import app.models  # noqa: F401 — register ORM models

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        try:
            await seed_all(session)
        except Exception:  # pragma: no cover - startup should not hard-fail on seed
            await session.rollback()
            logger.exception("Database seeding failed")

    yield

    await engine.dispose()


def create_app() -> FastAPI:
    """Application factory."""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="AI-Powered Financial Agent — manage finances with intelligent assistance",
        docs_url="/api/docs" if settings.DEBUG else None,
        redoc_url="/api/redoc" if settings.DEBUG else None,
        openapi_url="/api/openapi.json" if settings.DEBUG else None,
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

    # ── Exception handlers ───────────────────────────────────────────
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": True, "message": exc.message, "detail": exc.detail},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ):
        errors = []
        for error in exc.errors():
            location = ".".join(str(part) for part in error.get("loc", [])[1:])
            errors.append({"field": location or "body", "message": error.get("msg")})
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": True,
                "message": "Request validation failed",
                "detail": errors,
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        detail = str(exc) if settings.DEBUG else "Internal server error"
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": True, "message": "Internal server error", "detail": detail},
        )

    # ── Routes ───────────────────────────────────────────────────────
    from app.api.v1 import (
        assistant,
        auth,
        budgets,
        business,
        dashboard,
        expenses,
        goals,
        income,
        investments,
        recommendations,
        reports,
        users,
    )

    app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
    app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])
    app.include_router(income.router, prefix="/api/v1/income", tags=["Income"])
    app.include_router(expenses.router, prefix="/api/v1/expenses", tags=["Expenses"])
    app.include_router(budgets.router, prefix="/api/v1/budgets", tags=["Budgets"])
    app.include_router(goals.router, prefix="/api/v1/goals", tags=["Goals"])
    app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["Dashboard"])
    app.include_router(reports.router, prefix="/api/v1/reports", tags=["Reports"])
    app.include_router(assistant.router, prefix="/api/v1/assistant", tags=["AI Assistant"])
    app.include_router(
        recommendations.router,
        prefix="/api/v1/recommendations",
        tags=["Recommendations"],
    )
    app.include_router(
        investments.router, prefix="/api/v1/investments", tags=["Investments"]
    )
    app.include_router(business.router, prefix="/api/v1/business", tags=["Business"])

    # ── Meta routes ──────────────────────────────────────────────────
    @app.get("/", tags=["Meta"])
    async def root():
        return {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "docs": "/api/docs" if settings.DEBUG else None,
            "health": "/api/health",
            "api": "/api/v1",
        }

    async def _health():
        from app.core.database import engine

        database_ok = True
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        except Exception:  # pragma: no cover - depends on deployment
            database_ok = False

        return JSONResponse(
            status_code=status.HTTP_200_OK
            if database_ok
            else status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "healthy" if database_ok else "degraded",
                "version": settings.APP_VERSION,
                "database": "ok" if database_ok else "unreachable",
                "ai_configured": bool(settings.GEMINI_API_KEY.strip()),
                "market_data_configured": market_data.active_provider() != "none",
                "market_data_provider": market_data.active_provider(),
            },
        )

    app.add_api_route("/health", _health, tags=["Meta"])
    app.add_api_route("/api/health", _health, tags=["Meta"])

    return app


app = create_app()
