"""Deterministic redaction and local Ollama-assisted PII detection."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable
from typing import Any

EMAIL_PATTERN = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+(?![\w.-])")
PHONE_PATTERN = re.compile(r"(?<!\w)\+?\d[\d().\s-]{5,}\d(?!\w)")
DATE_PATTERN = re.compile(r"^\d{4}-\d{1,2}-\d{1,2}$")

Detector = Callable[[str], Iterable[dict[str, str]]]


class LocalOllamaVerifier:
    """Detect names and locations using an Ollama server on loopback only."""

    def __init__(self, model: str) -> None:
        try:
            from ollama import Client
        except ImportError as exc:
            raise RuntimeError("Install swimler with its Ollama dependency.") from exc
        self.client: Any = Client(host="http://127.0.0.1:11434")
        self.model = model

    def __call__(self, text: str) -> Iterable[dict[str, str]]:
        if not text.strip():
            return []

        schema = {
            "type": "object",
            "properties": {
                "entities": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string"},
                            "category": {"type": "string"},
                        },
                        "required": ["text", "category"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["entities"],
            "additionalProperties": False,
        }
        response = self.client.chat(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Identify only personal names and precise personal locations "
                        "that appear in the supplied text. Do not identify brands, "
                        "organizations, or generic places. Return the exact text spans "
                        "as JSON entities; do not rewrite the text."
                    ),
                },
                {"role": "user", "content": text},
            ],
            format=schema,
            options={"temperature": 0},
            stream=False,
        )
        message = response["message"] if isinstance(response, dict) else response.message
        content = message["content"] if isinstance(message, dict) else message.content
        try:
            result = json.loads(content)
        except (TypeError, json.JSONDecodeError) as exc:
            raise RuntimeError("Ollama returned invalid entity data.") from exc
        entities = result.get("entities") if isinstance(result, dict) else None
        if not isinstance(entities, list):
            raise RuntimeError("Ollama response did not contain an entity list.")
        return [
            item
            for item in entities
            if isinstance(item, dict)
            and isinstance(item.get("text"), str)
            and isinstance(item.get("category"), str)
        ]


def _brand_spans(text: str, brands: Iterable[str]) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for brand in brands:
        if not brand:
            continue
        pattern = re.compile(rf"(?<!\w){re.escape(brand)}(?!\w)", re.IGNORECASE)
        spans.extend(match.span() for match in pattern.finditer(text))
    return spans


def _overlaps(span: tuple[int, int], protected: list[tuple[int, int]]) -> bool:
    return any(span[0] < end and start < span[1] for start, end in protected)


def anonymize_line(
    text: str, detector: Detector, brands: Iterable[str] = ()
) -> tuple[str, dict[str, int]]:
    """Redact email addresses, phone numbers, and locally detected entities."""
    protected_brands = tuple(brand for brand in brands if brand)
    operations: dict[str, int] = {}

    for category, pattern, replacement in (
        ("email", EMAIL_PATTERN, "[EMAIL]"),
        ("phone", PHONE_PATTERN, "[PHONE]"),
    ):
        def replace(match: re.Match[str]) -> str:
            value = match.group()
            if category == "phone" and DATE_PATTERN.fullmatch(value.strip()):
                return value
            operations[category] = operations.get(category, 0) + 1
            return replacement

        text = pattern.sub(replace, text)

    entities = detector(text)
    for entity in entities:
        value = entity["text"].strip()
        category = re.sub(r"[^a-z0-9_]+", "_", entity["category"].strip().lower())
        category = category.strip("_")[:40] or "personal_data"
        if not value or value.casefold() in {brand.casefold() for brand in protected_brands}:
            continue
        pattern = re.compile(re.escape(value), re.IGNORECASE)
        spans = _brand_spans(text, protected_brands)
        replacement = f"[{category.upper().replace(' ', '_')}]"
        matches = list(pattern.finditer(text))
        replaceable = [match for match in matches if not _overlaps(match.span(), spans)]
        if replaceable:
            operations[category] = operations.get(category, 0) + len(replaceable)
            text = pattern.sub(
                lambda match: (
                    replacement
                    if not _overlaps(match.span(), _brand_spans(text, protected_brands))
                    else match.group()
                ),
                text,
            )
    return text, operations
