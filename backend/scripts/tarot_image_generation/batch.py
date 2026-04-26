from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Sequence

from .catalog import TarotImagePrompt, get_prompt_by_card_code, load_prompt_catalog
from .client import (
    build_image_generation_payload,
    create_image,
    response_summary,
    save_image_bytes,
    save_response_json,
)
from .config import get_image_generation_settings
from .job import (
    TarotImageJobState,
    load_or_initialize_job_state,
    mark_done,
    mark_failed,
    mark_running,
    plan_run,
    save_job_state,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    settings = get_image_generation_settings()
    catalog = load_prompt_catalog()
    output_root = Path(args.output_dir) if args.output_dir else settings.default_output_root
    state_file = Path(args.state_file) if args.state_file else output_root / "job-state.json"
    images_dir = output_root / "images"
    responses_dir = output_root / "responses"
    failures_file = output_root / "failures.jsonl"
    max_retries = args.max_retries or settings.openai_image_max_retries

    selected_catalog = _select_catalog(
        catalog,
        only_card=args.only_card,
        from_card=args.from_card,
        limit=args.limit,
    )
    state = load_or_initialize_job_state(
        catalog=catalog,
        state_file=state_file,
        skip_hash_check=args.skip_hash_check,
    )
    run_queue = plan_run(
        catalog=selected_catalog,
        state=state,
        force=args.force,
    )

    if args.dry_run:
        for entry in run_queue:
            payload = {
                "card_code": entry.card_code,
                "output_path": str(images_dir / entry.output_filename),
                "url": settings.images_generations_url,
                "model": settings.openai_image_model,
                "payload": build_image_generation_payload(
                    model=settings.openai_image_model,
                    prompt=entry.prompt,
                    size=settings.openai_image_size,
                ),
            }
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        print(
            json.dumps(
                {
                    "selected_cards": [entry.card_code for entry in run_queue],
                    "state_file": str(state_file),
                    "images_dir": str(images_dir),
                    "responses_dir": str(responses_dir),
                    "failures_file": str(failures_file),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    save_job_state(state, state_file)
    started_at = time.perf_counter()
    success_count = 0
    failure_count = 0
    failed_cards: list[str] = []
    skipped_count = len(selected_catalog) - len(run_queue)

    for entry in run_queue:
        card_failed = True
        for _ in range(max(1, max_retries)):
            mark_running(state, entry)
            save_job_state(state, state_file)
            try:
                result = create_image(
                    settings=settings,
                    prompt=entry.prompt,
                )
                image_path = images_dir / entry.output_filename
                save_image_bytes(image_path, result.parsed_image.image_bytes)
                if args.save_response_json:
                    save_response_json(responses_dir / f"{entry.card_code}.json", result.response_json)
                mark_done(state, entry, output_path=str(image_path))
                save_job_state(state, state_file)
                print(f"[done] {entry.card_code} -> {image_path}")
                print(f"        {response_summary(result)}")
                success_count += 1
                card_failed = False
                break
            except Exception as exc:  # noqa: BLE001
                error_message = str(exc)
                mark_failed(state, entry, error=error_message)
                save_job_state(state, state_file)
                _append_failure_log(
                    failures_file,
                    state=state,
                    entry=entry,
                    error=error_message,
                )
                print(f"[retry] {entry.card_code} failed: {error_message}", file=sys.stderr)

        if card_failed:
            failure_count += 1
            failed_cards.append(entry.card_code)

    elapsed_seconds = time.perf_counter() - started_at
    print(
        json.dumps(
            {
                "success_count": success_count,
                "failure_count": failure_count,
                "skipped_count": skipped_count,
                "elapsed_seconds": round(elapsed_seconds, 2),
                "failed_cards": failed_cards,
                "state_file": str(state_file),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if failure_count == 0 else 1


def _select_catalog(
    catalog: list[TarotImagePrompt],
    *,
    only_card: str | None,
    from_card: str | None,
    limit: int | None,
) -> list[TarotImagePrompt]:
    selected = list(catalog)
    if only_card:
        return [get_prompt_by_card_code(only_card, selected)]
    if from_card:
        start_index = next(
            (index for index, entry in enumerate(selected) if entry.card_code == from_card),
            None,
        )
        if start_index is None:
            raise ValueError(f"Unknown --from-card value: {from_card}")
        selected = selected[start_index:]
    if limit is not None:
        selected = selected[:limit]
    return selected


def _append_failure_log(
    failures_file: Path,
    *,
    state: TarotImageJobState,
    entry: TarotImagePrompt,
    error: str,
) -> None:
    failures_file.parent.mkdir(parents=True, exist_ok=True)
    card_state = state.cards[entry.card_code]
    payload = {
        "card_code": entry.card_code,
        "attempt_count": card_state.attempt_count,
        "error": error,
        "updated_at": card_state.updated_at,
    }
    with failures_file.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Batch generate tarot card images with resumable state.")
    parser.add_argument("--output-dir")
    parser.add_argument("--state-file")
    parser.add_argument("--only-card")
    parser.add_argument("--from-card")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--max-retries", type=int)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--save-response-json",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument("--skip-hash-check", action="store_true")
    return parser
