"""Service layer for structured work-item generation and enhancement."""

from __future__ import annotations

from app.providers.llm_provider import LLMProvider
from app.schemas.work_items import WorkItem


class WorkItemService:
    """Orchestrates LLM-powered work-item generation and enhancement."""

    def __init__(self, llm_provider: LLMProvider | None = None) -> None:
        self._llm = llm_provider or LLMProvider()

    async def generate(
        self, prompt: str, model: str = "gpt-4o-mini"
    ) -> list[WorkItem]:
        """Generate a hierarchy of work items from a user prompt."""
        return await self._llm.generate_work_items(prompt, model)

    async def enhance_prompt(
        self, prompt: str, model: str = "gpt-4o-mini"
    ) -> str:
        """Return an enhanced, more technically precise prompt."""
        return await self._llm.enhance_prompt(prompt, model)

    async def enhance_work_item(
        self, item: WorkItem, model: str = "gpt-4o-mini"
    ) -> WorkItem:
        """Return an enhanced version of a single work item."""
        return await self._llm.enhance_work_item(item, model)
