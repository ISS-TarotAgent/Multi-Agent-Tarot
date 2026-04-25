from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.deps import get_db_session_dep
from app.infrastructure.db import Base, get_engine, get_session_factory
from app.infrastructure.config.settings import get_settings
from app.main import create_app

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _clear_runtime_caches() -> None:
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()


@pytest.fixture(autouse=True)
def clear_settings_cache():
    _clear_runtime_caches()
    yield
    _clear_runtime_caches()


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


@pytest.fixture
def db_client(tmp_path) -> TestClient:
    database_path = tmp_path / "test.db"
    engine = create_engine(
        f"sqlite+pysqlite:///{database_path.as_posix()}",
        connect_args={"check_same_thread": False},
        future=True,
    )
    testing_session_factory = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    Base.metadata.create_all(engine)

    app = create_app()

    def override_get_db_session_dep():
        session = testing_session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db_session_dep] = override_get_db_session_dep

    with TestClient(app) as testing_client:
        yield testing_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def postgres_database_url() -> str:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL not set; set it to run PostgreSQL integration tests")
    yield database_url


@pytest.fixture
def postgres_db_client(postgres_database_url: str, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("DATABASE_URL", postgres_database_url)
    _clear_runtime_caches()
    app = create_app()

    with TestClient(app) as testing_client:
        yield testing_client

    _clear_runtime_caches()
