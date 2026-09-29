"""Spoiler detection engine."""

from __future__ import annotations

import uuid
from typing import Optional
from dataclasses import dataclass

from src.models.story_map import StoryMap, StoryEvent, Scene
from src.models.spoiler import SpoilerFact
from src.models.segment import Segment
from src.providers.base import ModelProvider


@dataclass
class SpoilerVerdict:
    """Result of a spoiler check."""
    verdict: str  # "PASS", "WARN", "FAIL", "UNVERIFIED"
    fact_id: Optional[str] = None
    check_type: str = ""  # "direct_reveal", "ordering_reveal", "inferential_reveal"
    segment_id: Optional[str] = None
    evidence: list[str] = None
    details: str = ""

    def __post_init__(self):
        if self.evidence is None:
            self.evidence = []


class SpoilerEngine:
    """Detects spoilers using multiple detection strategies."""

    def __init__(self, model_provider: ModelProvider, late_episode_threshold: float = 0.7, confidence_threshold: float = 0.6):
        self.model_provider = model_provider
        self.late_episode_threshold = late_episode_threshold
        self.confidence_threshold = confidence_threshold

    def build_spoiler_map(self, story_map: StoryMap) -> list[SpoilerFact]:
        """Build spoiler facts from story map."""
        facts = []
        
        # 1. Late-episode causal reveals
        facts.extend(self._detect_causal_reveals(story_map))
        
        # 2. Identity/relationship reveals
        facts.extend(self._detect_identity_reveals(story_map))
        
        # 3. Outcome events
        facts.extend(self._detect_outcome_events(story_map))
        
        # 4. Twist markers
        facts.extend(self._detect_twist_markers(story_map))
        
        # 5. Human-tagged facts (from metadata)
        facts.extend(self._detect_human_tagged(story_map))

        return facts

    def _detect_causal_reveals(self, story_map: StoryMap) -> list[SpoilerFact]:
        """Find events in late episode that are caused by earlier events."""
        facts = []
        late_events = [e for e in story_map.major_events if e.normalised_position >= self.late_episode_threshold]
        
        for event in late_events:
            if event.causes:  # Has causal predecessors
                fact = SpoilerFact(
                    fact_id=f"spoiler-causal-{uuid.uuid4().hex[:8]}",
                    fact_type="causal_reveal",
                    description=f"Late event '{event.description}' reveals causal chain from earlier events",
                    involved_entities=event.involved_entities,
                    involved_scenes=[event.scene_id],
                    reveal_boundary=self.late_episode_threshold,
                    evidence=[event.event_id] + event.causes,
                    confidence=0.8,
                )
                facts.append(fact)
        return facts

    def _detect_identity_reveals(self, story_map: StoryMap) -> list[SpoilerFact]:
        """Find identity/relationship reveals."""
        facts = []
        for entity in story_map.entities:
            for rel in entity.relationships:
                if rel.revealed_in_scene and rel.is_spoiler:
                    # Find the scene
                    scene = next((s for s in story_map.scenes if s.scene_id == rel.revealed_in_scene), None)
                    if scene:
                        position = scene.timecode_in.normalised_ms / story_map.total_duration_ms if story_map.total_duration_ms > 0 else 0
                        if position >= self.late_episode_threshold:
                            fact = SpoilerFact(
                                fact_id=f"spoiler-identity-{uuid.uuid4().hex[:8]}",
                                fact_type="identity_reveal",
                                description=f"Relationship '{rel.relationship_type}' between {entity.entity_id} and {rel.target_entity_id} revealed late",
                                involved_entities=[entity.entity_id, rel.target_entity_id],
                                involved_scenes=[rel.revealed_in_scene],
                                reveal_boundary=self.late_episode_threshold,
                                evidence=[entity.entity_id, rel.target_entity_id, rel.revealed_in_scene],
                                confidence=0.85,
                            )
                            facts.append(fact)
        return facts

    def _detect_outcome_events(self, story_map: StoryMap) -> list[SpoilerFact]:
        """Find final-act resolution events."""
        facts = []
        outcome_types = {"resolution", "climax"}
        for event in story_map.major_events:
            if event.event_type in outcome_types and event.normalised_position >= self.late_episode_threshold:
                fact = SpoilerFact(
                    fact_id=f"spoiler-outcome-{uuid.uuid4().hex[:8]}",
                    fact_type="outcome",
                    description=f"Outcome event: {event.description}",
                    involved_entities=event.involved_entities,
                    involved_scenes=[event.scene_id],
                    reveal_boundary=self.late_episode_threshold,
                    evidence=[event.event_id],
                    confidence=0.9,
                )
                facts.append(fact)
        return facts

    def _detect_twist_markers(self, story_map: StoryMap) -> list[SpoilerFact]:
        """Find events marked as twists."""
        facts = []
        for event in story_map.major_events:
            if event.event_type == "twist" or "twist" in event.description.lower() or "reveal" in event.description.lower():
                if event.normalised_position >= self.late_episode_threshold:
                    fact = SpoilerFact(
                        fact_id=f"spoiler-twist-{uuid.uuid4().hex[:8]}",
                        fact_type="twist",
                        description=f"Twist event: {event.description}",
                        involved_entities=event.involved_entities,
                        involved_scenes=[event.scene_id],
                        reveal_boundary=self.late_episode_threshold,
                        evidence=[event.event_id],
                        confidence=0.95,
                    )
                    facts.append(fact)
        return facts

    def _detect_human_tagged(self, story_map: StoryMap) -> list[SpoilerFact]:
        """Find human-tagged spoiler facts from metadata."""
        facts = []
        human_facts = story_map.metadata.get("spoiler_facts", [])
        for hf in human_facts:
            fact = SpoilerFact(
                fact_id=hf.get("fact_id", f"spoiler-human-{uuid.uuid4().hex[:8]}"),
                fact_type="human_tagged",
                description=hf.get("description", "Human-tagged spoiler"),
                involved_entities=hf.get("involved_entities", []),
                involved_scenes=hf.get("involved_scenes", []),
                reveal_boundary=hf.get("reveal_boundary", self.late_episode_threshold),
                evidence=hf.get("evidence", []),
                confidence=hf.get("confidence", 0.9),
            )
            facts.append(fact)
        return facts

    def check_segment(self, segment: Segment, story_map: StoryMap, spoiler_facts: list[SpoilerFact]) -> list[SpoilerVerdict]:
        """Check a segment for direct spoiler reveals."""
        verdicts = []
        
        # Direct reveal check
        for fact in spoiler_facts:
            if segment.video in fact.involved_scenes:
                verdicts.append(SpoilerVerdict(
                    verdict="FAIL",
                    fact_id=fact.fact_id,
                    check_type="direct_reveal",
                    segment_id=segment.segment_id,
                    evidence=[f"segment.video ({segment.video}) in fact.involved_scenes ({fact.involved_scenes})"],
                    details=f"Segment directly contains spoiler scene for {fact.fact_type}: {fact.description}"
                ))

        return verdicts

    def check_ordering(self, segments: list[Segment], story_map: StoryMap, spoiler_facts: list[SpoilerFact]) -> list[SpoilerVerdict]:
        """Check if segment ordering reveals causal chains."""
        verdicts = []
        
        # Build scene position map
        scene_positions = {}
        for scene in story_map.scenes:
            pos = scene.timecode_in.normalised_ms / story_map.total_duration_ms if story_map.total_duration_ms > 0 else 0
            scene_positions[scene.scene_id] = pos

        # Check for ordering that reveals late events early
        for fact in spoiler_facts:
            if fact.fact_type in ("causal_reveal", "twist"):
                # Find if any segment shows a cause before the effect
                cause_scenes = set()
                for evidence_id in fact.evidence:
                    event = next((e for e in story_map.major_events if e.event_id == evidence_id), None)
                    if event:
                        cause_scenes.add(event.scene_id)
                
                # Check if cause scenes appear before effect scenes in trailer
                cause_positions = []
                effect_positions = []
                for i, seg in enumerate(segments):
                    if seg.video in cause_scenes:
                        cause_positions.append(i)
                    if seg.video in fact.involved_scenes:
                        effect_positions.append(i)
                
                if cause_positions and effect_positions:
                    min_cause = min(cause_positions)
                    min_effect = min(effect_positions)
                    if min_cause < min_effect:
                        # Check if this ordering reveals the causal chain prematurely
                        verdicts.append(SpoilerVerdict(
                            verdict="WARN",
                            fact_id=fact.fact_id,
                            check_type="ordering_reveal",
                            segment_id=segments[min_effect].segment_id,
                            evidence=[
                                f"Cause scene {segments[min_cause].video} at position {min_cause}",
                                f"Effect scene {segments[min_effect].video} at position {min_effect}"
                            ],
                            details=f"Trailer ordering may reveal causal chain for {fact.description}"
                        ))

        return verdicts

    async def check_inferential(self, segments: list[Segment], story_map: StoryMap, spoiler_facts: list[SpoilerFact], dialogue_map: dict[str, str]) -> list[SpoilerVerdict]:
        """Use LLM to check for inferential spoiler reveals."""
        verdicts = []
        
        # Combine all dialogue from segments
        segment_dialogue = {}
        for seg in segments:
            if seg.video in dialogue_map:
                segment_dialogue[seg.segment_id] = dialogue_map[seg.video]
        
        if not segment_dialogue:
            return verdicts

        # For each spoiler fact, check if dialogue allows inference
        for fact in spoiler_facts:
            if fact.confidence < self.confidence_threshold:
                continue
                
            prompt = self._build_inferential_prompt(fact, segment_dialogue)
            
            try:
                response = await self.model_provider.complete_async(
                    messages=[{"role": "user", "content": prompt}],
                    budget_tag=f"spoiler_inferential_{fact.fact_id}"
                )
                
                # Parse response
                if "SPOILER_DETECTED" in response.text:
                    verdicts.append(SpoilerVerdict(
                        verdict="FAIL",
                        fact_id=fact.fact_id,
                        check_type="inferential_reveal",
                        segment_id=list(segment_dialogue.keys())[0],
                        evidence=[f"LLM detected inferential reveal: {response.text[:200]}"],
                        details=f"Combined dialogue allows deduction of {fact.fact_type}: {fact.description}"
                    ))
                else:
                    verdicts.append(SpoilerVerdict(
                        verdict="PASS",
                        fact_id=fact.fact_id,
                        check_type="inferential_reveal",
                        segment_id=list(segment_dialogue.keys())[0],
                        evidence=[f"LLM verdict: {response.text[:200]}"],
                        details="No inferential spoiler detected"
                    ))
            except Exception as e:
                verdicts.append(SpoilerVerdict(
                    verdict="UNVERIFIED",
                    fact_id=fact.fact_id,
                    check_type="inferential_reveal",
                    segment_id=list(segment_dialogue.keys())[0],
                    evidence=[f"LLM check failed: {e}"],
                    details="Inferential check could not complete"
                ))

        return verdicts

    def _build_inferential_prompt(self, fact: SpoilerFact, segment_dialogue: dict[str, str]) -> str:
        dialogue_text = "\n".join([f"[{seg_id}]: {text}" for seg_id, text in segment_dialogue.items()])
        return f"""Does the following trailer dialogue, taken together, allow a viewer to deduce this protected story fact?

PROTECTED FACT: {fact.description}
FACT TYPE: {fact.fact_type}
INVOLVED ENTITIES: {', '.join(fact.involved_entities)}

TRAILER DIALOGUE:
{dialogue_text}

Answer with exactly one of:
- SPOILER_DETECTED: [explanation with segment IDs]
- NO_SPOILER: [explanation]

The fact is considered revealed if a viewer who hasn't seen the episode could deduce it from the trailer dialogue alone."""