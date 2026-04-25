"""Multi-Agent Tarot system package.

This package holds the orchestration logic that wires Clarifier, Draw & Interpret,
Synthesis, and Safety Guard agents together. Concrete implementations live under
`nodes/`, shared infrastructure under `core/`, and workflow graphs under
`workflows/`.
"""

import sys
from pathlib import Path

# Ensure backend/ is on sys.path so that backend-internal imports (`from app.domain...`)
# resolve correctly when the agent package is used from the project root.
_backend_path = str(Path(__file__).resolve().parents[1] / "backend")
if _backend_path not in sys.path:
    sys.path.insert(0, _backend_path)

__all__ = [
    "core",
    "nodes",
    "workflows",
]
