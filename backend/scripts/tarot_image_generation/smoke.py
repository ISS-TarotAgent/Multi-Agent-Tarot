from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .catalog import get_prompt_by_card_code, load_prompt_catalog
from .client import (
    build_image_generation_payload,
    create_image,
    response_summary,
    save_image_bytes,
    save_response_json,
)
from .config import get_image_generation_settings


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    settings = get_image_generation_settings()
    catalog = load_prompt_catalog()
    entry = get_prompt_by_card_code(args.card_code, catalog)
    output_dir = Path(args.output_dir) if args.output_dir else settings.default_output_root / "test"
    image_path = output_dir / entry.output_filename
    response_path = output_dir / f"{entry.card_code}.response.json"

    if args.dry_run:
        payload = {
            "card_code": entry.card_code,
            "model": settings.openai_image_model,
            "url": settings.images_generations_url,
            "output_path": str(image_path),
            "payload": build_image_generation_payload(
                model=settings.openai_image_model,
                prompt=entry.prompt,
                size=settings.openai_image_size,
            ),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    result = create_image(
        settings=settings,
        prompt=entry.prompt,
    )
    save_image_bytes(image_path, result.parsed_image.image_bytes)
    if args.save_response_json:
        save_response_json(response_path, result.response_json)

    print(f"model={settings.openai_image_model}")
    print(f"card_code={entry.card_code}")
    print(f"output_path={image_path}")
    print(f"elapsed_seconds={result.elapsed_seconds:.2f}")
    print(f"response_summary={response_summary(result)}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Smoke test a single tarot card image generation request.")
    parser.add_argument("--card-code", default="major-fool")
    parser.add_argument("--output-dir")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--save-response-json",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    return parser
