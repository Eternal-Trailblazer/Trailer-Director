"""Rule DSL models."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field
from enum import Enum


class RuleScope(str, Enum):
    SCENE = "scene"
    ACTOR = "actor"
    VOICE = "voice"
    MUSIC_TRACK = "music_track"
    TERRITORY = "territory"
    AUDIENCE = "audience"
    TIME_WINDOW = "time_window"
    DIALOGUE = "dialogue"
    VISUAL_CONTENT = "visual_content"


class RuleEffect(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE = "require"
    LIMIT = "limit"


class RuleCondition(BaseModel):
    field: str  # e.g. "actor_id", "territory", "audience_age_min"
    operator: str  # eq, ne, gt, lt, gte, lte, in, not_in, contains, before, after
    value: Any


class Rule(BaseModel):
    rule_id: str
    source_contract_id: str | None = None
    source_policy_id: str | None = None
    source_span: str  # exact text from input
    scope: RuleScope
    effect: RuleEffect
    conditions: list[RuleCondition] = Field(default_factory=list)
    confidence: float = 1.0
    is_ambiguous: bool = False
    human_approved: bool = False