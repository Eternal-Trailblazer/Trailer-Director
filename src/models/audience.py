"""Audience Definition and Promise models."""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class AudienceDefinition(BaseModel):
    model_config = ConfigDict(extra='allow')
    
    audience_id: str
    name: str
    description: str
    goal: str
    special_care: list[str] = Field(default_factory=list)
    rating_policy_ids: list[str] = Field(default_factory=list)
    age_range: Optional[tuple[int, int]] = None
    territories: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    preferences: dict = Field(default_factory=dict)
    engagement_patterns: dict = Field(default_factory=dict)


class AudiencePromise(BaseModel):
    audience_id: str
    promise_text: str
    intended_emotions: list[str] = Field(default_factory=list)
    narrative_arc: list[str] = Field(default_factory=list)  # ["setup", "tension", "hook"]
    tone: str
    avoid: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)  # story-map element IDs