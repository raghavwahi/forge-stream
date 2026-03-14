"""Tests for the PromptTemplate dataclass."""

import pytest

from app.prompts.base import PromptTemplate


class TestPromptTemplateFormatUser:
    def test_successful_formatting(self):
        tmpl = PromptTemplate(
            system="System message",
            user_template="Hello, {name}! You are {age} years old.",
            required_vars=["name", "age"],
        )
        result = tmpl.format_user(name="Alice", age=30)
        assert result == "Hello, Alice! You are 30 years old."

    def test_missing_required_var_raises_value_error(self):
        tmpl = PromptTemplate(
            system="System message",
            user_template="Hello, {name}! You are {age} years old.",
            required_vars=["name", "age"],
        )
        with pytest.raises(ValueError, match="Missing required template variables"):
            tmpl.format_user(name="Alice")

    def test_multiple_missing_vars_reported(self):
        tmpl = PromptTemplate(
            system="System message",
            user_template="Hello, {name}! Task: {task}. Ref: {ref}.",
            required_vars=["name", "task", "ref"],
        )
        with pytest.raises(ValueError) as exc_info:
            tmpl.format_user(name="Alice")
        error_msg = str(exc_info.value)
        assert "task" in error_msg
        assert "ref" in error_msg

    def test_no_required_vars_succeeds(self):
        tmpl = PromptTemplate(
            system="System message",
            user_template="Static user message.",
            required_vars=[],
        )
        result = tmpl.format_user()
        assert result == "Static user message."

    def test_extra_kwargs_are_ignored(self):
        tmpl = PromptTemplate(
            system="System message",
            user_template="Hello, {name}!",
            required_vars=["name"],
        )
        result = tmpl.format_user(name="Bob", extra="ignored")
        assert result == "Hello, Bob!"


class TestPromptTemplateFormatSystem:
    def test_successful_system_formatting(self):
        tmpl = PromptTemplate(
            system="Schema: {schema}. Example: {example}.",
            user_template="User message.",
            system_vars=["schema", "example"],
        )
        result = tmpl.format_system(schema="my-schema", example="my-example")
        assert result == "Schema: my-schema. Example: my-example."

    def test_missing_system_var_raises_value_error(self):
        tmpl = PromptTemplate(
            system="Schema: {schema}.",
            user_template="User message.",
            system_vars=["schema"],
        )
        with pytest.raises(ValueError, match="Missing required template variables"):
            tmpl.format_system()

    def test_no_system_vars_returns_system_as_is(self):
        tmpl = PromptTemplate(
            system="Static system message.",
            user_template="User message.",
            system_vars=[],
        )
        result = tmpl.format_system()
        assert result == "Static system message."


class TestPromptTemplateDefaults:
    def test_default_values(self):
        tmpl = PromptTemplate(system="sys", user_template="user")
        assert tmpl.max_tokens == 4096
        assert tmpl.temperature == 0.7
        assert tmpl.output_format == "json"
        assert tmpl.required_vars == []
        assert tmpl.system_vars == []
