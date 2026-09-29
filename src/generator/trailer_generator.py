"""Trailer generator - selects and orders moments maintaining mini-story arc."""

from __future__ import annotations

import uuid
from typing import Any
from dataclasses import dataclass

from src.models.story_map import StoryMap, Scene
from src.models.spoiler import SpoilerFact
from src.models.rule import Rule
from src.models.audience import AudiencePromise
from src.models.segment import Segment, TransitionType
from src.models.trailer import TrailerPlan
from src.models.capability import CapabilityReport
from src.rule_compiler import RuleEvaluator
from src.providers.base import ModelProvider
from src.observability import DecisionLogger


@dataclass
class GeneratorResult:
    """Result of trailer generation."""
    trailer_plan: TrailerPlan
    warnings: list[str]


class TrailerGenerator:
    """Generates trailer plans following audience promise and arc structure."""

    def __init__(
        self,
        model_provider: ModelProvider,
        rule_evaluator: RuleEvaluator,
        decision_logger: DecisionLogger,
        min_duration_seconds: float = 20,
        max_duration_seconds: float = 60,
        min_segments: int = 3,
        max_segments: int = 12,
        diversity_threshold: float = 0.4,
    ):
        self.model_provider = model_provider
        self.rule_evaluator = rule_evaluator
        self.decision_logger = decision_logger
        self.min_duration_seconds = min_duration_seconds
        self.max_duration_seconds = max_duration_seconds
        self.min_segments = min_segments
        self.max_segments = max_segments
        self.diversity_threshold = diversity_threshold

    def generate(
        self,
        audience_promise: AudiencePromise,
        story_map: StoryMap,
        spoiler_facts: list[SpoilerFact],
        rules: list[Rule],
        capability_report: CapabilityReport,
        existing_trailers: list[TrailerPlan] | None = None,
    ) -> GeneratorResult:
        """Generate a trailer plan for the given audience."""
        warnings = []
        existing_trailers = existing_trailers or []
        
        # 1. Score scenes for relevance to promise
        scene_scores = self._score_scenes(audience_promise, story_map, spoiler_facts, rules, capability_report)
        
        # 2. Filter by rules and spoilers
        eligible_scenes = self._filter_eligible_scenes(scene_scores, rules, spoiler_facts, story_map, capability_report)
        
        if len(eligible_scenes) < self.min_segments:
            warnings.append(f"Only {len(eligible_scenes)} eligible scenes, below minimum {self.min_segments}")
        
        # 3. Select scenes following arc template
        selected_scenes = self._select_arc_scenes(eligible_scenes, audience_promise, story_map)
        
        # 4. Apply diversity constraint against existing trailers
        selected_scenes = self._apply_diversity(selected_scenes, existing_trailers, story_map, warnings)
        
        # 5. Create segments with timecodes and audio/subtitle selections
        segments = self._create_segments(selected_scenes, audience_promise, story_map, rules, capability_report)
        
        # 6. Validate duration
        total_duration = sum(s.duration_ms for s in segments) / 1000.0
        if total_duration > self.max_duration_seconds:
            # Trim segments
            segments = self._trim_to_duration(segments, self.max_duration_seconds)
            total_duration = sum(s.duration_ms for s in segments) / 1000.0
            warnings.append(f"Trailer trimmed to {total_duration:.1f}s")
        elif total_duration < self.min_duration_seconds:
            warnings.append(f"Trailer duration {total_duration:.1f}s below minimum {self.min_duration_seconds}s")
        
        # 7. Create trailer plan
        trailer_plan = TrailerPlan(
            trailer_id=f"trailer_{audience_promise.audience_id}_{uuid.uuid4().hex[:8]}",
            audience=audience_promise.audience_id,
            audience_promise=audience_promise,
            duration_seconds=total_duration,
            segments=segments,
            estimated_cost=0.0,  # Will be filled by budget controller
        )
        
        return GeneratorResult(trailer_plan=trailer_plan, warnings=warnings)

    def _score_scenes(
        self,
        promise: AudiencePromise,
        story_map: StoryMap,
        spoiler_facts: list[SpoilerFact],
        rules: list[Rule],
        capability_report: CapabilityReport,
    ) -> dict[str, float]:
        """Score each scene for relevance to audience promise."""
        scores = {}
        spoiler_scenes = set()
        for fact in spoiler_facts:
            spoiler_scenes.update(fact.involved_scenes)
        
        for scene in story_map.scenes:
            score = 0.0
            
            # Base score from promise evidence
            if scene.scene_id in promise.evidence:
                score += 10.0
            
            # Score from emotional arc alignment
            beat = next((b for b in story_map.emotional_arc if b.scene_id == scene.scene_id), None)
            if beat:
                if "tension" in promise.narrative_arc and beat.emotion in ("tension", "anticipation", "fear"):
                    score += beat.intensity * 5
                if "hook" in promise.narrative_arc and beat.emotion in ("surprise", "anticipation"):
                    score += beat.intensity * 5
                if "setup" in promise.narrative_arc and beat.emotion in ("neutral", "joy", "sadness"):
                    score += beat.intensity * 3
            
            # Score from event alignment
            event = next((e for e in story_map.major_events if e.scene_id == scene.scene_id), None)
            if event:
                if event.event_type in ("setup", "conflict") and "setup" in promise.narrative_arc:
                    score += 3
                if event.event_type in ("escalation", "climax") and "tension" in promise.narrative_arc:
                    score += 4
                if event.event_type == "twist" and "hook" in promise.narrative_arc:
                    score += 5
            
            # Penalize spoiler scenes heavily
            if scene.scene_id in spoiler_scenes:
                score -= 100.0
            
            # Penalize uncharacterised scenes
            if not scene.is_characterised:
                score -= 5.0
            
            # Check rules - if any DENY rule applies, score = -inf
            deny = False
            for rule in rules:
                if rule.effect.value == "deny" and rule.scope.value == "scene":
                    for cond in rule.conditions:
                        if cond.field == "scene_id" and cond.operator == "eq" and cond.value == scene.scene_id:
                            deny = True
                            break
                if deny:
                    break
            if deny:
                score = float('-inf')
            
            scores[scene.scene_id] = score
        
        return scores

    def _filter_eligible_scenes(
        self,
        scene_scores: dict[str, float],
        rules: list[Rule],
        spoiler_facts: list[SpoilerFact],
        story_map: StoryMap,
        capability_report: CapabilityReport,
    ) -> list[Scene]:
        """Filter scenes by rules and spoilers."""
        eligible = []
        spoiler_scenes = set()
        for fact in spoiler_facts:
            spoiler_scenes.update(fact.involved_scenes)
        
        for scene in story_map.scenes:
            if scene.scene_id in spoiler_scenes:
                continue
            if scene_scores.get(scene.scene_id, 0) == float('-inf'):
                continue
            if not scene.is_characterised and capability_report.has_scene_descriptions:
                continue  # Skip uncharacterised if we have descriptions
            eligible.append(scene)
        
        # Sort by score descending
        eligible.sort(key=lambda s: scene_scores.get(s.scene_id, 0), reverse=True)
        return eligible

    def _select_arc_scenes(
        self,
        eligible_scenes: list[Scene],
        promise: AudiencePromise,
        story_map: StoryMap,
    ) -> list[Scene]:
        """Select scenes following arc template: setup -> tension -> hook."""
        if not eligible_scenes:
            return []
        
        # Arc template: 1-2 setup, 2-3 tension, 1 hook
        arc_structure = {
            "setup": 2,
            "tension": 3,
            "hook": 1,
        }
        
        selected = []
        used_scenes = set()
        
        for arc_phase, count in arc_structure.items():
            # Find scenes matching this phase
            phase_scenes = []
            for scene in eligible_scenes:
                if scene.scene_id in used_scenes:
                    continue
                
                beat = next((b for b in story_map.emotional_arc if b.scene_id == scene.scene_id), None)
                event = next((e for e in story_map.major_events if e.scene_id == scene.scene_id), None)
                
                matches = False
                if arc_phase == "setup":
                    matches = (beat and beat.emotion in ("neutral", "joy", "sadness", "anticipation")) or \
                              (event and event.event_type in ("setup", "conflict"))
                elif arc_phase == "tension":
                    matches = (beat and beat.emotion in ("tension", "fear", "anger", "anticipation")) or \
                              (event and event.event_type in ("conflict", "escalation", "climax"))
                elif arc_phase == "hook":
                    matches = (beat and beat.emotion in ("surprise", "anticipation")) or \
                              (event and event.event_type in ("climax", "twist"))
                
                if matches:
                    phase_scenes.append(scene)
            
            # Take top N
            for scene in phase_scenes[:count]:
                selected.append(scene)
                used_scenes.add(scene.scene_id)
        
        # If not enough scenes, fill from remaining eligible
        if len(selected) < self.min_segments:
            for scene in eligible_scenes:
                if scene.scene_id not in used_scenes and len(selected) < self.max_segments:
                    selected.append(scene)
                    used_scenes.add(scene.scene_id)
        
        # Limit to max_segments
        return selected[:self.max_segments]

    def _apply_diversity(
        self,
        selected_scenes: list[Scene],
        existing_trailers: list[TrailerPlan],
        story_map: StoryMap,
        warnings: list[str],
    ) -> list[Scene]:
        """Ensure diversity against existing trailers."""
        if not existing_trailers:
            return selected_scenes
        
        # Compute Jaccard distance for each existing trailer
        selected_ids = {s.scene_id for s in selected_scenes}
        
        for existing in existing_trailers:
            existing_ids = {s.video for s in existing.segments}
            if not existing_ids or not selected_ids:
                continue
            intersection = len(selected_ids & existing_ids)
            union = len(selected_ids | existing_ids)
            jaccard = intersection / union if union > 0 else 0
            
            if jaccard > (1 - self.diversity_threshold):
                warnings.append(
                    f"Low diversity (Jaccard={jaccard:.2f}) with trailer {existing.trailer_id}. "
                    f"Consider replacing scenes."
                )
                # Try to replace overlapping scenes
                overlapping = selected_ids & existing_ids
                non_overlapping = [s for s in selected_scenes if s.scene_id not in overlapping]
                # Would need additional eligible scenes to replace - simplified for now
        
        return selected_scenes

    def _create_segments(
        self,
        selected_scenes: list[Scene],
        promise: AudiencePromise,
        story_map: StoryMap,
        rules: list[Rule],
        capability_report: CapabilityReport,
    ) -> list[Segment]:
        """Create segments from selected scenes."""
        segments = []
        
        for i, scene in enumerate(selected_scenes):
            # Determine audio track
            audio = self._select_audio(scene, story_map, rules, capability_report)
            
            # Determine subtitle
            subtitle = self._select_subtitle(scene, promise, capability_report)
            
            # Create segment
            segment = Segment(
                segment_id=f"seg_{scene.scene_id}_{uuid.uuid4().hex[:6]}",
                sequence_order=i,
                source_in=scene.timecode_in,
                source_out=scene.timecode_out,
                video=scene.scene_id,
                audio=audio,
                subtitle=subtitle,
                text_card=None,
                voice_over=None,
                transition=TransitionType.CUT if i > 0 else None,
                reason=f"Selected for {promise.narrative_arc[min(i, len(promise.narrative_arc)-1)]} phase: {scene.description[:100] if scene.description else 'Key moment'}",
                evidence=[f"scene:{scene.scene_id}"] + promise.evidence,
                risk_flags=[],
                duration_ms=scene.duration_ms,
            )
            segments.append(segment)
            
            # Log decision
            self.decision_logger.log(
                component="trailer_generator",
                decision_type="include_segment",
                description=f"Included {scene.scene_id} as segment {i} ({promise.narrative_arc[min(i, len(promise.narrative_arc)-1)]})",
                evidence=[f"scene:{scene.scene_id}", f"promise:{promise.audience_id}"],
                confidence=0.8,
            )
        
        return segments

    def _select_audio(self, scene: Scene, story_map: StoryMap, rules: list[Rule], capability_report: CapabilityReport) -> str:
        """Select audio track for scene."""
        # Check for music tracks in scene
        music_entities = [e for e in scene.entities if e.startswith("music_")]
        if music_entities:
            # Check rights
            for music_id in music_entities:
                allowed = True
                for rule in rules:
                    if rule.scope.value == "music_track" and rule.effect.value == "deny":
                        for cond in rule.conditions:
                            if cond.field == "music_track" and cond.operator == "eq" and cond.value == music_id:
                                allowed = False
                                break
                if allowed:
                    return music_id
        
        # Default to dialogue
        if scene.dialogue_ids:
            return "dialogue"
        return "silence"

    def _select_subtitle(self, scene: Scene, promise: AudiencePromise, capability_report: CapabilityReport) -> str | None:
        """Select subtitle track for dialect audiences."""
        if "dialect" in promise.audience_id and capability_report.dialect_tracks:
            return capability_report.dialect_tracks[0]
        return None

    def _trim_to_duration(self, segments: list[Segment], max_duration: float) -> list[Segment]:
        """Trim segments to fit within max duration."""
        max_ms = int(max_duration * 1000)
        total = sum(s.duration_ms for s in segments)
        
        if total <= max_ms:
            return segments
        
        # Proportionally trim each segment
        ratio = max_ms / total
        trimmed = []
        for seg in segments:
            new_duration = int(seg.duration_ms * ratio)
            new_out_ms = seg.source_in.normalised_ms + new_duration
            # Create new timecode (simplified)
            from src.models.timecode import ms_to_timecode, TimecodeFormat
            new_out = ms_to_timecode(new_out_ms, TimecodeFormat.MILLISECONDS)
            
            trimmed.append(Segment(
                segment_id=seg.segment_id,
                sequence_order=seg.sequence_order,
                source_in=seg.source_in,
                source_out=new_out,
                video=seg.video,
                audio=seg.audio,
                subtitle=seg.subtitle,
                text_card=seg.text_card,
                voice_over=seg.voice_over,
                transition=seg.transition,
                reason=seg.reason,
                evidence=seg.evidence,
                risk_flags=seg.risk_flags,
                duration_ms=new_duration,
            ))
        
        return trimmed