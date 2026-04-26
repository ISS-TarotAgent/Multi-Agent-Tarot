from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

CATALOG_FILE = Path(__file__).with_name("tarot_image_prompts.json")


@dataclass(frozen=True, slots=True)
class TarotImagePrompt:
    card_code: str
    card_name: str
    prompt: str
    output_filename: str


def load_prompt_catalog(path: Path | None = None) -> list[TarotImagePrompt]:
    catalog_path = path or CATALOG_FILE
    raw_items = json.loads(catalog_path.read_text(encoding="utf-8"))
    return [
        TarotImagePrompt(
            card_code=item["card_code"],
            card_name=item["card_name"],
            prompt=item["prompt"],
            output_filename=item["output_filename"],
        )
        for item in raw_items
    ]


def get_prompt_by_card_code(card_code: str, catalog: list[TarotImagePrompt] | None = None) -> TarotImagePrompt:
    for entry in catalog or load_prompt_catalog():
        if entry.card_code == card_code:
            return entry
    raise ValueError(f"Unknown tarot card code: {card_code}")


def compute_prompt_hash(entry: TarotImagePrompt) -> str:
    payload = json.dumps(
        {
            "card_code": entry.card_code,
            "card_name": entry.card_name,
            "prompt": entry.prompt,
            "output_filename": entry.output_filename,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
