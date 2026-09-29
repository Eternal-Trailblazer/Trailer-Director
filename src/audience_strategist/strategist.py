"""Audience strategist - plans audience promises before clip selection."""

from __future__ import annotations

import uuid
from typing import Any
from dataclasses import dataclass

from src.models.story_map import StoryMap
from src.models.audience import AudienceDefinition, AudiencePromise
from src.models.spoiler import SpoilerFact
from src.models.capability import CapabilityReport
from src.bias_auditor import BiasAuditor, BiasReport
from src.providers.base import ModelProvider
from src.quarantine import QuarantineGate


@dataclass
class StrategistResult:
    """Result of audience strategy planning."""
    promises: list[AudiencePromise]
    bias_report: BiasReport
    warnings: list[str]


class AudienceStrategist:
    """Plans audience promises before any clip selection."""

    def __init__(
        self, 
        model_provider: ModelProvider, 
        quarantine: QuarantineGate,
        bias_auditor: BiasAuditor
    ):
        self.model_provider = model_provider
        self.quarantine = quarantine
        self.bias_auditor = bias_auditor

    def plan_promises(
        self,
        audiences: list[AudienceDefinition],
        story_map: StoryMap,
        spoiler_facts: list[SpoilerFact],
        capability_report: CapabilityReport,
    ) -> StrategistResult:
        """Generate audience promises for all audiences."""
        warnings = []
        
        # 1. Run bias auditor on audience profiles
        bias_report = self.bias_auditor.audit(audiences, [])
        if bias_report.has_flags:
            warnings.extend(bias_report.flags_summary)
        
        # 2. Generate promise for each audience
        promises = []
        for audience in audiences:
            promise = self._generate_promise(audience, story_map, spoiler_facts, capability_report)
            promises.append(promise)
        
        # 3. Check promise differentiation
        diff_warnings = self._check_promise_differentiation(promises, story_map)
        warnings.extend(diff_warnings)
        
        return StrategistResult(
            promises=promises,
            bias_report=bias_report,
            warnings=warnings,
        )

    def _generate_promise(
        self,
        audience: AudienceDefinition,
        story_map: StoryMap,
        spoiler_facts: list[SpoilerFact],
        capability_report: CapabilityReport,
    ) -> AudiencePromise:
        """Generate a single audience promise."""
        # Build context from story map
        context = self._build_story_context(story_map, spoiler_facts)
        
        # Get audience-specific constraints
        avoid_content = self._get_avoid_content(audience, capability_report)
        
        prompt = f"""Create an audience promise for this trailer audience.

AUDIENCE: {audience.name} ({audience.audience_id})
GOAL: {audience.goal}
SPECIAL CARE: {', '.join(audience.special_care)}
RATING POLICIES: {', '.join(audience.rating_policy_ids)}
TERRITORIES: {', '.join(audience.territories)}
LANGUAGES: {', '.join(audience.languages)}

EPISODE CONTEXT:
{context}

CONTENT TO AVOID: {', '.join(avoid_content) if avoid_content else 'None'}

The promise must:
1. Be grounded in actual episode events (cite event_ids from context)
2. NOT imply any spoilers (avoid late-episode reveals)
3. Match the audience's stated goal and special care requirements
4. Define a clear narrative arc: setup -> tension -> hook
5. Specify intended emotions and tone

Output as JSON matching AudiencePromise schema."""

        try:
            response = self.model_provider.complete(
                messages=[{"role": "user", "content": prompt}],
                budget_tag=f"audience_promise_{audience.audience_id}"
            )
            return self._parse_promise_response(response.text, audience.audience_id)
        except Exception as e:
            # Fallback promise
            return self._fallback_promise(audience, story_map)

    def _build_story_context(self, story_map: StoryMap, spoiler_facts: list[SpoilerFact]) -> str:
        """Build story context for promise generation."""
        parts = []
        
        # Major events (non-spoiler)
        safe_events = []
        spoiler_scenes = set()
        for fact in spoiler_facts:
            spoiler_scenes.update(fact.involved_scenes)
        
        for event in story_map.major_events:
            if event.scene_id not in spoiler_scenes and event.normalised_position < 0.7:
                safe_events.append(f"  {event.event_id} ({event.event_type}): {event.description} [scene: {event.scene_id}]")
        
        parts.append("SAFE EVENTS (can reference in promise):")
        parts.extend(safe_events[:10])  # Limit
        
        # Emotional arc highlights
        parts.append("\nEMOTIONAL BEATS:")
        for beat in story_map.emotional_arc[:10]:
            parts.append(f"  {beat.scene_id}: {beat.emotion} (intensity: {beat.intensity})")
        
        # Key entities
        parts.append("\nKEY ENTITIES:")
        for entity in story_map.entities[:10]:
            rels = [f"{r.relationship_type}->{r.target_entity_id}" for r in entity.relationships[:2]]
            parts.append(f"  {entity.entity_id} ({entity.entity_type.value}): {entity.name} - {', '.join(rels) if rels else 'no relationships'}")
        
        return "\n".join(parts)

    def _get_avoid_content(self, audience: AudienceDefinition, capability_report: CapabilityReport) -> list[str]:
        """Determine content to avoid based on audience and policies."""
        avoid = []
        
        # Add special care items
        avoid.extend(audience.special_care)
        
        # Add rating policy restrictions (would come from compiled rules)
        # For now, add generic restrictions based on audience_id
        if "family" in audience.audience_id.lower():
            avoid.extend(["violence", "blood", "frightening", "suggestive", "profanity"])
        if "young_adult" in audience.audience_id.lower():
            avoid.extend(["misleading_intensity", "central_twist"])
        
        return avoid

    def _parse_promise_response(self, response: str, audience_id: str) -> AudiencePromise:
        """Parse LLM promise response."""
        import json
        try:
            data = json.loads(response)
            return AudiencePromise(
                audience_id=audience_id,
                promise_text=data.get("promise_text", ""),
                intended_emotions=data.get("intended_emotions", []),
                narrative_arc=data.get("narrative_arc", ["setup", "tension", "hook"]),
                tone=data.get("tone", ""),
                avoid=data.get("avoid", []),
                evidence=data.get("evidence", []),
            )
        except Exception:
            return self._fallback_promise_obj(audience_id)

    def _fallback_promise(self, audience: AudienceDefinition, story_map: StoryMap) -> AudiencePromise:
        """Generate fallback promise when LLM fails."""
        return AudiencePromise(
            audience_id=audience.audience_id,
            promise_text=f"A {audience.goal.lower()} trailer for {audience.name}",
            intended_emotions=["engagement", "curiosity"],
            narrative_arc=["setup", "tension", "hook"],
            tone="authentic",
            avoid=audience.special_care,
            evidence=[],
        )

    def _fallback_promise_obj(self, audience_id: str) -> AudiencePromise:
        return AudiencePromise(
            audience_id=audience_id,
            promise_text="A compelling trailer",
            intended_emotions=["engagement"],
            narrative_arc=["setup", "tension", "hook"],
            tone="authentic",
            avoid=[],
            evidence=[],
        )

    def _check_promise_differentiation(
        self, 
        promises: list[AudiencePromise], 
        story_map: StoryMap
    ) -> list[str]:
        """Check that promises are sufficiently differentiated."""
        warnings = []
        
        if len(promises) < 2:
            return warnings
        
        # Simple text similarity check
        for i, p1 in enumerate(promises):
            for j, p2 in enumerate(promises[i+1:], i+1):
                # Compare evidence sets
                ev1 = set(p1.evidence)
                ev2 = set(p2.evidence)
                if ev1 and ev2:
                    intersection = len(ev1 & ev2)
                    union = len(ev1 | ev2)
                    similarity = intersection / union if union > 0 else 0
                    if similarity > 0.7:
                        warnings.append(
                            f"High promise similarity between {p1.audience_id} and {p2.audience_id}: "
                            f"{similarity:.2f} (evidence overlap)"
                        )
                
                # Compare narrative arcs
                if p1.narrative_arc == p2.narrative_arc:
                    warnings.append(
                        f"Identical narrative arc for {p1.audience_id} and {p2.audience_id}"
                    )
        
        return warnings