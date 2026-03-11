"""Base prompt template dataclass with variable interpolation and validation."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PromptTemplate:
    """Prompt template with variable interpolation and validation."""

    system: str
    user_template: str
    required_vars: list[str] = field(default_factory=list)
    system_vars: list[str] = field(default_factory=list)
    output_format: str = "json"  # "json" | "text"
    max_tokens: int = 4096
    temperature: float = 0.7

    def _validate_vars(self, required: list[str], provided: dict) -> None:
        """Raise ValueError if any required variable is missing from provided."""
        missing = [v for v in required if v not in provided]
        if missing:
            raise ValueError(f"Missing required template variables: {missing}")

    def format_user(self, **kwargs) -> str:
        """Format user message with variables, raising ValueError for missing required vars."""
        self._validate_vars(self.required_vars, kwargs)
        return self.user_template.format(**kwargs)

    def format_system(self, **kwargs) -> str:
        """Format system message, raising ValueError for missing required vars."""
        self._validate_vars(self.system_vars, kwargs)
        return self.system.format(**kwargs)
