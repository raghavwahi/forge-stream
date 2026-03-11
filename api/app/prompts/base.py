"""Base prompt template dataclass with variable interpolation and validation."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PromptTemplate:
    """Immutable prompt template with variable interpolation and validation."""

    system: str
    user_template: str
    required_vars: list[str] = field(default_factory=list)
    output_format: str = "json"  # "json" | "text"
    max_tokens: int = 4096
    temperature: float = 0.7

    def format_user(self, **kwargs) -> str:
        """Format user message with variables, raising ValueError for missing vars."""
        missing = [v for v in self.required_vars if v not in kwargs]
        if missing:
            raise ValueError(f"Missing required template variables: {missing}")
        return self.user_template.format(**kwargs)

    def validate_vars(self, **kwargs) -> None:
        """Validate all required vars are present."""
        missing = [v for v in self.required_vars if v not in kwargs]
        if missing:
            raise ValueError(f"Missing required template variables: {missing}")
