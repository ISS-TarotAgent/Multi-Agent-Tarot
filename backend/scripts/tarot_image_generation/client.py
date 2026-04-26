from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from .config import ImageGenerationSettings


@dataclass(frozen=True, slots=True)
class ImageGenerationRequest:
    url: str
    payload: dict[str, Any]
    headers: dict[str, str]
    timeout_seconds: int


@dataclass(frozen=True, slots=True)
class ParsedImageResponse:
    model: str | None
    response_id: str | None
    image_bytes: bytes
    mime_type: str
    image_source_path: str
    text_summary: str


@dataclass(frozen=True, slots=True)
class ImageGenerationExecutionResult:
    request: ImageGenerationRequest
    response_json: dict[str, Any]
    parsed_image: ParsedImageResponse
    request_id: str | None
    elapsed_seconds: float


class RelayRequestError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        response_body: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body

    def __str__(self) -> str:
        message = super().__str__()
        if not self.response_body:
            return message
        body = self.response_body.strip().replace("\r", " ").replace("\n", " ")
        body_snippet = body[:500]
        return f"{message} Response body: {body_snippet}"


class ResponseParseError(RuntimeError):
    """Raised when the relay response does not contain a supported image payload."""


def build_image_generation_request(
    *,
    settings: ImageGenerationSettings,
    prompt: str,
) -> ImageGenerationRequest:
    payload = build_image_generation_payload(
        model=settings.openai_image_model,
        prompt=prompt,
        size=settings.openai_image_size,
    )
    return ImageGenerationRequest(
        url=settings.images_generations_url,
        payload=payload,
        headers={
            "Authorization": f"Bearer {settings.require_api_key()}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/135.0.0.0 Safari/537.36"
            ),
        },
        timeout_seconds=settings.openai_image_timeout_seconds,
    )


def build_image_generation_payload(
    *,
    model: str,
    prompt: str,
    size: str | None,
) -> dict[str, Any]:
    payload = {
        "model": model,
        "prompt": prompt,
    }
    if size:
        payload["size"] = size
    return payload


def create_image(
    *,
    settings: ImageGenerationSettings,
    prompt: str,
) -> ImageGenerationExecutionResult:
    request = build_image_generation_request(
        settings=settings,
        prompt=prompt,
    )
    started_at = time.perf_counter()
    response_json, response_headers = _send_request(request)
    elapsed_seconds = time.perf_counter() - started_at
    parsed_image = parse_image_response(response_json)
    return ImageGenerationExecutionResult(
        request=request,
        response_json=response_json,
        parsed_image=parsed_image,
        request_id=response_headers.get("x-request-id"),
        elapsed_seconds=elapsed_seconds,
    )


def parse_image_response(response_json: dict[str, Any]) -> ParsedImageResponse:
    primary = _extract_from_images_api_data(response_json)
    if primary is not None:
        image_bytes, mime_type, source_path, text_summary = primary
        return ParsedImageResponse(
            model=_as_string(response_json.get("model")),
            response_id=_as_string(response_json.get("id")),
            image_bytes=image_bytes,
            mime_type=mime_type,
            image_source_path=source_path,
            text_summary=text_summary,
        )

    choice = _first_choice(response_json)
    message = choice.get("message") if isinstance(choice, dict) else None
    if not isinstance(message, dict):
        raise ResponseParseError("Relay response missing choices[0].message.")

    primary = _extract_from_content_parts(message)
    if primary is not None:
        image_bytes, mime_type, source_path = primary
        return ParsedImageResponse(
            model=_as_string(response_json.get("model")),
            response_id=_as_string(response_json.get("id")),
            image_bytes=image_bytes,
            mime_type=mime_type,
            image_source_path=source_path,
            text_summary=_collect_text_summary(message),
        )

    fallback = _extract_from_images_array(message)
    if fallback is not None:
        image_bytes, mime_type, source_path = fallback
        return ParsedImageResponse(
            model=_as_string(response_json.get("model")),
            response_id=_as_string(response_json.get("id")),
            image_bytes=image_bytes,
            mime_type=mime_type,
            image_source_path=source_path,
            text_summary=_collect_text_summary(message),
        )

    raise ResponseParseError("Relay response did not contain a supported image payload.")


