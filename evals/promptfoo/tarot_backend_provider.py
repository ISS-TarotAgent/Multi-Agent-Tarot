from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"

def _discover_venv_site_packages(venv_root: Path, *, platform: str) -> list[Path]:
    if platform.startswith("win"):
        candidate = venv_root / "Lib" / "site-packages"
        return [candidate] if candidate.exists() else []

    lib_root = venv_root / "lib"
    if not lib_root.exists():
        return []
    return sorted(path for path in lib_root.glob("python*/site-packages") if path.exists())


def _bootstrap_backend_python_paths() -> None:
    candidate_paths = [
        REPO_ROOT,
        BACKEND_ROOT,
        *_discover_venv_site_packages(BACKEND_ROOT / ".venv", platform=sys.platform),
    ]
    for path in reversed(candidate_paths):
        path_str = str(path)
        if path.exists() and path_str not in sys.path:
            sys.path.insert(0, path_str)


_bootstrap_backend_python_paths()

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from fastapi.testclient import TestClient

from app.api.deps import get_db_session_dep
from app.infrastructure.db import Base
from app.main import create_app

ENGINE = create_engine(
    "sqlite+pysqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    future=True,
)
SESSION_FACTORY = sessionmaker(
    bind=ENGINE,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)
Base.metadata.create_all(ENGINE)

APP = create_app()


def _override_get_db_session_dep():
    session = SESSION_FACTORY()
    try:
        yield session
    finally:
        session.close()


APP.dependency_overrides[get_db_session_dep] = _override_get_db_session_dep
CLIENT = TestClient(APP)


def call_api(prompt: str, options: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    vars_payload = context.get("vars", {})
    response = CLIENT.post(
        "/api/v1/readings",
        json={
            "question": prompt,
            "locale": vars_payload.get("locale", "zh-CN"),
        },
    )
    try:
        body = response.json()
        output_str = json.dumps(body, ensure_ascii=False)
    except (ValueError, KeyError):
        output_str = response.text
    return {
        "output": output_str,
        "metadata": {
            "status_code": response.status_code,
        },
    }
