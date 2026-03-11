"""
LLM response schema validation with structured repair strategies.

Validates LLM JSON output against Pydantic schemas and attempts
JSON repair before giving up.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Generic, Type, TypeVar

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class ValidationResult(Generic[T]):
    def __init__(
        self,
        success: bool,
        model: T | None = None,
        error: str | None = None,
        attempts: int = 0,
    ):
        self.success = success
        self.model = model
        self.error = error
        self.attempts = attempts


class LLMResponseValidator:
    """Validates and repairs LLM JSON responses against Pydantic schemas."""

    @staticmethod
    def extract_json(text: str) -> str:
        """
        Extract JSON from LLM response that may contain markdown fences or prose.

        Strategies (tried in order):
        1. Strip whitespace — return if starts with { or [
        2. Extract from ```json ... ``` markdown fence
        3. Extract from ``` ... ``` fence
        4. Bracket matching to find first complete {...} or [...] block
        5. Return original text as fallback
        """
        text = text.strip()

        # Strategy 1: already looks like JSON
        if text.startswith(("{", "[")):
            return text

        # Strategy 2: ```json ... ``` fence
        fence_json = re.search(r"```json\s*\n?(.*?)\n?```", text, re.DOTALL)
        if fence_json:
            return fence_json.group(1).strip()

        # Strategy 3: ``` ... ``` fence (no language tag)
        fence_generic = re.search(r"```\s*\n?(.*?)\n?```", text, re.DOTALL)
        if fence_generic:
            return fence_generic.group(1).strip()

        # Strategy 4: bracket matching — find first { or [
        for start_char, end_char in [("{", "}"), ("[", "]")]:
            start_idx = text.find(start_char)
            if start_idx == -1:
                continue
            depth = 0
            in_string = False
            escape_next = False
            for i, ch in enumerate(text[start_idx:], start=start_idx):
                if escape_next:
                    escape_next = False
                    continue
                if ch == "\\" and in_string:
                    escape_next = True
                    continue
                if ch == '"':
                    in_string = not in_string
                    continue
                if not in_string:
                    if ch == start_char:
                        depth += 1
                    elif ch == end_char:
                        depth -= 1
                        if depth == 0:
                            return text[start_idx : i + 1]

        return text  # Strategy 5: fallback

    @staticmethod
    def repair_json(json_str: str) -> str:
        """
        Attempt common JSON repairs:
        - Remove trailing commas before } or ]
        - Normalize single-quoted strings (simple cases only)
        """
        # Remove trailing commas before closing braces/brackets
        repaired = re.sub(r",\s*([}\]])", r"\1", json_str)
        return repaired

    @classmethod
    def validate(cls, response_text: str, schema: Type[T]) -> ValidationResult[T]:
        """Validate LLM response text against a Pydantic schema."""
        extracted = cls.extract_json(response_text)
        try:
            data = json.loads(extracted)
            model = schema.model_validate(data)
            return ValidationResult(success=True, model=model, attempts=1)
        except json.JSONDecodeError as e:
            return ValidationResult(
                success=False, error=f"JSON parse error: {e}", attempts=1
            )
        except ValidationError as e:
            return ValidationResult(
                success=False, error=f"Schema validation error: {e}", attempts=1
            )

    @classmethod
    def validate_with_repair(
        cls, response_text: str, schema: Type[T]
    ) -> ValidationResult[T]:
        """
        Attempt validation, then JSON repair on failure, then give up.
        Returns a ValidationResult.
        """
        # First attempt: direct validation
        result = cls.validate(response_text, schema)
        if result.success:
            return result

        # Second attempt: extract + repair + validate
        extracted = cls.extract_json(response_text)
        repaired = cls.repair_json(extracted)
        try:
            data = json.loads(repaired)
            model = schema.model_validate(data)
            logger.info("JSON repaired successfully for schema %s", schema.__name__)
            return ValidationResult(success=True, model=model, attempts=2)
        except (json.JSONDecodeError, ValidationError) as e:
            return ValidationResult(
                success=False,
                error=f"Validation failed after repair: {e}",
                attempts=2,
            )
