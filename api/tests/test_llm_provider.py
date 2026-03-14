"""Tests for LLMProvider and work_items prompt template constants."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

from app.prompts.schemas import (
    WORK_ITEM_HIERARCHY_EXAMPLE,
    WORK_ITEM_HIERARCHY_SCHEMA,
    WORK_ITEM_SCHEMA,
)
from app.prompts.work_items import (
    ENHANCE_PROMPT_TEMPLATE,
    ENHANCE_WORK_ITEM_TEMPLATE,
    GENERATE_WORK_ITEMS_PROMPT,
)
from app.providers.llm_provider import LLMProvider
from app.schemas.work_items import WorkItem, WorkItemType


# ── Work-item template constants ──────────────────────────────────────────────


class TestGenerateWorkItemsPrompt:
    def test_temperature_is_low_for_structured_output(self):
        assert GENERATE_WORK_ITEMS_PROMPT.temperature == 0.3

    def test_max_tokens(self):
        assert GENERATE_WORK_ITEMS_PROMPT.max_tokens == 4096

    def test_output_format_is_json(self):
        assert GENERATE_WORK_ITEMS_PROMPT.output_format == "json"

    def test_required_vars_contains_prompt(self):
        assert "prompt" in GENERATE_WORK_ITEMS_PROMPT.required_vars

    def test_system_vars_contains_schema_and_example(self):
        assert "schema" in GENERATE_WORK_ITEMS_PROMPT.system_vars
        assert "example" in GENERATE_WORK_ITEMS_PROMPT.system_vars

    def test_format_user_with_prompt(self):
        result = GENERATE_WORK_ITEMS_PROMPT.format_user(prompt="Build a login page")
        assert "Build a login page" in result

    def test_format_user_missing_prompt_raises(self):
        with pytest.raises(ValueError, match="Missing required template variables"):
            GENERATE_WORK_ITEMS_PROMPT.format_user()

    def test_format_system_replaces_placeholders(self):
        result = GENERATE_WORK_ITEMS_PROMPT.format_system(
            schema=WORK_ITEM_HIERARCHY_SCHEMA,
            example=WORK_ITEM_HIERARCHY_EXAMPLE,
        )
        assert "{schema}" not in result
        assert "{example}" not in result
        assert "WorkItemHierarchy" in result

    def test_format_system_missing_schema_raises(self):
        with pytest.raises(ValueError, match="Missing required template variables"):
            GENERATE_WORK_ITEMS_PROMPT.format_system(
                example=WORK_ITEM_HIERARCHY_EXAMPLE
            )


class TestEnhancePromptTemplate:
    def test_temperature(self):
        assert ENHANCE_PROMPT_TEMPLATE.temperature == 0.5

    def test_max_tokens(self):
        assert ENHANCE_PROMPT_TEMPLATE.max_tokens == 2048

    def test_output_format_is_text(self):
        assert ENHANCE_PROMPT_TEMPLATE.output_format == "text"

    def test_required_vars_contains_prompt(self):
        assert "prompt" in ENHANCE_PROMPT_TEMPLATE.required_vars

    def test_no_system_vars(self):
        assert ENHANCE_PROMPT_TEMPLATE.system_vars == []

    def test_format_user_with_prompt(self):
        result = ENHANCE_PROMPT_TEMPLATE.format_user(prompt="Add search feature")
        assert "Add search feature" in result

    def test_format_user_missing_prompt_raises(self):
        with pytest.raises(ValueError, match="Missing required template variables"):
            ENHANCE_PROMPT_TEMPLATE.format_user()

    def test_format_system_returns_system_unchanged(self):
        result = ENHANCE_PROMPT_TEMPLATE.format_system()
        assert result == ENHANCE_PROMPT_TEMPLATE.system


class TestEnhanceWorkItemTemplate:
    def test_temperature_is_low_for_structured_output(self):
        assert ENHANCE_WORK_ITEM_TEMPLATE.temperature == 0.3

    def test_max_tokens(self):
        assert ENHANCE_WORK_ITEM_TEMPLATE.max_tokens == 2048

    def test_output_format_is_json(self):
        assert ENHANCE_WORK_ITEM_TEMPLATE.output_format == "json"

    def test_required_vars_contains_item_json(self):
        assert "item_json" in ENHANCE_WORK_ITEM_TEMPLATE.required_vars

    def test_system_vars_contains_schema(self):
        assert "schema" in ENHANCE_WORK_ITEM_TEMPLATE.system_vars

    def test_format_user_with_item_json(self):
        result = ENHANCE_WORK_ITEM_TEMPLATE.format_user(item_json='{"type":"task"}')
        assert '{"type":"task"}' in result

    def test_format_user_missing_item_json_raises(self):
        with pytest.raises(ValueError, match="Missing required template variables"):
            ENHANCE_WORK_ITEM_TEMPLATE.format_user()

    def test_format_system_replaces_schema_placeholder(self):
        result = ENHANCE_WORK_ITEM_TEMPLATE.format_system(schema=WORK_ITEM_SCHEMA)
        assert "{schema}" not in result
        assert "WorkItem" in result

    def test_format_system_missing_schema_raises(self):
        with pytest.raises(ValueError, match="Missing required template variables"):
            ENHANCE_WORK_ITEM_TEMPLATE.format_system()


# ── LLMProvider ───────────────────────────────────────────────────────────────


@pytest.fixture()
def provider():
    return LLMProvider()


@pytest.fixture()
def mock_llm():
    """Return a mock ChatOpenAI-like object with a patched ainvoke."""
    llm = MagicMock()
    llm.ainvoke = AsyncMock()
    return llm


class TestLLMProviderGenerateWorkItems:
    @pytest.mark.asyncio
    async def test_returns_work_item_list(self, provider, mock_llm):
        hierarchy_json = (
            '{"items": [{"type": "epic", "title": "Auth System",'
            ' "description": "Full auth implementation", "labels": ["auth"],'
            ' "children": []}]}'
        )
        mock_llm.ainvoke.return_value = AIMessage(content=hierarchy_json)

        with patch.object(provider, "_build_chat_model", return_value=mock_llm):
            result = await provider.generate_work_items("Build auth system")

        assert len(result) == 1
        assert result[0].type == WorkItemType.EPIC
        assert result[0].title == "Auth System"

    @pytest.mark.asyncio
    async def test_passes_correct_temperature_and_tokens(self, provider, mock_llm):
        hierarchy_json = '{"items": []}'
        mock_llm.ainvoke.return_value = AIMessage(content=hierarchy_json)

        with patch.object(
            provider, "_build_chat_model", return_value=mock_llm
        ) as mock_build:
            await provider.generate_work_items("some prompt")

        mock_build.assert_called_once_with(
            "gpt-4o-mini",
            temperature=GENERATE_WORK_ITEMS_PROMPT.temperature,
            max_tokens=GENERATE_WORK_ITEMS_PROMPT.max_tokens,
        )

    @pytest.mark.asyncio
    async def test_system_message_contains_schema(self, provider, mock_llm):
        hierarchy_json = '{"items": []}'
        captured_messages = []

        async def capture_ainvoke(messages):
            captured_messages.extend(messages)
            return AIMessage(content=hierarchy_json)

        mock_llm.ainvoke = capture_ainvoke

        with patch.object(provider, "_build_chat_model", return_value=mock_llm):
            await provider.generate_work_items("some prompt")

        system_content = captured_messages[0].content
        assert "WorkItemHierarchy" in system_content
        assert "{schema}" not in system_content
        assert "{example}" not in system_content


class TestLLMProviderEnhancePrompt:
    @pytest.mark.asyncio
    async def test_returns_stripped_string(self, provider, mock_llm):
        mock_llm.ainvoke.return_value = MagicMock(
            content="  Enhanced prompt text.  "
        )

        with patch.object(provider, "_build_chat_model", return_value=mock_llm):
            result = await provider.enhance_prompt("raw prompt")

        assert result == "Enhanced prompt text."

    @pytest.mark.asyncio
    async def test_passes_correct_temperature_and_tokens(self, provider, mock_llm):
        mock_llm.ainvoke.return_value = MagicMock(content="Enhanced.")

        with patch.object(
            provider, "_build_chat_model", return_value=mock_llm
        ) as mock_build:
            await provider.enhance_prompt("raw prompt")

        mock_build.assert_called_once_with(
            "gpt-4o-mini",
            temperature=ENHANCE_PROMPT_TEMPLATE.temperature,
            max_tokens=ENHANCE_PROMPT_TEMPLATE.max_tokens,
        )

    @pytest.mark.asyncio
    async def test_system_message_has_no_unformatted_placeholders(
        self, provider, mock_llm
    ):
        captured_messages = []

        async def capture_ainvoke(messages):
            captured_messages.extend(messages)
            return MagicMock(content="Enhanced.")

        mock_llm.ainvoke = capture_ainvoke

        with patch.object(provider, "_build_chat_model", return_value=mock_llm):
            await provider.enhance_prompt("raw prompt")

        system_content = captured_messages[0].content
        # System prompt for enhance_prompt has no {var} placeholders to fill
        assert "{schema}" not in system_content
        assert "{example}" not in system_content


class TestLLMProviderEnhanceWorkItem:
    @pytest.mark.asyncio
    async def test_returns_enhanced_work_item(self, provider, mock_llm):
        enhanced_json = (
            '{"type": "story", "title": "Login page",'
            ' "description": "Implement secure login with rate limiting",'
            ' "labels": ["auth", "backend"], "children": []}'
        )
        mock_llm.ainvoke.return_value = AIMessage(content=enhanced_json)
        item = WorkItem(type=WorkItemType.STORY, title="Login page")

        with patch.object(provider, "_build_chat_model", return_value=mock_llm):
            result = await provider.enhance_work_item(item)

        assert result.type == WorkItemType.STORY
        assert result.title == "Login page"
        assert "rate limiting" in result.description

    @pytest.mark.asyncio
    async def test_passes_correct_temperature_and_tokens(self, provider, mock_llm):
        enhanced_json = (
            '{"type": "task", "title": "T", "description": "desc",'
            ' "labels": [], "children": []}'
        )
        mock_llm.ainvoke.return_value = AIMessage(content=enhanced_json)
        item = WorkItem(type=WorkItemType.TASK, title="T")

        with patch.object(
            provider, "_build_chat_model", return_value=mock_llm
        ) as mock_build:
            await provider.enhance_work_item(item)

        mock_build.assert_called_once_with(
            "gpt-4o-mini",
            temperature=ENHANCE_WORK_ITEM_TEMPLATE.temperature,
            max_tokens=ENHANCE_WORK_ITEM_TEMPLATE.max_tokens,
        )

    @pytest.mark.asyncio
    async def test_system_message_contains_schema(self, provider, mock_llm):
        enhanced_json = (
            '{"type": "task", "title": "T", "description": "desc",'
            ' "labels": [], "children": []}'
        )
        captured_messages = []

        async def capture_ainvoke(messages):
            captured_messages.extend(messages)
            return AIMessage(content=enhanced_json)

        mock_llm.ainvoke = capture_ainvoke
        item = WorkItem(type=WorkItemType.TASK, title="T")

        with patch.object(provider, "_build_chat_model", return_value=mock_llm):
            await provider.enhance_work_item(item)

        system_content = captured_messages[0].content
        assert "WorkItem" in system_content
        assert "{schema}" not in system_content
