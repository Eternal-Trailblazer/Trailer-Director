"""Human Approval Registry model."""

from __future__ import annotations

from pydantic import BaseModel, Field
from enum import Enum


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ApprovalUrgency(str, Enum):
    BLOCKING = "blocking"
    ADVISORY = "advisory"


class HumanApprovalEntry(BaseModel):
    entry_id: str
    decision_type: str  # "ambiguous_rule", "cultural_sensitivity", "creative_override", "bias_concern"
    description: str
    affected_trailer_ids: list[str] = Field(default_factory=list)
    affected_segment_ids: list[str] = Field(default_factory=list)
    urgency: ApprovalUrgency = ApprovalUrgency.ADVISORY
    status: ApprovalStatus = ApprovalStatus.PENDING