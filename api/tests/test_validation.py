"""Unit tests for LLM response validation utilities."""
from __future__ import annotations

import json
import pytest

from app.providers.validation import LLMResponseValidator, ValidationResult
from app.schemas.work_items import WorkItem, WorkItemHierarchy, WorkItemType


# ---------------------------------------------------------------------------
# TestExtractJson
# ---------------------------------------------------------------------------


class TestExtractJson:
    def test_plain_json_object(self):
        raw = '{"items": []}'
        assert LLMResponseValidator.extract_json(raw) == raw

    def test_plain_json_array(self):
        raw = '[{"type": "epic", "title": "T", "description": "", "labels": [], "children": []}]'
        assert LLMResponseValidator.extract_json(raw) == raw

    def test_markdown_fence_json(self):
        raw = '```json\n{"items": []}\n```'
        assert LLMResponseValidator.extract_json(raw) == '{"items": []}'

    def test_markdown_fence_no_lang(self):
        raw = '```\n{"items": []}\n```'
        assert LLMResponseValidator.extract_json(raw) == '{"items": []}'

    def test_prose_before_json(self):
        raw = "Here is the JSON:\n\n{\"items\": []}"
        result = LLMResponseValidator.extract_json(raw)
        assert result == '{"items": []}'

    def test_nested_json(self):
        raw = '{"items": [{"type": "epic", "children": [{"type": "story"}]}]}'
        result = LLMResponseValidator.extract_json(raw)
        json.loads(result)  # should not raise


# ---------------------------------------------------------------------------
# TestRepairJson
# ---------------------------------------------------------------------------


class TestRepairJson:
    def test_trailing_comma_object(self):
        raw = '{"a": 1,}'
        repaired = LLMResponseValidator.repair_json(raw)
        data = json.loads(repaired)
        assert data == {"a": 1}

    def test_trailing_comma_array(self):
        raw = '[1, 2,]'
        repaired = LLMResponseValidator.repair_json(raw)
        data = json.loads(repaired)
        assert data == [1, 2]

    def test_no_trailing_comma_unchanged(self):
        raw = '{"a": 1}'
        assert LLMResponseValidator.repair_json(raw) == raw


# ---------------------------------------------------------------------------
# TestValidate
# ---------------------------------------------------------------------------


_VALID_HIERARCHY = {
    "items": [
        {
            "type": "epic",
            "title": "Test epic",
            "description": "desc",
            "labels": ["backend"],
            "children": [],
        }
    ]
}


class TestValidate:
    def test_valid_response(self):
        result = LLMResponseValidator.validate(json.dumps(_VALID_HIERARCHY), WorkItemHierarchy)
        assert result.success is True
        assert result.model is not None
        assert len(result.model.items) == 1

    def test_invalid_json(self):
        result = LLMResponseValidator.validate("{not valid json}", WorkItemHierarchy)
        assert result.success is False
        assert "JSON parse" in (result.error or "")

    def test_schema_mismatch(self):
        result = LLMResponseValidator.validate('{"wrong_key": 123}', WorkItemHierarchy)
        assert result.success is False
        assert result.error is not None

    def test_markdown_wrapped_json(self):
        wrapped = f"```json\n{json.dumps(_VALID_HIERARCHY)}\n```"
        result = LLMResponseValidator.validate(wrapped, WorkItemHierarchy)
        assert result.success is True


# ---------------------------------------------------------------------------
# TestValidateWithRepair
# ---------------------------------------------------------------------------


class TestValidateWithRepair:
    def test_valid_response_passes(self):
        result = LLMResponseValidator.validate_with_repair(
            json.dumps(_VALID_HIERARCHY), WorkItemHierarchy
        )
        assert result.success is True

    def test_trailing_comma_repaired(self):
        raw_with_comma = '{"items": [{"type": "epic", "title": "T", "description": "", "labels": [], "children": []},]}'
        result = LLMResponseValidator.validate_with_repair(raw_with_comma, WorkItemHierarchy)
        assert result.success is True
        assert result.attempts == 2  # needed repair

    def test_unfixable_json_fails(self):
        result = LLMResponseValidator.validate_with_repair(
            "this is not json at all and cannot be repaired", WorkItemHierarchy
        )
        assert result.success is False
