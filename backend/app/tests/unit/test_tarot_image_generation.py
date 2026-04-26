from __future__ import annotations

import base64
import importlib
import json
from pathlib import Path

from agent.core.tarot_deck import TAROT_DECK


def _load_module(name: str):
    return importlib.import_module(name)


def test_build_image_generation_request_uses_images_endpoint_and_single_prompt_payload() -> None:
    config_module = _load_module("scripts.tarot_image_generation.config")
    client_module = _load_module("scripts.tarot_image_generation.client")

    settings = config_module.ImageGenerationSettings(
        openai_api_key="test-key",
        openai_base_url="https://ai.centos.hk",
        openai_image_model="gpt-image-2",
        openai_image_timeout_seconds=90,
        openai_image_max_retries=2,
        openai_image_size=None,
    )

    request = client_module.build_image_generation_request(
        settings=settings,
        prompt="A complete tarot card prompt.",
    )

    assert request.url == "https://ai.centos.hk/v1/images/generations"
    assert request.timeout_seconds == 90
    assert request.payload["model"] == "gpt-image-2"
    assert request.payload["prompt"] == "A complete tarot card prompt."
    assert "size" not in request.payload
    assert request.headers["Accept"] == "application/json"
    assert request.headers["User-Agent"].startswith("Mozilla/5.0")
    assert "tools" not in request.payload
    assert "messages" not in request.payload
    assert "response" not in request.payload


def test_build_image_generation_request_includes_size_only_when_explicitly_configured() -> None:
    config_module = _load_module("scripts.tarot_image_generation.config")
    client_module = _load_module("scripts.tarot_image_generation.client")

    settings = config_module.ImageGenerationSettings(
        openai_api_key="test-key",
        openai_base_url="https://ai.centos.hk",
        openai_image_model="gpt-image-2",
        openai_image_size="1024x1536",
    )

    request = client_module.build_image_generation_request(
        settings=settings,
        prompt="A complete tarot card prompt.",
    )

    assert request.payload["size"] == "1024x1536"


def test_prompt_catalog_matches_backend_tarot_deck_truth() -> None:
    catalog_module = _load_module("scripts.tarot_image_generation.catalog")

    catalog = catalog_module.load_prompt_catalog()

    assert len(catalog) == 78
    assert [entry.card_code for entry in catalog] == [card["card_code"] for card in TAROT_DECK]
    assert all(entry.output_filename == f"{entry.card_code}.png" for entry in catalog)
    assert all(entry.prompt for entry in catalog)
    assert all("Negative prompt:" not in entry.prompt for entry in catalog)


def test_parse_image_response_supports_images_api_data_path() -> None:
    client_module = _load_module("scripts.tarot_image_generation.client")
    image_bytes = b"primary-image-bytes"
    image_base64 = base64.b64encode(image_bytes).decode("ascii")
    response_json = {
        "created": 1712345678,
        "data": [
            {
                "b64_json": image_base64,
                "revised_prompt": "Rewritten prompt",
            }
        ],
    }

    result = client_module.parse_image_response(response_json)

    assert result.model is None
    assert result.mime_type == "image/png"
    assert result.image_bytes == image_bytes
    assert result.image_source_path == "data[0].b64_json"
    assert result.text_summary == "Rewritten prompt"


def test_parse_image_response_supports_fallback_chat_images_path() -> None:
    client_module = _load_module("scripts.tarot_image_generation.client")
    image_bytes = b"fallback-image-bytes"
    image_base64 = base64.b64encode(image_bytes).decode("ascii")
    response_json = {
        "id": "chatcmpl-fallback",
        "model": "gpt-image-2",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "images": [
                        {
                            "b64_json": image_base64,
                            "mime_type": "image/png",
                        }
                    ],
                    "content": "Generated the image.",
                },
            }
        ],
    }

    result = client_module.parse_image_response(response_json)

    assert result.mime_type == "image/png"
    assert result.image_bytes == image_bytes
    assert result.image_source_path == "choices[0].message.images[0].b64_json"


def test_relay_request_error_string_includes_response_body_snippet() -> None:
    client_module = _load_module("scripts.tarot_image_generation.client")

    error = client_module.RelayRequestError(
        "Relay request failed with HTTP 503.",
        status_code=503,
        response_body='{"error":{"message":"auth_unavailable"}}',
    )

    assert "HTTP 503" in str(error)
    assert "auth_unavailable" in str(error)


def test_job_state_recycles_running_and_prompt_hash_changes_to_pending(tmp_path: Path) -> None:
    catalog_module = _load_module("scripts.tarot_image_generation.catalog")
    job_module = _load_module("scripts.tarot_image_generation.job")

    catalog = catalog_module.load_prompt_catalog()
    major_fool = next(entry for entry in catalog if entry.card_code == "major-fool")
    major_magician = next(entry for entry in catalog if entry.card_code == "major-magician")

    state_file = tmp_path / "job-state.json"
    state_file.write_text(
        json.dumps(
            {
                "cards": {
                    "major-fool": {
                        "card_code": "major-fool",
                        "status": "running",
                        "attempt_count": 1,
                        "prompt_hash": "old-hash",
                        "output_path": None,
                        "updated_at": "2026-04-26T00:00:00+00:00",
                        "error": None,
                    },
                    "major-magician": {
                        "card_code": "major-magician",
                        "status": "done",
                        "attempt_count": 1,
                        "prompt_hash": "outdated-hash",
                        "output_path": "generated/tarot-cards/images/major-magician.png",
                        "updated_at": "2026-04-26T00:00:00+00:00",
                        "error": None,
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    state = job_module.load_or_initialize_job_state(
        catalog=[major_fool, major_magician],
        state_file=state_file,
        skip_hash_check=False,
    )

    assert state.cards["major-fool"].status == "pending"
    assert state.cards["major-magician"].status == "pending"


def test_plan_run_skips_done_by_default_and_retries_failed_or_forced_cards() -> None:
    catalog_module = _load_module("scripts.tarot_image_generation.catalog")
    job_module = _load_module("scripts.tarot_image_generation.job")

    catalog = catalog_module.load_prompt_catalog()
    subset = [entry for entry in catalog if entry.card_code in {"major-fool", "major-magician", "major-world"}]
    state = job_module.create_empty_job_state(subset)

    state.cards["major-fool"].status = "done"
    state.cards["major-magician"].status = "failed"
    state.cards["major-world"].status = "pending"

    planned = job_module.plan_run(catalog=subset, state=state, force=False)
    forced = job_module.plan_run(catalog=subset, state=state, force=True)

    assert [entry.card_code for entry in planned] == ["major-magician", "major-world"]
    assert [entry.card_code for entry in forced] == ["major-fool", "major-magician", "major-world"]
