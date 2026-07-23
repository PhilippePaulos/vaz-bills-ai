from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

import anthropic
from anthropic.types import (
    ContentBlockParam,
    MessageParam,
    ParsedMessage,
    TextBlockParam,
    ThinkingConfigAdaptiveParam,
)

from src.extraction.errors import ExtractionError
from src.extraction.images import image_block
from src.extraction.prompt import SYSTEM_PROMPT
from src.extraction.schema import DocumentExtrait
from src.extraction.validators import DEFAULT_VALIDATORS, Validator

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-opus-4-8"

MAX_TOKENS = 16_000

TIMEOUT_S = 300.0
MAX_RETRIES = 3


@dataclass(frozen=True)
class ExtractionResult:
    document: DocumentExtrait
    model: str
    input_tokens: int
    output_tokens: int


class DocumentExtractor:

    def __init__(
        self,
        client: Optional[anthropic.Anthropic] = None,
        model: str = DEFAULT_MODEL,
        validators: Sequence[Validator] = DEFAULT_VALIDATORS,
    ) -> None:
        self._client = client or anthropic.Anthropic(timeout=TIMEOUT_S, max_retries=MAX_RETRIES)
        self._model = model
        self._validators = tuple(validators)

    def extract(self, image_paths: Sequence[Path]) -> ExtractionResult:
        self._check_paths(image_paths)

        logger.info(
            "Calling %s: %d page(s), reading the document (may take 1-2 min)…",
            self._model, len(image_paths),
        )
        started = time.monotonic()
        response = self._client.messages.parse(
            model=self._model,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            thinking=ThinkingConfigAdaptiveParam(type="adaptive"),
            messages=[MessageParam(role="user", content=self._build_content(image_paths))],
            output_format=DocumentExtrait,
        )
        logger.info(
            "Response received in %.1f s (stop_reason=%s, %d tokens in / %d out)",
            time.monotonic() - started,
            response.stop_reason,
            response.usage.input_tokens,
            response.usage.output_tokens,
        )

        doc = self._parsed_document(response)
        for validate in self._validators:
            validate(doc)

        logger.info(
            "Extraction validated: %s no. %s, %d chapter(s), %d line(s), %d décompte line(s)",
            doc.type_doc or "document",
            doc.numero or "?",
            len(doc.chapitres),
            sum(len(c.lignes) for c in doc.chapitres),
            len(doc.decompte),
        )
        return ExtractionResult(
            document=doc,
            model=response.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )

    @staticmethod
    def _check_paths(image_paths: Sequence[Path]) -> None:
        if not image_paths:
            raise ValueError("No photo provided.")
        missing = [p for p in image_paths if not p.is_file()]
        if missing:
            raise FileNotFoundError(f"Photos not found: {', '.join(str(p) for p in missing)}")

    @staticmethod
    def _build_content(image_paths: Sequence[Path]) -> list[ContentBlockParam]:
        content: list[ContentBlockParam] = []
        for i, path in enumerate(image_paths, start=1):
            content.append(TextBlockParam(type="text", text=f"--- Page {i} of {len(image_paths)} ---"))
            content.append(image_block(path))
        content.append(TextBlockParam(type="text", text="Extract this document."))
        return content

    @staticmethod
    def _parsed_document(response: ParsedMessage[DocumentExtrait]) -> DocumentExtrait:
        if response.stop_reason == "refusal":
            raise ExtractionError(f"Request refused by the model guardrails: {response.stop_details}")
        if response.stop_reason == "max_tokens":
            raise ExtractionError(
                f"Response truncated at {MAX_TOKENS} tokens — document too long. "
                "Raise MAX_TOKENS and switch to streaming (messages.stream)."
            )
        if response.parsed_output is None:
            raise ExtractionError(f"No structured output (stop_reason={response.stop_reason!r}).")
        return response.parsed_output
