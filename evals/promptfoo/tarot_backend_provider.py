"""Promptfoo Python provider for the Multi-Agent Tarot workflow.

Runs TarotReflectionWorkflow directly (no HTTP server required),
so evals can run in CI without Docker.

Entry point used by promptfoo: call_api(prompt, options, context)
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from uuid import uuid4


# ---------------------------------------------------------------------------
# Path bootstrap
# ---------------------------------------------------------------------------

def _discover_venv_site_packages(venv_root: Path, *, platform: str = sys.platform) -> list[Path]:
    """Return candidate site-packages paths inside a venv.

    Used by call_api to extend sys.path when backend deps live in a local venv.
    """
    if platform == "win32":
        return [venv_root / "Lib" / "site-packages"]
    lib = venv_root / "lib"
    if lib.exists():
        return [p / "site-packages" for p in sorted(lib.iterdir()) if p.name.startswith("python")]
    return [venv_root / "lib" / "site-packages"]


def _bootstrap_paths() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    candidates = [str(repo_root), str(repo_root / "backend")]

    # Optionally include a local venv so promptfoo can find installed deps
    venv_root = repo_root / "backend" / ".venv"
    if venv_root.exists():
        for sp in _discover_venv_site_packages(venv_root):
            if sp.exists():
                candidates.append(str(sp))

    for path in reversed(candidates):
        if path not in sys.path:
            sys.path.insert(0, path)


# ---------------------------------------------------------------------------
# Provider entry point
# ---------------------------------------------------------------------------

def call_api(prompt: str, options: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """Promptfoo provider entry point.

    Args:
        prompt:  The rendered prompt string — treated as the tarot question.
        options: Provider options from promptfooconfig.yaml.
                 options['config'] may carry: locale, spread_type.
        context: Promptfoo execution context (vars, test metadata).

    Returns:
        {"output": {...}} with workflow result fields for assertion.
    """
    _bootstrap_paths()

    from agent.workflows.orchestrator import TarotReflectionWorkflow  # noqa: PLC0415
    from backend.app.domain.enums import SpreadType  # noqa: PLC0415

    cfg = (options or {}).get("config") or {}
    locale: str = cfg.get("locale", "zh-CN")
    spread_type = SpreadType(cfg.get("spread_type", "THREE_CARD_REFLECTION"))

    workflow = TarotReflectionWorkflow()
    state = workflow.run(
        session_id=str(uuid4()),
        reading_id=str(uuid4()),
        raw_question=prompt,
        locale=locale,
        spread_type=spread_type,
    )

    safety = state.safety_output
    clarification = state.clarification_output

    return {
        "output": {
            "status": state.status.value,
            "input_safety_status": state.input_safety_status,
            "input_risk_level": state.input_risk_level,
            "clarification_required": clarification.clarification_required if clarification else False,
            "cards_count": len(state.cards),
            "risk_level": safety.risk_level.value if safety else None,
            "action_taken": safety.action_taken.value if safety else None,
            "safe_summary": safety.safe_summary if safety else None,
            "trace_event_count": len(state.trace_events),
        }
    }
