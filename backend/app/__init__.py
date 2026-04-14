from __future__ import annotations

import sys
from pathlib import Path

# Keep the repo root importable so the backend can load the sibling `agent/` package
# when developers run the app from `backend/`.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

__all__ = []
