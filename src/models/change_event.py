"""Change Event models."""

from __future__ import annotations

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum


class ChangeEventType(str, Enum):
    RULE_ADDED = "rule_added"
    RULE_REMOVED = "rule_removed"
    RULE_MODIFIED = "rule_modified"
    ASSET_EXPIRED = "asset_expired"
    ASSET_UNAVAILABLE = "asset_unavailable"
    AUDIENCE_DATA_REVISED = "audience_data_revised"
    MODEL_UNAVAILABLE = "model_unavailable"
    MARKETING_DIRECTIVE = "marketing_directive"
    CONTENT_REVISED = "content_revised"


class ChangeEvent(BaseModel):
    event_id: str
    event_type: ChangeEventType
    timestamp: datetime = Field(default_factory=datetime.now)
    description: str
    affected_entity_ids: list[str] = Field(default_factory=list)
    old_value: Optional[dict] = None
    new_value: Optional[dict] = None
    source: str
    requires_replan: bool = True