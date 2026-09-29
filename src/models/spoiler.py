"""Spoiler Fact model."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SpoilerFact(BaseModel):
    fact_id: str
    fact_type: str  # "causal_reveal", "identity_reveal", "relationship_reveal", "outcome", "twist", "human_tagged"
    description: str
    involved_entities: list[str]
    involved_scenes: list[str]
    reveal_boundary: float  # normalised position threshold (0.0-1.0)
    evidence: list[str]  # story-map element IDs
    confidence: float