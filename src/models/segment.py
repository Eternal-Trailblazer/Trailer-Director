"""Segment and Transition models."""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field
from enum import Enum

from src.models.timecode import Timecode


class TransitionType(str, Enum):
    CUT = "cut"
    FADE = "fade"
    DISSOLVE = "dissolve"


class Segment(BaseModel):
    segment_id: str
    sequence_order: int
    source_in: Timecode
    source_out: Timecode
    video: str  # scene_id
    audio: str  # "dialogue" | "music" | "dialogue_and_music" | "silence" | track_id
    subtitle: Optional[str] = None
    text_card: Optional[str] = None
    voice_over: Optional[str] = None
    transition: Optional[TransitionType] = None
    reason: str
    evidence: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    duration_ms: int

    @property
    def duration_seconds(self) -> float:
        return self.duration_ms / 1000.0