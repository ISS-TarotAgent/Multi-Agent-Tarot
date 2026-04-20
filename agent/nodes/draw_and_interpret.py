"""Draw & Interpret Agent node stub."""

from __future__ import annotations

from agent.core import schemas

from agent.core.tarot_draw_service import TarotDrawService

from agent.core.tarot_repository import TarotRepository

from agent.core.model_gateway import ModelGateway


def _resolve_question(state: schemas.OrchestratorState) -> str:

    if state.finalize_result and state.finalize_result.reframed_question.strip():

        return state.finalize_result.reframed_question.strip()

    if state.final_question.strip():

        return state.final_question.strip()

    if state.clarification_result and state.clarification_result.normalized_question.strip():

        return state.clarification_result.normalized_question.strip()

    return state.raw_question.strip()


async def draw_and_interpret_node(state: schemas.OrchestratorState) -> schemas.OrchestratorState:
    """Handle card selection and per-card narrative."""

    question = _resolve_question(state)

    if not question:

        raise ValueError("DrawAndInterpret node requires a non-empty question")

    repository = TarotRepository()

    model_gateway = ModelGateway()

    service = TarotDrawService(

        repository=repository,

        model_gateway=model_gateway,

    )

    request = schemas.DrawInterpretRequest(

        session_id=state.session_id,

        question=question,

        spread_code=state.spread_code or "three_card_reflection",

        user_number=state.user_number or 17,

        allow_reversed=state.allow_reversed,

    )

    result = await service.execute(request)

    state.session_id = result.session_id

    state.final_question = question

    state.draw_interpret_result = result

    state.card_interpretations = result.cards

    return state
