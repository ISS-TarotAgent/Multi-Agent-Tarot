from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

import psycopg
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


def _run_command(
    command: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"command failed: {' '.join(command)}\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    return completed


def _docker_available() -> tuple[bool, str | None]:
    try:
        completed = subprocess.run(
            ["docker", "version", "--format", "{{.Server.Version}}"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except FileNotFoundError:
        return False, "docker executable was not found"
    except subprocess.TimeoutExpired:
        return False, "docker version timed out"

    if completed.returncode == 0:
        return True, None

    reason = completed.stderr.strip() or completed.stdout.strip() or "docker version failed"
    return False, reason


def _wait_for_postgres(database_url: str, *, timeout_seconds: int = 60) -> None:
    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with psycopg.connect(database_url, connect_timeout=2) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("select 1")
                    cursor.fetchone()
            return
        except psycopg.OperationalError as exc:
            last_error = exc
            time.sleep(1)
    raise RuntimeError(f"postgres container did not become ready in time: {last_error}")


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
def postgres_database_url(free_tcp_port_factory) -> str:
    docker_ready, reason = _docker_available()
    if not docker_ready:
        pytest.skip(f"Docker is required for PostgreSQL integration tests: {reason}")

    port = free_tcp_port_factory()
    container_name = f"multi-agent-tarot-pg-{uuid4().hex[:12]}"
    sqlalchemy_url = f"postgresql+psycopg://postgres:postgres@127.0.0.1:{port}/multi_agent_tarot_test"
    psycopg_url = f"postgresql://postgres:postgres@127.0.0.1:{port}/multi_agent_tarot_test"

    try:
        _run_command(
            [
                "docker",
                "run",
                "--rm",
                "-d",
                "--name",
                container_name,
                "-e",
                "POSTGRES_USER=postgres",
                "-e",
                "POSTGRES_PASSWORD=postgres",
                "-e",
                "POSTGRES_DB=multi_agent_tarot_test",
                "-p",
                f"127.0.0.1:{port}:5432",
                "postgres:16-alpine",
            ]
        )
        _wait_for_postgres(psycopg_url)

        env = os.environ.copy()
        env["DATABASE_URL"] = sqlalchemy_url
        _run_command(
            [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
            cwd=BACKEND_ROOT,
            env=env,
        )

        yield sqlalchemy_url
    finally:
        subprocess.run(
            ["docker", "rm", "-f", container_name],
            capture_output=True,
            text=True,
            check=False,
        )


@pytest.fixture
def postgres_db_client(postgres_database_url: str, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("DATABASE_URL", postgres_database_url)
    _clear_runtime_caches()
    app = create_app()

    with TestClient(app) as testing_client:
        yield testing_client

    _clear_runtime_caches()
