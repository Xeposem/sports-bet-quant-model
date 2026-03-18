"""
FastAPI application entry point for the Tennis Betting API.

Startup (lifespan):
  1. Creates async SQLAlchemy engine + session factory (sqlite+aiosqlite).
  2. Loads calibrated model pipeline from MODEL_PATH env var (or default).
  3. Stores both on app.state for dependency injection and background jobs.

Configuration via environment variables:
  TENNIS_DB    - Path to SQLite database file (default: data/tennis.db)
  MODEL_PATH   - Path to joblib model file (default: models/logistic_v1.joblib)
  CORS_ORIGINS - Comma-separated allowed origins (default: localhost:3000,5173)
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler as _default_http_exception_handler
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup → yield → shutdown."""
    # --- Startup ---
    db_path = os.environ.get("TENNIS_DB", "data/tennis.db")
    db_url = f"sqlite+aiosqlite:///{db_path}"

    engine = create_async_engine(
        db_url,
        connect_args={"check_same_thread": False},
        echo=False,
    )
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    app.state.engine = engine
    app.state.async_session_factory = session_factory
    app.state.db_path = db_path

    # Load model — warn and continue if file is missing
    model_path = os.environ.get("MODEL_PATH", "models/logistic_v1.joblib")
    model = None
    try:
        import asyncio
        from src.model.trainer import load_model
        loop = asyncio.get_event_loop()
        model = await loop.run_in_executor(None, load_model, model_path)
        logger.info("Model loaded from %s", model_path)
    except FileNotFoundError:
        logger.warning("Model file not found at %s — model features disabled", model_path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to load model from %s: %s — model features disabled", model_path, exc)

    app.state.model = model

    yield

    # --- Shutdown ---
    await app.state.engine.dispose()
    logger.info("Database engine disposed")


# ---------------------------------------------------------------------------
# Application instance
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Tennis Betting API",
    version="1.0.0",
    description="Quantitative tennis betting model — predictions, EV analysis, backtesting",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS middleware
# ---------------------------------------------------------------------------

_cors_env = os.environ.get("CORS_ORIGINS", "")
if _cors_env:
    _allowed_origins = [o.strip() for o in _cors_env.split(",") if o.strip()]
else:
    _allowed_origins = ["http://localhost:3000", "http://localhost:5173"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# ---------------------------------------------------------------------------
# Custom exception handler — structured JSON errors
# ---------------------------------------------------------------------------

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Return structured error JSON instead of FastAPI's default detail string.

    Catches both FastAPI HTTPException and Starlette's routing 404/405.
    Returns {"error": "<status_code>", "message": "<detail>"} format.
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": str(exc.status_code),
            "message": exc.detail,
        },
    )


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/api/v1/health", tags=["system"])
async def health(request: Request):
    """Basic liveness check. Returns model load status."""
    return {
        "status": "ok",
        "model_loaded": request.app.state.model is not None,
    }


# ---------------------------------------------------------------------------
# Router registration — read-only GET routers (Phase 5 Plan 02)
# ---------------------------------------------------------------------------

from src.api.routers import predict, backtest, bankroll, models, calibration, props

app.include_router(predict.router, prefix="/api/v1")
app.include_router(backtest.router, prefix="/api/v1")
app.include_router(bankroll.router, prefix="/api/v1")
app.include_router(models.router, prefix="/api/v1")
app.include_router(calibration.router, prefix="/api/v1")
app.include_router(props.router, prefix="/api/v1")

# ---------------------------------------------------------------------------
# Optional write routers (Phase 5 Plan 03 — wrapped in try/except)
# ---------------------------------------------------------------------------

try:
    from src.api.routers import odds  # noqa: F401
    app.include_router(odds.router, prefix="/api/v1")
except (ImportError, AttributeError):
    pass

try:
    from src.api.routers import refresh  # noqa: F401
    app.include_router(refresh.router, prefix="/api/v1")
except (ImportError, AttributeError):
    pass