def save_image_bytes(path, image_bytes: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(image_bytes)


def save_response_json(path, response_json: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(response_json, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def response_summary(result: ImageGenerationExecutionResult) -> str:
    summary_bits = [
        f"response_id={result.parsed_image.response_id or 'n/a'}",
        f"request_id={result.request_id or 'n/a'}",
        f"image_path={result.parsed_image.image_source_path}",
        f"text={result.parsed_image.text_summary or 'n/a'}",
    ]
    return ", ".join(summary_bits)


def _send_request(request: ImageGenerationRequest) -> tuple[dict[str, Any], dict[str, str]]:
    encoded_payload = json.dumps(request.payload).encode("utf-8")
    http_request = urllib.request.Request(
        request.url,
        data=encoded_payload,
        headers=request.headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(http_request, timeout=request.timeout_seconds) as response:
            response_body = response.read().decode("utf-8")
            response_json = json.loads(response_body)
            headers = {key.lower(): value for key, value in response.headers.items()}
            return response_json, headers
    except urllib.error.HTTPError as exc:  # pragma: no cover - exercised through live smoke
        body = exc.read().decode("utf-8", errors="replace")
        raise RelayRequestError(
            f"Relay request failed with HTTP {exc.code}.",
            status_code=exc.code,
            response_body=body,
        ) from exc
    except urllib.error.URLError as exc:  # pragma: no cover - exercised through live smoke
        raise RelayRequestError(f"Relay request failed: {exc.reason}") from exc
    except json.JSONDecodeError as exc:  # pragma: no cover - exercised through live smoke
        raise RelayRequestError("Relay response was not valid JSON.") from exc


def _first_choice(response_json: dict[str, Any]) -> dict[str, Any]:
    choices = response_json.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ResponseParseError("Relay response missing choices[0].")
    choice = choices[0]
    if not isinstance(choice, dict):
        raise ResponseParseError("Relay response choices[0] was not an object.")
    return choice


def _extract_from_images_api_data(
    response_json: dict[str, Any],
) -> tuple[bytes, str, str, str] | None:
    data = response_json.get("data")
    if not isinstance(data, list) or not data:
        return None

    first = data[0]
    if not isinstance(first, dict):
        return None

    mime_hint = _as_string(first.get("mime_type"))
    if isinstance(first.get("b64_json"), str):
        image_bytes, mime_type = _decode_image_candidate(first["b64_json"], mime_hint)
        return image_bytes, mime_type, "data[0].b64_json", _as_string(first.get("revised_prompt")) or ""

    if isinstance(first.get("url"), str):
        image_bytes, mime_type = _decode_image_candidate(first["url"], mime_hint)
        return image_bytes, mime_type, "data[0].url", _as_string(first.get("revised_prompt")) or ""

    return None


def _extract_from_content_parts(message: dict[str, Any]) -> tuple[bytes, str, str] | None:
    content = message.get("content")
    if not isinstance(content, list):
        return None

    for index, part in enumerate(content):
        if not isinstance(part, dict):
            continue
        candidate = None
        mime_hint = _as_string(part.get("mime_type"))
        if isinstance(part.get("image_url"), dict):
            image_url = part["image_url"]
            candidate = image_url.get("url") or image_url.get("b64_json") or image_url.get("data")
            mime_hint = mime_hint or _as_string(image_url.get("mime_type"))
            source_path = f"choices[0].message.content[{index}].image_url.url"
        elif isinstance(part.get("image_url"), str):
            candidate = part.get("image_url")
            source_path = f"choices[0].message.content[{index}].image_url"
        elif isinstance(part.get("url"), str):
            candidate = part.get("url")
            source_path = f"choices[0].message.content[{index}].url"
        elif isinstance(part.get("b64_json"), str):
            candidate = part.get("b64_json")
            source_path = f"choices[0].message.content[{index}].b64_json"
        else:
            continue

        image_bytes, mime_type = _decode_image_candidate(candidate, mime_hint)
        return image_bytes, mime_type, source_path

    return None


def _extract_from_images_array(message: dict[str, Any]) -> tuple[bytes, str, str] | None:
    images = message.get("images")
    if not isinstance(images, list):
        return None

    for index, image in enumerate(images):
        if not isinstance(image, dict):
            continue
        mime_hint = _as_string(image.get("mime_type"))
        if isinstance(image.get("b64_json"), str):
            image_bytes, mime_type = _decode_image_candidate(image["b64_json"], mime_hint)
            return image_bytes, mime_type, f"choices[0].message.images[{index}].b64_json"
        if isinstance(image.get("image_url"), dict):
            image_url = image["image_url"]
            candidate = image_url.get("url") or image_url.get("b64_json") or image_url.get("data")
            image_bytes, mime_type = _decode_image_candidate(candidate, mime_hint or _as_string(image_url.get("mime_type")))
            return image_bytes, mime_type, f"choices[0].message.images[{index}].image_url.url"
        if isinstance(image.get("url"), str):
            image_bytes, mime_type = _decode_image_candidate(image["url"], mime_hint)
            return image_bytes, mime_type, f"choices[0].message.images[{index}].url"
    return None


def _decode_image_candidate(candidate: Any, mime_hint: str | None) -> tuple[bytes, str]:
    if not isinstance(candidate, str) or not candidate:
        raise ResponseParseError("Relay image payload was empty.")
    if candidate.startswith("data:"):
        header, _, encoded = candidate.partition(",")
        if not encoded:
            raise ResponseParseError("Relay image payload data URL was empty.")
        mime_type = header.removeprefix("data:").split(";")[0] or (mime_hint or "image/png")
        return base64.b64decode(encoded), mime_type
    return base64.b64decode(candidate), mime_hint or "image/png"


def _collect_text_summary(message: dict[str, Any]) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return content[:200]
    if isinstance(content, list):
        texts: list[str] = []
        for part in content:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                texts.append(part["text"])
        return " ".join(texts)[:200]
    return ""


def _as_string(value: Any) -> str | None:
    return value if isinstance(value, str) else None
