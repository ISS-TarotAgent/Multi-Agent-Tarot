from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter()

_DEMO_PAGE_PATH = Path(__file__).resolve().parents[3] / "frontend" / "demo" / "index.html"


@router.get("/demo", include_in_schema=False)
def get_demo_page() -> FileResponse:
    return FileResponse(_DEMO_PAGE_PATH)
