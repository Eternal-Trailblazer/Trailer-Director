"""Decision Log model."""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class DecisionLogEntry(BaseModel):
    entry_id: str
    timestamp: datetime = Field(default_factory=datetime.now)
    component: str  # which module made this decision
    decision_type: str  # "include_segment", "exclude_segment", "replace_segment", "escalate", etc.
    description: str
    evidence: list[str] = Field(default_factory=list)
    alternatives_considered: list[str] = Field(default_factory=list)
    confidence: float = 1.0
    cost_incurred: float = 0.0
    human_approval_required: bool = False