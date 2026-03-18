"""
FastAPI dependency injection for async database sessions.

Provides:
    get_db: async generator yielding an AsyncSession from the app's session factory.
    DbDep: Annotated type alias for use in route function signatures.

The session factory is set on app.state.async_session_factory during lifespan
startup (see main.py). This keeps the dependency stateless and testable.
"""

from __future__ import annotations

from typing import Annotated, AsyncGenerator

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession


async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """Yield an async SQLAlchemy session, closing it on exit.

    Reads the session factory from app.state (set during lifespan startup).
    Using request.app.state avoids circular imports between main.py and deps.py.

    Usage in route:
        @router.get("/example")
        async def example(db: DbDep):
            result = await db.execute(...)
    """
    async with request.app.state.async_session_factory() as session:
        yield session


# Annotated alias — use this in route signatures for concise dependency injection.
DbDep = Annotated[AsyncSession, Depends(get_db)]
