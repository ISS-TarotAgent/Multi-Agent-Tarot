from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_tarot_reading_service
from app.application.services import TarotReadingService
from app.schemas.api.readings import CreateReadingRequest, ReadingResultResponse

router = APIRouter(prefix="/readings", tags=["readings"])


@router.post("", response_model=ReadingResultResponse, summary="Create a tarot reading")
def create_reading(
    request: CreateReadingRequest,
    service: TarotReadingService = Depends(get_tarot_reading_service),
) -> ReadingResultResponse:
    return service.create_reading(request)


@router.get("/{reading_id}", response_model=ReadingResultResponse, summary="Get a tarot reading")
def get_reading(
    reading_id: str,
    service: TarotReadingService = Depends(get_tarot_reading_service),
) -> ReadingResultResponse:
    return service.get_reading(reading_id)
