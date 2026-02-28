"""LLM provider abstraction for structured work-item generation."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import JsonOutputParser
from langchain_openai import ChatOpenAI

from app.schemas.work_items import WorkItem, WorkItemHierarchy

SYSTEM_PROMPT_GENERATE = """\
You are an expert software project planner. Given a user prompt, produce a \
structured JSON hierarchy of GitHub work items.

Rules:
- Return ONLY valid JSON (no markdown fences, no commentary).
- The root JSON must be an object with a single key "items" containing an array.
- Each item has: "type" (epic | story | bug | task), "title", "description", \
"labels" (array of strings), and "children" (array of nested items).
- Epics should have children (stories, bugs, or tasks).
- Stories and bugs may have child tasks.
- Use clear, actionable titles and concise descriptions with acceptance criteria.
"""

SYSTEM_PROMPT_ENHANCE_PROMPT = """\
You are an expert prompt engineer for software project planning.
Given a rough user prompt, rewrite it into a detailed, technically precise \
prompt that will produce better structured work items.
Return ONLY the enhanced prompt text, nothing else.
"""

SYSTEM_PROMPT_ENHANCE_ITEM = """\
You are an expert software architect. Given a work item as JSON, enhance it \
by adding more technical detail to its description: acceptance criteria, \
implementation hints, edge cases, and any missing children.

Rules:
- Return ONLY valid JSON representing the enhanced work item.
- Keep the same schema: type, title, description, labels, children.
- Preserve the original title; enrich description and children.
"""


class LLMProvider:
    """Abstraction over LLM calls for work-item generation."""

    def _build_chat_model(
        self, model: str, temperature: float = 0.2
    ) -> ChatOpenAI:
        """Create a ChatOpenAI instance."""
        return ChatOpenAI(model=model, temperature=temperature)

    async def generate_work_items(
        self, prompt: str, model: str = "gpt-4o-mini"
    ) -> list[WorkItem]:
        """Generate a structured work-item hierarchy from a prompt."""
        llm = self._build_chat_model(model)
        parser = JsonOutputParser(pydantic_object=WorkItemHierarchy)

        messages = [
            SystemMessage(content=SYSTEM_PROMPT_GENERATE),
            HumanMessage(content=prompt),
        ]

        response = await llm.ainvoke(messages)
        parsed: dict[str, Any] = parser.invoke(response)
        hierarchy = WorkItemHierarchy.model_validate(parsed)
        return hierarchy.items

    async def enhance_prompt(
        self, prompt: str, model: str = "gpt-4o-mini"
    ) -> str:
        """Rewrite a rough prompt into a detailed, technical one."""
        llm = self._build_chat_model(model)
        messages = [
            SystemMessage(content=SYSTEM_PROMPT_ENHANCE_PROMPT),
            HumanMessage(content=prompt),
        ]
        response = await llm.ainvoke(messages)
        return str(response.content).strip()

    async def enhance_work_item(
        self, item: WorkItem, model: str = "gpt-4o-mini"
    ) -> WorkItem:
        """Inject more technical detail into an existing work item."""
        llm = self._build_chat_model(model)
        parser = JsonOutputParser(pydantic_object=WorkItem)
        messages = [
            SystemMessage(content=SYSTEM_PROMPT_ENHANCE_ITEM),
            HumanMessage(content=item.model_dump_json()),
        ]
        response = await llm.ainvoke(messages)
        parsed: dict[str, Any] = parser.invoke(response)
        return WorkItem.model_validate(parsed)
