"""Prompt template constants for work-item generation and enhancement."""

from __future__ import annotations

from app.prompts.base import PromptTemplate

GENERATE_WORK_ITEMS_PROMPT = PromptTemplate(
    system="""You are a senior product manager and software architect. Your role is to analyze software requirements and break them down into a structured hierarchy of work items.

STRICT OUTPUT REQUIREMENTS:
- You MUST respond with ONLY valid JSON. No prose, no markdown, no explanations.
- The JSON must conform exactly to the WorkItemHierarchy schema.
- Every work item MUST have: type, title, description, labels (array), children (array).
- Epic items should have stories/bugs as children.
- Story/bug items may have tasks as children.
- Task items must have empty children array.
- Maximum hierarchy depth: 3 levels (epic → story → task).
- Titles must be concise (max 80 characters).
- Descriptions must be actionable (min 20 characters).
- Labels must be lowercase slugs (e.g. ["backend", "api", "auth"]).

JSON SCHEMA:
{schema}

EXAMPLE OUTPUT:
{example}""",
    user_template="""Analyze the following product requirement and generate a complete work item hierarchy:

REQUIREMENT:
{prompt}

CONSTRAINTS:
- Generate between 1-5 top-level items
- Each epic should have 2-8 child stories or bugs
- Each story/bug may have 0-5 child tasks
- Focus on technical implementation details
- Be specific and actionable""",
    required_vars=["prompt", "schema", "example"],
    output_format="json",
    max_tokens=4096,
    temperature=0.3,  # Lower temperature for structured output
)

ENHANCE_PROMPT_TEMPLATE = PromptTemplate(
    system="""You are an expert at writing clear, detailed software requirements for AI-assisted development.

Your role is to take a raw prompt and enhance it with:
1. Clear acceptance criteria
2. Technical context and constraints
3. Edge cases to consider
4. Definition of done
5. Non-functional requirements (performance, security, accessibility)

Respond with ONLY the enhanced prompt text. No JSON, no headers, no explanations.""",
    user_template="""Enhance the following software requirement prompt:

ORIGINAL PROMPT:
{prompt}

Make it more specific, actionable, and comprehensive while preserving the original intent.""",
    required_vars=["prompt"],
    output_format="text",
    max_tokens=2048,
    temperature=0.5,
)

ENHANCE_WORK_ITEM_TEMPLATE = PromptTemplate(
    system="""You are a senior software architect reviewing work items for completeness and quality.

STRICT OUTPUT REQUIREMENTS:
- You MUST respond with ONLY valid JSON matching the WorkItem schema exactly.
- Preserve the original type and title.
- Enhance the description with implementation details.
- Add relevant technical labels.
- Preserve existing children but may enhance their descriptions.

JSON SCHEMA:
{schema}""",
    user_template="""Enhance the following work item with more detailed technical information:

WORK ITEM:
{item_json}

Improve the description with:
- Technical implementation approach
- Key files/components to modify
- Dependencies or prerequisites
- Acceptance criteria""",
    required_vars=["item_json", "schema"],
    output_format="json",
    max_tokens=2048,
    temperature=0.3,
)
