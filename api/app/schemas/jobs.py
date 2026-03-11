"""Job schemas for the async worker queue."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class JobType(str, Enum):
    """Supported async job types."""

    GENERATE_ITEMS = "generate_items"
    CREATE_ISSUES = "create_issues"
    ENHANCE_ITEMS = "enhance_items"


class JobStatus(str, Enum):
    """Lifecycle status of a job."""

    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


@dataclass
class Job:
    """Represents a single unit of async work.

    Attributes
    ----------
    type:
        The kind of operation to perform.
    payload:
        Arbitrary data passed to the handler.
    status:
        Current lifecycle status (default: PENDING).
    id:
        Unique identifier, auto-generated if not supplied.
    result:
        Output from a successful handler invocation.
    error:
        Error message from a failed handler invocation.
    """

    type: JobType
    payload: Dict[str, Any]
    status: JobStatus = JobStatus.PENDING
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    def model_dump(self) -> Dict[str, Any]:
        """Return a JSON-serialisable dict representation."""
        return {
            "id": self.id,
            "type": self.type.value,
            "payload": self.payload,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
        }

    def model_dump_json(self) -> str:
        """Serialise the job to a JSON string."""
        return json.dumps(self.model_dump())
