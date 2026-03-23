"""Utilities to load versioned prompt templates from ../../prompts."""

from __future__ import annotations

from pathlib import Path
from typing import Dict

PROMPT_ROOT = Path(__file__).resolve().parents[2] / "prompts"


def load_prompt(name: str) -> str:
    """Return the raw prompt template text.

    TODO:
        - define naming convention (e.g., clarifier/system_v1)
        - add caching and checksum validation
        - add error classes for missing/invalid prompts
    """

    target = PROMPT_ROOT / f"{name}.md"
    raise NotImplementedError(f"Prompt loader pending; expected file at {target}")


def list_prompts() -> Dict[str, Path]:
    """Enumerate available prompt templates for tooling support.

    TODO:
        - integrate with Promptfoo test suite
        - surface prompt versions for the frontend/debug UI
    """

    raise NotImplementedError("Prompt listing not implemented yet")
