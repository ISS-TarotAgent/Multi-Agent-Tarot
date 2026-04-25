"""SQLAlchemy session factory placeholder."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession


async def get_session() -> AsyncSession:
    """TODO: implement engine + sessionmaker using Python 3.12 stack."""

    raise NotImplementedError("Database session factory not implemented yet")
