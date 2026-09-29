"""Change handler - responds to changes with selective replanning."""

from __future__ import annotations

import uuid
from typing import Any
from dataclasses import dataclass
from datetime import datetime
from copy import deepcopy

from src.models.change_event import ChangeEvent, ChangeEventType
from src.models.trailer import TrailerPlan, TrailerValidation, ValidationStatus
from src.models.story_map import StoryMap
from src.models.spoiler import SpoilerFact
from src.models.rule import Rule
from src.models.capability import CapabilityReport
from src.change_handler.dependency_graph import DependencyGraph
from src.generator import TrailerGenerator
from src.verifier import VerifierOrchestrator
from src.repair_engine import RepairEngine
from src.observability import DecisionLogger


@dataclass
class ChangeResult:
    """Result of change handling."""
    updated_trailers: list[TrailerPlan]
    changelog: list[dict]
    human_approvals_required: list[str]


class ChangeHandler:
    """Handles change events with selective replanning."""

    def __init__(
        self,
        generator: TrailerGenerator,
        verifier: VerifierOrchestrator,
        repair_engine: RepairEngine,
        decision_logger: DecisionLogger,
    ):
        self.generator = generator
        self.verifier = verifier
        self.repair_engine = repair_engine
        self.decision_logger = decision_logger
        self.dependency_graph = DependencyGraph()

    def initialize_graph(
        self,
        story_map: StoryMap,
        spoiler_facts: list[SpoilerFact],
        rules: list[Rule],
        trailers: list[TrailerPlan],
    ) -> None:
        """Initialize dependency graph from current state."""
        self.dependency_graph.build_from_pipeline(story_map, spoiler_facts, rules, trailers)

    def handle_change(
        self,
        event: ChangeEvent,
        trailers: list[TrailerPlan],
        story_map: StoryMap,
        spoiler_facts: list[SpoilerFact],
        rules: list[Rule],
        capability_report: CapabilityReport,
        dialogue_map: dict[str, str] | None = None,
        dialect_map: dict[str, str] | None = None,
    ) -> ChangeResult:
        """Handle a change event with selective replanning."""
        changelog = []
        human_approvals = []
        
        # 1. Update dependency graph based on event
        self._update_graph_for_event(event, story_map, spoiler_facts, rules)
        
        # 2. Identify affected segments and trailers
        affected_segments = set()
        affected_trailers = set()
        
        # Try multiple prefixes for entity_id lookup
        prefix_variants = [
            lambda x: x,
            lambda x: f"music:{x}",
            lambda x: f"scene:{x}",
            lambda x: f"entity:{x}",
            lambda x: f"rule:{x}",
            lambda x: f"spoiler:{x}",
        ]
        
        for entity_id in event.affected_entity_ids:
            for variant_fn in prefix_variants:
                variant_id = variant_fn(entity_id)
                # For asset expiration, we need to go UPSTREAM (find segments that use this asset)
                if event.event_type == ChangeEventType.ASSET_EXPIRED:
                    # Get upstream nodes (segments that reference this asset)
                    upstream_nodes = self.dependency_graph.get_upstream(variant_id)
                    affected_segments.update([n for n in upstream_nodes if n.startswith("segment:") or n.startswith("seg_")])
                    affected_trailers.update([n for n in upstream_nodes if n.startswith("trailer:")])
                else:
                    # For other changes, go downstream
                    segments = self.dependency_graph.get_affected_segments(variant_id)
                    trailers_affected = self.dependency_graph.get_affected_trailers(variant_id)
                    affected_segments.update(segments)
                    affected_trailers.update(trailers_affected)
        
        changelog.append({
            "event_id": event.event_id,
            "event_type": event.event_type.value,
            "affected_entities": event.affected_entity_ids,
            "affected_segments": list(affected_segments),
            "affected_trailers": list(affected_trailers),
            "timestamp": datetime.now().isoformat(),
        })
        
        # 3. For each affected trailer, selectively revise
        updated_trailers = []
        for trailer in trailers:
            if f"trailer:{trailer.trailer_id}" in affected_trailers:
                revised = self._revise_trailer(
                    trailer, affected_segments, event, story_map, spoiler_facts, rules, 
                    capability_report, dialogue_map, dialect_map
                )
                updated_trailers.append(revised)
                
                # Log revision
                changelog.append({
                    "trailer_id": trailer.trailer_id,
                    "revised": revised != trailer,
                    "segments_revised": [
                        s.segment_id for s in revised.segments 
                        if s.risk_flags and "revised" in s.risk_flags
                    ],
                })
            else:
                updated_trailers.append(trailer)
        
        # 4. Re-verify affected trailers
        for trailer in updated_trailers:
            if f"trailer:{trailer.trailer_id}" in affected_trailers:
                result = self.verifier.verify(
                    trailer, story_map, spoiler_facts, rules,
                    capability_report, dialogue_map, dialect_map
                )
                trailer.validation = result.validation
                
                if trailer.validation.status == ValidationStatus.FAIL:
                    repair_result = self.repair_engine.repair(
                        trailer, story_map, spoiler_facts, rules,
                        capability_report, dialogue_map, dialect_map
                    )
                    trailer = repair_result.trailer
                    changelog.append({
                        "trailer_id": trailer.trailer_id,
                        "repaired": repair_result.repaired,
                        "repair_iterations": repair_result.iterations,
                        "final_status": trailer.validation.status.value,
                    })
                    
                    if trailer.validation.status == ValidationStatus.REJECTED:
                        human_approvals.append(f"trailer:{trailer.trailer_id}:rejected_after_repair")
        
        return ChangeResult(
            updated_trailers=updated_trailers,
            changelog=changelog,
            human_approvals_required=human_approvals,
        )

    def _update_graph_for_event(
        self,
        event: ChangeEvent,
        story_map: StoryMap,
        spoiler_facts: list[SpoilerFact],
        rules: list[Rule],
    ) -> None:
        """Update dependency graph based on change event."""
        # Add new nodes for new entities
        for entity_id in event.affected_entity_ids:
            # Try different prefixes for graph lookup
            possible_ids = [
                entity_id,
                f"music:{entity_id}",
                f"scene:{entity_id}",
                f"entity:{entity_id}",
                f"rule:{entity_id}",
                f"spoiler:{entity_id}",
            ]
            
            for pid in possible_ids:
                if pid not in self.dependency_graph.nodes:
                    # Determine type from prefix or event
                    if pid.startswith("rule:") or event.event_type in (ChangeEventType.RULE_ADDED, ChangeEventType.RULE_MODIFIED):
                        self.dependency_graph.add_node(pid, "rule", {})
                    elif pid.startswith("spoiler:") or event.event_type == ChangeEventType.RULE_ADDED:
                        self.dependency_graph.add_node(pid, "spoiler_fact", {})
                    elif pid.startswith("music:"):
                        self.dependency_graph.add_node(pid, "music", {})
                    elif pid.startswith("scene:"):
                        self.dependency_graph.add_node(pid, "scene", {})
                    elif pid.startswith("entity:"):
                        self.dependency_graph.add_node(pid, "entity", {})

    def _revise_trailer(
        self,
        trailer: TrailerPlan,
        affected_segments: set[str],
        event: ChangeEvent,
        story_map: StoryMap,
        spoiler_facts: list[SpoilerFact],
        rules: list[Rule],
        capability_report: CapabilityReport,
        dialogue_map: dict[str, str] | None,
        dialect_map: dict[str, str] | None,
    ) -> TrailerPlan:
        """Revise only affected segments in a trailer."""
        revised = deepcopy(trailer)
        revised_segments = []
        
        for segment in revised.segments:
            if segment.segment_id in affected_segments or f"segment:{segment.segment_id}" in affected_segments:
                # Regenerate this segment
                new_segment = self._regenerate_segment(
                    segment, event, story_map, spoiler_facts, rules, capability_report
                )
                if new_segment:
                    new_segment.risk_flags.append("revised")
                    revised_segments.append(new_segment)
                    self.decision_logger.log(
                        component="change_handler",
                        decision_type="replace_segment",
                        description=f"Revised segment {segment.segment_id} due to {event.event_type.value}",
                        evidence=[f"event:{event.event_id}", f"old_segment:{segment.segment_id}"],
                        confidence=0.8,
                    )
                else:
                    # Could not regenerate - mark for removal
                    self.decision_logger.log(
                        component="change_handler",
                        decision_type="remove_segment",
                        description=f"Could not revise segment {segment.segment_id}, marking for removal",
                        evidence=[f"event:{event.event_id}"],
                        confidence=0.5,
                    )
            else:
                revised_segments.append(segment)
        
        revised.segments = revised_segments
        revised.duration_seconds = sum(s.duration_ms for s in revised_segments) / 1000.0
        return revised

    def _regenerate_segment(
        self,
        segment: "Segment",
        event: ChangeEvent,
        story_map: StoryMap,
        spoiler_facts: list[SpoilerFact],
        rules: list[Rule],
        capability_report: CapabilityReport,
    ) -> "Segment | None":
        """Regenerate a single segment based on change type."""
        from src.models.segment import Segment, TransitionType
        
        # Find alternative scene
        used_scenes = {s.video for s in [segment]}  # Simplified
        
        # Get eligible scenes based on change type
        if event.event_type == ChangeEventType.ASSET_EXPIRED:
            # Music expired - try to keep same scene but change audio
            expired_asset = event.affected_entity_ids[0] if event.affected_entity_ids else None
            if segment.audio == expired_asset or segment.audio == f"music:{expired_asset}":
                # Create new segment with same scene but different audio
                return Segment(
                    segment_id=f"{segment.segment_id}_revised_{uuid.uuid4().hex[:6]}",
                    sequence_order=segment.sequence_order,
                    source_in=segment.source_in,
                    source_out=segment.source_out,
                    video=segment.video,
                    audio="dialogue",  # Fallback to dialogue
                    subtitle=segment.subtitle,
                    text_card=segment.text_card,
                    voice_over=segment.voice_over,
                    transition=segment.transition,
                    reason=f"Revised due to {event.event_type.value} (asset {expired_asset} expired): {segment.reason}",
                    evidence=segment.evidence + [f"change_event:{event.event_id}"],
                    risk_flags=["revised"],
                    duration_ms=segment.duration_ms,
                )
            # If segment doesn't use the expired asset, look for alternative scene
            eligible = [
                s for s in story_map.scenes 
                if s.scene_id not in used_scenes and s.is_characterised
                and (expired_asset is None or expired_asset not in s.entities)
            ]
        elif event.event_type == ChangeEventType.RULE_ADDED:
            # New rule - find scene that complies
            new_rule_id = event.affected_entity_ids[0] if event.affected_entity_ids else None
            # Simplified: just pick first unused scene
            eligible = [s for s in story_map.scenes if s.scene_id not in used_scenes and s.is_characterised]
        else:
            eligible = [s for s in story_map.scenes if s.scene_id not in used_scenes and s.is_characterised]
        
        if not eligible:
            return None
        
        new_scene = eligible[0]
        
        return Segment(
            segment_id=f"{segment.segment_id}_revised_{uuid.uuid4().hex[:6]}",
            sequence_order=segment.sequence_order,
            source_in=new_scene.timecode_in,
            source_out=new_scene.timecode_out,
            video=new_scene.scene_id,
            audio="dialogue",  # Simplified
            subtitle=segment.subtitle,
            text_card=segment.text_card,
            voice_over=segment.voice_over,
            transition=segment.transition,
            reason=f"Revised due to {event.event_type.value}: {segment.reason}",
            evidence=segment.evidence + [f"change_event:{event.event_id}"],
            risk_flags=["revised"],
            duration_ms=new_scene.duration_ms,
        )