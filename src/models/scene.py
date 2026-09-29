"""Scene, Entity, and Relationship models."""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field
from enum import Enum

from src.models.timecode import Timecode


class EntityType(str, Enum):
    CHARACTER = "character"
    LOCATION = "location"
    OBJECT = "object"
    MUSIC_TRACK = "music_track"


class Relationship(BaseModel):
    target_entity_id: str
    relationship_type: str  # e.g. "sibling", "rival", "mentor"
    revealed_in_scene: Optional[str] = None
    is_spoiler: bool = False


class Entity(BaseModel):
    entity_id: str
    entity_type: EntityType
    name: str
    aliases: list[str] = Field(default_factory=list)
    first_appearance_scene: Optional[str] = None
    relationships: list[Relationship] = Field(default_factory=list)


class Scene(BaseModel):
    scene_id: str
    timecode_in: Timecode
    timecode_out: Timecode
    duration_ms: int
    description: Optional[str] = None
    entities: list[str] = Field(default_factory=list)  # entity_ids
    content_tags: list[str] = Field(default_factory=list)  # e.g. ["violence", "romance"]
    emotional_tone: Optional[str] = None
    dialogue_ids: list[str] = Field(default_factory=list)
    is_characterised: bool = True
    trust_level: str = "untrusted"  # "authoritative" | "untrusted" | "semi-trusted"

    def contains_timecode(self, tc: Timecode) -> bool:
        return self.timecode_in <= tc < self.timecode_out

    def validate_bounds(self, source_in: Timecode, source_out: Timecode) -> bool:
        return (self.timecode_in <= source_in < source_out <= self.timecode_out)