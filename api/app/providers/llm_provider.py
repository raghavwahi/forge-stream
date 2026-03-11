"""LLM provider abstraction for structured work-item generation."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import JsonOutputParser
from langchain_openai import ChatOpenAI

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
from app.schemas.work_items import WorkItem, WorkItemHierarchy


class LLMProvider:
    """Abstraction over LLM calls for work-item generation."""

    def _build_chat_model(
        self, model: str, temperature: float = 0.2, max_tokens: int = 4096
    ) -> ChatOpenAI:
        """Create a ChatOpenAI instance."""
        return ChatOpenAI(
            model=model, temperature=temperature, max_tokens=max_tokens
        )

    async def generate_work_items(
        self, prompt: str, model: str = "gpt-4o-mini"
    ) -> list[WorkItem]:
        """Generate a structured work-item hierarchy from a prompt."""
        template = GENERATE_WORK_ITEMS_PROMPT
        llm = self._build_chat_model(
            model,
            temperature=template.temperature,
            max_tokens=template.max_tokens,
        )
        parser = JsonOutputParser(pydantic_object=WorkItemHierarchy)

        user_message = template.format_user(
            prompt=prompt,
            schema=WORK_ITEM_HIERARCHY_SCHEMA,
            example=WORK_ITEM_HIERARCHY_EXAMPLE,
        )

        messages = [
            SystemMessage(content=template.system),
            HumanMessage(content=user_message),
        ]

        response = await llm.ainvoke(messages)
        parsed: dict[str, Any] = parser.invoke(response)
        hierarchy = WorkItemHierarchy.model_validate(parsed)
        return hierarchy.items

    async def enhance_prompt(
        self, prompt: str, model: str = "gpt-4o-mini"
    ) -> str:
        """Rewrite a rough prompt into a detailed, technical one."""
        template = ENHANCE_PROMPT_TEMPLATE
        llm = self._build_chat_model(
            model,
            temperature=template.temperature,
            max_tokens=template.max_tokens,
        )
        user_message = template.format_user(prompt=prompt)
        messages = [
            SystemMessage(content=template.system),
            HumanMessage(content=user_message),
        ]
        response = await llm.ainvoke(messages)
        return str(response.content).strip()

    async def enhance_work_item(
        self, item: WorkItem, model: str = "gpt-4o-mini"
    ) -> WorkItem:
        """Inject more technical detail into an existing work item."""
        template = ENHANCE_WORK_ITEM_TEMPLATE
        llm = self._build_chat_model(
            model,
            temperature=template.temperature,
            max_tokens=template.max_tokens,
        )
        parser = JsonOutputParser(pydantic_object=WorkItem)
        user_message = template.format_user(
            item_json=item.model_dump_json(),
            schema=WORK_ITEM_SCHEMA,
        )
        messages = [
            SystemMessage(content=template.system),
            HumanMessage(content=user_message),
        ]
        response = await llm.ainvoke(messages)
        parsed: dict[str, Any] = parser.invoke(response)
        return WorkItem.model_validate(parsed)
