"""Utilities to load versioned prompt templates from ../../prompts."""

from __future__ import annotations

from pathlib import Path
from typing import Dict

PROMPT_ROOT = Path(__file__).resolve().parents[2] / "prompts"


def load_prompt(name: str) -> str:
    """Return the raw prompt template text for the given name.

    Args:
        name: Prompt file name without the ``.md`` extension
              (e.g. ``"clarifier_init"``).

    Returns:
        Full text content of the prompt template.

    Raises:
        FileNotFoundError: When no matching ``.md`` file exists under
            ``prompts/``.
    """
    target = PROMPT_ROOT / f"{name}.md"
    if not target.exists():
        raise FileNotFoundError(
            f"Prompt template '{name}' not found. Expected file at: {target}"
        )
    return target.read_text(encoding="utf-8")


def list_prompts() -> Dict[str, Path]:
    """Enumerate available prompt templates.

    Returns:
        Mapping of prompt name (without ``.md``) to its absolute ``Path``.
    """
    return {p.stem: p for p in sorted(PROMPT_ROOT.glob("*.md"))}
