"""Promptfoo Python provider for the Multi-Agent Tarot workflow.

Runs build_llm_workflow() directly (no HTTP server required), using real LLM
agents so evals exercise the full production path.

Entry point used by promptfoo: call_api(prompt, options, context)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4


# ---------------------------------------------------------------------------
# Path bootstrap
# ---------------------------------------------------------------------------


def _discover_venv_site_packages(venv_root: Path, *, platform: str = sys.platform) -> list[Path]:
    if platform == "win32":
        return [venv_root / "Lib" / "site-packages"]
    lib = venv_root / "lib"
    if lib.exists():
        return [p / "site-packages" for p in sorted(lib.iterdir()) if p.name.startswith("python")]
    return [venv_root / "lib" / "site-packages"]


def _bootstrap_paths() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    candidates = [str(repo_root), str(repo_root / "backend")]

    venv_root = repo_root / "backend" / ".venv"
    if venv_root.exists():
        for sp in _discover_venv_site_packages(venv_root):
            if sp.exists():
                candidates.append(str(sp))

    for path in reversed(candidates):
        if path not in sys.path:
            sys.path.insert(0, path)


def _load_env() -> None:
    """Load backend/.env so OPENAI_API_KEY and other settings are available."""
    repo_root = Path(__file__).resolve().parents[2]
    env_file = repo_root / "backend" / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


# ---------------------------------------------------------------------------
# Provider entry point
# ---------------------------------------------------------------------------


def call_api(prompt: str, options: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """Promptfoo provider entry point.

    Args:
        prompt:  The rendered prompt string — treated as the tarot question.
        options: Provider options from promptfooconfig.yaml.
        context: Promptfoo execution context (vars, test metadata).
                 context['vars']['skip_clarification'] = true skips the
                 clarification wait and drives the full pipeline to Safety Guard.

    Returns:
        {"output": {...}} with workflow result fields for assertion.
    """
    _bootstrap_paths()
    _load_env()

    from agent.workflows.orchestrator import build_llm_workflow  # noqa: PLC0415
    from backend.app.domain.enums import SpreadType  # noqa: PLC0415

    cfg = (options or {}).get("config") or {}
    spread_type = SpreadType(cfg.get("spread_type", "THREE_CARD_REFLECTION"))
    locale: str = cfg.get("locale", "zh-CN")

    # Per-test override: set skip_clarification=true in test vars to bypass
    # the clarification wait and drive the full pipeline (Draw → Synthesis →
    # Safety Guard). Required for happy-path and safety tests.
    vars_ = (context or {}).get("vars") or {}
    skip_clarification = str(vars_.get("skip_clarification", "false")).lower() == "true"

    workflow = build_llm_workflow()

    state = workflow.run(
        session_id=str(uuid4()),
        reading_id=str(uuid4()),
        raw_question=prompt,
        locale=locale,
        spread_type=spread_type,
        skip_clarification=skip_clarification,
    )

    safety = state.safety_output
    clarification = state.clarification_output
    cards = state.cards or []

    clarification_prompts_count = (
        len(clarification.clarification_prompts)
        if clarification and clarification.clarification_required
        else 0
    )
    cards_have_reflection_questions = bool(cards) and all(
        getattr(c, "reflection_question", None) for c in cards
    )
    cards_have_caution_notes = bool(cards) and all(
        getattr(c, "caution_note", None) for c in cards
    )
    cards_have_keywords = bool(cards) and all(
        getattr(c, "keywords", None) for c in cards
    )

    return {
        "output": {
            "status": state.status.value,
            "input_safety_status": state.input_safety_status,
            "input_risk_level": state.input_risk_level,
            "clarification_required": clarification.clarification_required if clarification else False,
            "clarification_prompts_count": clarification_prompts_count,
            "intent_tag": state.intent_tag,
            "cards_count": len(cards),
            "cards_have_reflection_questions": cards_have_reflection_questions,
            "cards_have_caution_notes": cards_have_caution_notes,
            "cards_have_keywords": cards_have_keywords,
            "risk_level": safety.risk_level.value if safety else None,
            "action_taken": safety.action_taken.value if safety else None,
            "safe_summary": safety.safe_summary if safety else None,
            "trace_event_count": len(state.trace_events),
        }
    }
