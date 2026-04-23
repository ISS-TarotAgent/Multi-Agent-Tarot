"""Static 78-card Rider-Waite-Smith deck and seeded draw utilities.

Seeded draw approach:
- Each draw generates a fresh UUID seed → truly random per request
- Shuffle and orientation assignment use Python's Random(seed) → reproducible
  if the seed is stored (visible in trace metadata)

Card meanings are loaded from agent/data/tarot_meanings.json at module import.
"""

from __future__ import annotations

import json
import random
import uuid
from pathlib import Path
from typing import TypedDict

# ---------------------------------------------------------------------------
# Load meanings (once at import time)
# ---------------------------------------------------------------------------

_MEANINGS_PATH = Path(__file__).parent.parent / "data" / "tarot_meanings.json"

with _MEANINGS_PATH.open(encoding="utf-8") as _f:
    _MEANINGS: dict[str, dict[str, str]] = json.load(_f)


class TarotCard(TypedDict):
    card_code: str
    card_name: str
    upright_meaning: str
    reversed_meaning: str


# ---------------------------------------------------------------------------
# Full 78-card RWS deck
# ---------------------------------------------------------------------------

_CARD_CODES: list[tuple[str, str]] = [
    # ── Major Arcana (22) ────────────────────────────────────────────────────
    ("major-fool", "The Fool"),
    ("major-magician", "The Magician"),
    ("major-high-priestess", "The High Priestess"),
    ("major-empress", "The Empress"),
    ("major-emperor", "The Emperor"),
    ("major-hierophant", "The Hierophant"),
    ("major-lovers", "The Lovers"),
    ("major-chariot", "The Chariot"),
    ("major-strength", "Strength"),
    ("major-hermit", "The Hermit"),
    ("major-wheel-of-fortune", "Wheel of Fortune"),
    ("major-justice", "Justice"),
    ("major-hanged-man", "The Hanged Man"),
    ("major-death", "Death"),
    ("major-temperance", "Temperance"),
    ("major-devil", "The Devil"),
    ("major-tower", "The Tower"),
    ("major-star", "The Star"),
    ("major-moon", "The Moon"),
    ("major-sun", "The Sun"),
    ("major-judgement", "Judgement"),
    ("major-world", "The World"),
    # ── Cups (14) ────────────────────────────────────────────────────────────
    ("cups-ace", "Ace of Cups"),
    ("cups-2", "Two of Cups"),
    ("cups-3", "Three of Cups"),
    ("cups-4", "Four of Cups"),
    ("cups-5", "Five of Cups"),
    ("cups-6", "Six of Cups"),
    ("cups-7", "Seven of Cups"),
    ("cups-8", "Eight of Cups"),
    ("cups-9", "Nine of Cups"),
    ("cups-10", "Ten of Cups"),
    ("cups-page", "Page of Cups"),
    ("cups-knight", "Knight of Cups"),
    ("cups-queen", "Queen of Cups"),
    ("cups-king", "King of Cups"),
    # ── Wands (14) ───────────────────────────────────────────────────────────
    ("wands-ace", "Ace of Wands"),
    ("wands-2", "Two of Wands"),
    ("wands-3", "Three of Wands"),
    ("wands-4", "Four of Wands"),
    ("wands-5", "Five of Wands"),
    ("wands-6", "Six of Wands"),
    ("wands-7", "Seven of Wands"),
    ("wands-8", "Eight of Wands"),
    ("wands-9", "Nine of Wands"),
    ("wands-10", "Ten of Wands"),
    ("wands-page", "Page of Wands"),
    ("wands-knight", "Knight of Wands"),
    ("wands-queen", "Queen of Wands"),
    ("wands-king", "King of Wands"),
    # ── Swords (14) ──────────────────────────────────────────────────────────
    ("swords-ace", "Ace of Swords"),
    ("swords-2", "Two of Swords"),
    ("swords-3", "Three of Swords"),
    ("swords-4", "Four of Swords"),
    ("swords-5", "Five of Swords"),
    ("swords-6", "Six of Swords"),
    ("swords-7", "Seven of Swords"),
    ("swords-8", "Eight of Swords"),
    ("swords-9", "Nine of Swords"),
    ("swords-10", "Ten of Swords"),
    ("swords-page", "Page of Swords"),
    ("swords-knight", "Knight of Swords"),
    ("swords-queen", "Queen of Swords"),
    ("swords-king", "King of Swords"),
    # ── Pentacles (14) ───────────────────────────────────────────────────────
    ("pentacles-ace", "Ace of Pentacles"),
    ("pentacles-2", "Two of Pentacles"),
    ("pentacles-3", "Three of Pentacles"),
    ("pentacles-4", "Four of Pentacles"),
    ("pentacles-5", "Five of Pentacles"),
    ("pentacles-6", "Six of Pentacles"),
    ("pentacles-7", "Seven of Pentacles"),
    ("pentacles-8", "Eight of Pentacles"),
    ("pentacles-9", "Nine of Pentacles"),
    ("pentacles-10", "Ten of Pentacles"),
    ("pentacles-page", "Page of Pentacles"),
    ("pentacles-knight", "Knight of Pentacles"),
    ("pentacles-queen", "Queen of Pentacles"),
    ("pentacles-king", "King of Pentacles"),
]

TAROT_DECK: list[TarotCard] = [
    TarotCard(
        card_code=code,
        card_name=name,
        upright_meaning=_MEANINGS[code]["upright_meaning"],
        reversed_meaning=_MEANINGS[code]["reversed_meaning"],
    )
    for code, name in _CARD_CODES
]

assert len(TAROT_DECK) == 78, f"Expected 78 cards, got {len(TAROT_DECK)}"


# ---------------------------------------------------------------------------
# Draw utilities
# ---------------------------------------------------------------------------


class DrawnCard(TypedDict):
    card_code: str
    card_name: str
    orientation: str  # "UPRIGHT" | "REVERSED"
    meaning: str  # orientation-resolved meaning from tarot_meanings.json
    seed: str


def draw_cards(
    count: int,
    *,
    allow_reversed: bool = True,
    seed: str | None = None,
) -> tuple[list[DrawnCard], str]:
    """Randomly draw `count` distinct cards from the 78-card deck.

    Returns (drawn_cards, seed_used). Store the seed to replay the same draw.
    """
    used_seed = seed or uuid.uuid4().hex
    rng = random.Random(used_seed)

    deck = list(TAROT_DECK)
    rng.shuffle(deck)
    selected = deck[:count]

    orient_rng = random.Random(f"{used_seed}|orientation")
    result: list[DrawnCard] = []
    for card in selected:
        orientation = "REVERSED" if allow_reversed and orient_rng.choice([True, False]) else "UPRIGHT"
        meaning = card["reversed_meaning"] if orientation == "REVERSED" else card["upright_meaning"]
        result.append(
            DrawnCard(
                card_code=card["card_code"],
                card_name=card["card_name"],
                orientation=orientation,
                meaning=meaning,
                seed=used_seed,
            )
        )
    return result, used_seed
