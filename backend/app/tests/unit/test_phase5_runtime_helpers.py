from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

from app.tests.conftest import _docker_available


def _load_promptfoo_provider_module():
    repo_root = Path(__file__).resolve().parents[4]
    provider_path = repo_root / "evals" / "promptfoo" / "tarot_backend_provider.py"
    spec = importlib.util.spec_from_file_location("tarot_backend_provider_test", provider_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_promptfoo_provider_discovers_backend_venv_site_packages() -> None:
    module = _load_promptfoo_provider_module()
    venv_root = Path(__file__).resolve().parents[3] / ".venv"

    discovered_paths = module._discover_venv_site_packages(venv_root, platform="win32")

    assert venv_root / "Lib" / "site-packages" in discovered_paths


def test_docker_available_returns_false_with_cli_error(monkeypatch) -> None:
    def fake_run(*args, **kwargs):  # noqa: ANN002, ANN003
        return subprocess.CompletedProcess(
            args=args[0],
            returncode=1,
            stdout="",
            stderr="daemon unavailable",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    available, reason = _docker_available()

    assert available is False
    assert reason == "daemon unavailable"
