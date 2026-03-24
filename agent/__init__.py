"""Multi-Agent Tarot system package.

This package holds the orchestration logic that wires Clarifier, Draw & Interpret,
Synthesis, and Safety Guard agents together. Concrete implementations live under
`nodes/`, shared infrastructure under `core/`, and workflow graphs under
`workflows/`.
"""

__all__ = [
    "core",
    "nodes",
    "workflows",
]
