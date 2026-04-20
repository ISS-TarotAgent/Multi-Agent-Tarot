from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_tarot_reading_service
from app.application.services import TarotReadingService
from app.schemas.api.traces import ReadingTraceResponse

router = APIRouter(prefix="/readings", tags=["traces"])


@router.get("/{reading_id}/trace", response_model=ReadingTraceResponse, summary="Get reading trace")
def get_reading_trace(
    reading_id: str,
    service: TarotReadingService = Depends(get_tarot_reading_service),
) -> ReadingTraceResponse:
    return service.get_reading_trace(reading_id)
