"""Story Map models."""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class StoryEvent(BaseModel):
    event_id: str
    description: str
    scene_id: str
    involved_entities: list[str]
    event_type: str  # "setup", "conflict", "escalation", "climax", "resolution", "twist"
    normalised_position: float  # 0.0 to 1.0 in episode timeline
    causes: list[str] = Field(default_factory=list)  # event_ids that cause this
    caused_by: list[str] = Field(default_factory=list)  # event_ids caused by this


class EmotionalBeat(BaseModel):
    scene_id: str
    emotion: str
    intensity: float  # 0.0 to 1.0


class StoryMap(BaseModel):
    episode_id: str
    scenes: list["Scene"]
    entities: list["Entity"]
    major_events: list[StoryEvent]
    emotional_arc: list[EmotionalBeat]
    total_duration_ms: int
    metadata: dict = Field(default_factory=dict)


# Forward references
from src.models.scene import Scene, Entity
StoryMap.model_rebuild()