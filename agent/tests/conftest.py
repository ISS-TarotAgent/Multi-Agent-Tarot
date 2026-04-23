"""Pytest configuration for agent tests.

Adds backend/ to sys.path so that backend's internal imports (from app.domain.enums ...)
resolve correctly when running tests from the project root.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2] / "backend"))
