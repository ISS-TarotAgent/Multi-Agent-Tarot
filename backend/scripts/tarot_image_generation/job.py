from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from .catalog import TarotImagePrompt, compute_prompt_hash


@dataclass(slots=True)
class CardJobState:
    card_code: str
    status: str
    attempt_count: int
    prompt_hash: str
    output_path: str | None
    updated_at: str
    error: str | None


@dataclass(slots=True)
class TarotImageJobState:
    cards: dict[str, CardJobState] = field(default_factory=dict)


def create_empty_job_state(catalog: list[TarotImagePrompt]) -> TarotImageJobState:
    now = _utc_now_iso()
    return TarotImageJobState(
        cards={
            entry.card_code: CardJobState(
                card_code=entry.card_code,
                status="pending",
                attempt_count=0,
                prompt_hash=compute_prompt_hash(entry),
                output_path=None,
                updated_at=now,
                error=None,
            )
            for entry in catalog
        }
    )


def load_or_initialize_job_state(
    *,
    catalog: list[TarotImagePrompt],
    state_file: Path,
    skip_hash_check: bool,
) -> TarotImageJobState:
    if not state_file.exists():
        return create_empty_job_state(catalog)

    payload = json.loads(state_file.read_text(encoding="utf-8"))
    raw_cards = payload.get("cards", {})
    state = TarotImageJobState(cards={})
    now = _utc_now_iso()

    for entry in catalog:
        prompt_hash = compute_prompt_hash(entry)
        raw = raw_cards.get(entry.card_code)
        if isinstance(raw, dict):
            card_state = CardJobState(
                card_code=entry.card_code,
                status=str(raw.get("status", "pending")),
                attempt_count=int(raw.get("attempt_count", 0)),
                prompt_hash=str(raw.get("prompt_hash") or prompt_hash),
                output_path=raw.get("output_path"),
                updated_at=str(raw.get("updated_at") or now),
                error=raw.get("error"),
            )
        else:
            card_state = CardJobState(
                card_code=entry.card_code,
                status="pending",
                attempt_count=0,
                prompt_hash=prompt_hash,
                output_path=None,
                updated_at=now,
                error=None,
            )

        if card_state.status == "running":
            card_state.status = "pending"
            card_state.updated_at = now
            card_state.error = "Recovered interrupted run."

        if not skip_hash_check and card_state.prompt_hash != prompt_hash:
            card_state.status = "pending"
            card_state.prompt_hash = prompt_hash
            card_state.output_path = None
            card_state.updated_at = now
            card_state.error = "Prompt hash changed; scheduled for regeneration."
        else:
            card_state.prompt_hash = prompt_hash

        state.cards[entry.card_code] = card_state

    return state


def save_job_state(state: TarotImageJobState, state_file: Path) -> None:
    state_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "cards": {
            card_code: asdict(card_state)
            for card_code, card_state in state.cards.items()
        }
    }
    state_file.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def plan_run(
    *,
    catalog: list[TarotImagePrompt],
    state: TarotImageJobState,
    force: bool,
) -> list[TarotImagePrompt]:
    planned: list[TarotImagePrompt] = []
    now = _utc_now_iso()
    for entry in catalog:
        card_state = state.cards[entry.card_code]
        if force:
            card_state.status = "pending"
            card_state.output_path = None
            card_state.updated_at = now
            card_state.error = None
            planned.append(entry)
            continue
        if card_state.status == "done":
            continue
        planned.append(entry)
    return planned


def mark_running(state: TarotImageJobState, entry: TarotImagePrompt) -> None:
    card_state = state.cards[entry.card_code]
    card_state.status = "running"
    card_state.attempt_count += 1
    card_state.updated_at = _utc_now_iso()
    card_state.error = None


def mark_done(
    state: TarotImageJobState,
    entry: TarotImagePrompt,
    *,
    output_path: str,
) -> None:
    card_state = state.cards[entry.card_code]
    card_state.status = "done"
    card_state.output_path = output_path
    card_state.prompt_hash = compute_prompt_hash(entry)
    card_state.updated_at = _utc_now_iso()
    card_state.error = None


def mark_failed(
    state: TarotImageJobState,
    entry: TarotImagePrompt,
    *,
    error: str,
) -> None:
    card_state = state.cards[entry.card_code]
    card_state.status = "failed"
    card_state.updated_at = _utc_now_iso()
    card_state.error = error


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()
