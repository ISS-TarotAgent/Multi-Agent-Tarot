"""Prompt template loading from the prompts/ directory."""

from __future__ import annotations

from pathlib import Path

PROMPT_ROOT = Path(__file__).resolve().parents[2] / "prompts"

_cache: dict[str, str] = {}


def load_prompt(name: str) -> str:
    """Load a prompt template by name (relative to prompts/, without .md extension).

    Examples::

        load_prompt("clarifier_system_prompt")
        load_prompt("security/safety_rewrite")
    """
    if name in _cache:
        return _cache[name]

    target = PROMPT_ROOT / f"{name}.md"
    if not target.exists():
        raise FileNotFoundError(
            f"Prompt template not found: '{name}' (expected file at {target})"
        )

    text = target.read_text(encoding="utf-8")
    _cache[name] = text
    return text


def list_prompts() -> dict[str, Path]:
    """Return a mapping of prompt name → absolute path for all .md files under prompts/."""
    return {
        p.relative_to(PROMPT_ROOT).with_suffix("").as_posix(): p
        for p in PROMPT_ROOT.rglob("*.md")
        if p.name != "README.md"
    }


def clear_cache() -> None:
    """Flush the in-process prompt cache (useful in tests)."""
    _cache.clear()
