from agent.core.schemas import DrawInterpretRequest
from agent.core.tarot_draw_service import TarotDrawService


class DummyModelGateway:
    model_name = "dummy-model"

    async def generate_json(self, system_prompt: str, user_input: str):
        return {
            "keywords": ["开始", "观察"],
            "position_interpretation": "这张牌提示你关注当前阶段中的变化与内在选择，不必急着立刻下结论。你可以先看清自己真正想推动的方向。",
            "reflection_question": "你现在最需要确认的内在方向是什么？",
            "caution_note": "该解释用于个人反思，不构成事实预测或专业建议。",
        }


class DummyRepository:
    def get_spread_by_code(self, spread_code):
        return {
            "id": 1,
            "spread_code": "three_card_reflection",
            "spread_name": "Three Card Reflection",
            "description": "现状 / 阻碍 / 建议",
            "card_count": 3,
        }

    def get_spread_positions(self, spread_id):
        return [
            {"position_index": 1, "label": "现状", "meaning": "当前处境"},
            {"position_index": 2, "label": "阻碍", "meaning": "当前阻碍"},
            {"position_index": 3, "label": "建议", "meaning": "建议方向"},
        ]

    def list_active_major_arcana_cards(self):
        return [
            {"id": 1, "card_code": "the_fool", "name_cn": "愚者", "name_en": "The Fool", "card_number": 0},
            {"id": 2, "card_code": "the_magician", "name_cn": "魔术师", "name_en": "The Magician", "card_number": 1},
            {"id": 3, "card_code": "the_high_priestess", "name_cn": "女祭司", "name_en": "The High Priestess", "card_number": 2},
            {"id": 4, "card_code": "the_empress", "name_cn": "皇后", "name_en": "The Empress", "card_number": 3},
        ]

    def get_card_meaning(self, card_id, orientation, version="v1"):
        return {
            "keywords": ["开始", "探索"],
            "core_meaning": "象征新的起点与内在探索。",
            "advice": "先观察，再行动。",
            "reflection_prompt": "你真正想开始的是什么？",
        }

    def create_tarot_session(self, *args, **kwargs):
        return 101

    def mark_tarot_session_completed(self, session_row_id):
        return None

    def create_draw(self, *args, **kwargs):
        return 202

    def create_draw_card(self, *args, **kwargs):
        return None

    def create_interpretation(self, *args, **kwargs):
        return None


async def test_draw_and_interpret_service_runs():
    service = TarotDrawService(
        repository=DummyRepository(),
        model_gateway=DummyModelGateway(),
    )

    req = DrawInterpretRequest(
        question="我最近是否应该尝试新的方向？",
        spread_code="three_card_reflection",
        user_number=17,
        allow_reversed=True,
        session_id="sess_test_001",
    )

    result = await service.execute(req)

    assert result.session_id == "sess_test_001"
    assert result.spread_code == "three_card_reflection"
    assert len(result.cards) == 3
    assert result.trace.model_name == "dummy-model"