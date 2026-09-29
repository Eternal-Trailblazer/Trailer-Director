"""Capability Report model."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CapabilityReport(BaseModel):
    has_video: bool
    has_audio: bool
    has_scene_descriptions: bool
    has_source_dialogue: bool
    dialect_tracks: list[str] = Field(default_factory=list)
    has_policies: bool
    has_contracts: bool
    has_audience_profiles: bool
    has_historic_data: bool
    has_cost_sheet: bool
    warnings: list[str] = Field(default_factory=list)
    degraded_checks: list[str] = Field(default_factory=list)