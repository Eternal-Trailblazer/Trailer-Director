"""Repair engine - fixes failed trailers or rejects them."""

from __future__ import annotations

from typing import Any
from dataclasses import dataclass
from copy import deepcopy

from src.models.trailer import TrailerPlan, TrailerValidation, ValidationCheck, ValidationStatus
from src.models.story_map import StoryMap
from src.models.spoiler import SpoilerFact
from src.models.rule import Rule
from src.models.capability import CapabilityReport
from src.generator import TrailerGenerator
from src.verifier import VerifierOrchestrator
from src.observability import DecisionLogger


@dataclass
class RepairResult:
    """Result of repair attempt."""
    trailer: TrailerPlan
    repaired: bool
    iterations: int
    final_status: ValidationStatus
    repair_log: list[str]


class RepairEngine:
    """Repairs failed trailers by replacing problematic segments."""

    def __init__(
        self,
        generator: TrailerGenerator,
        verifier: VerifierOrchestrator,
        decision_logger: DecisionLogger,
        max_iterations: int = 3,
    ):
        self.generator = generator
        self.verifier = verifier
        self.decision_logger = decision_logger
        self.max_iterations = max_iterations

    def repair(
        self,
        trailer: TrailerPlan,
        story_map: StoryMap,
        spoiler_facts: list[SpoilerFact],
        rules: list[Rule],
        capability_report: CapabilityReport,
        dialogue_map: dict[str, str] | None = None,
        dialect_map: dict[str, str] | None = None,
    ) -> RepairResult:
        """Attempt to repair a failed trailer."""
        repair_log = []
        current_trailer = deepcopy(trailer)
        iterations = 0
        
        while iterations < self.max_iterations:
            # Verify current state
            result = self.verifier.verify(
                current_trailer, story_map, spoiler_facts, rules, 
                capability_report, dialogue_map, dialect_map
            )
            
            current_trailer.validation = result.validation
            
            if result.validation.status in (ValidationStatus.PASS, ValidationStatus.PASS_WITH_WARNINGS):
                repair_log.append(f"Iteration {iterations}: Trailer passes validation")
                return RepairResult(
                    trailer=current_trailer,
                    repaired=True,
                    iterations=iterations,
                    final_status=result.validation.status,
                    repair_log=repair_log,
                )
            
            # Find FAIL checks to repair
            fail_checks = [c for c in result.validation.checks if c.verdict == "FAIL"]
            if not fail_checks:
                repair_log.append(f"Iteration {iterations}: No FAIL checks to repair")
                break
            
            repair_log.append(f"Iteration {iterations}: Found {len(fail_checks)} FAIL checks")
            
            # Attempt to repair each failure
            repaired_any = False
            for check in fail_checks:
                repaired = self._repair_check(current_trailer, check, story_map, spoiler_facts, rules, capability_report)
                if repaired:
                    repaired_any = True
                    repair_log.append(f"  Repaired: {check.check_type} - {check.details}")
            
            if not repaired_any:
                repair_log.append(f"Iteration {iterations}: No repairs possible")
                break
            
            iterations += 1
        
        # Final verification
        final_result = self.verifier.verify(
            current_trailer, story_map, spoiler_facts, rules,
            capability_report, dialogue_map, dialect_map
        )
        current_trailer.validation = final_result.validation
        
        if final_result.validation.status == ValidationStatus.FAIL:
            current_trailer.validation.status = ValidationStatus.REJECTED
            repair_log.append("Trailer REJECTED after max repair iterations")
        
        return RepairResult(
            trailer=current_trailer,
            repaired=final_result.validation.status != ValidationStatus.REJECTED,
            iterations=iterations,
            final_status=current_trailer.validation.status,
            repair_log=repair_log,
        )

    def _repair_check(
        self,
        trailer: TrailerPlan,
        check: ValidationCheck,
        story_map: StoryMap,
        spoiler_facts: list[SpoilerFact],
        rules: list[Rule],
        capability_report: CapabilityReport,
    ) -> bool:
        """Attempt to repair a specific failed check."""
        check_type = check.check_type
        segment_id = None
        
        # Extract segment ID from check_id
        if "_" in check.check_id:
            parts = check.check_id.split("_")
            if len(parts) >= 2:
                segment_id = parts[-2] if parts[-1].startswith("spoiler") else parts[-1]
        
        if not segment_id:
            return False
        
        # Find the segment
        segment_idx = next((i for i, s in enumerate(trailer.segments) if s.segment_id == segment_id), None)
        if segment_idx is None:
            return False
        
        segment = trailer.segments[segment_idx]
        
        if check_type == "spoiler":
            return self._repair_spoiler(trailer, segment_idx, segment, story_map, spoiler_facts, rules, capability_report)
        elif check_type == "rights":
            return self._repair_rights(trailer, segment_idx, segment, story_map, rules, capability_report)
        elif check_type == "audience_safety":
            return self._repair_safety(trailer, segment_idx, segment, story_map, rules, capability_report)
        elif check_type == "source_accuracy":
            return self._repair_source_accuracy(trailer, segment_idx, segment, story_map)
        
        return False

    def _repair_spoiler(
        self,
        trailer: TrailerPlan,
        segment_idx: int,
        segment: "Segment",
        story_map: StoryMap,
        spoiler_facts: list[SpoilerFact],
        rules: list[Rule],
        capability_report: CapabilityReport,
    ) -> bool:
        """Replace spoiler scene with non-spoiler alternative."""
        # Find alternative scenes not in spoiler facts
        spoiler_scenes = set()
        for fact in spoiler_facts:
            spoiler_scenes.update(fact.involved_scenes)
        
        used_scenes = {s.video for s in trailer.segments}
        alternatives = [
            s for s in story_map.scenes 
            if s.scene_id not in used_scenes 
            and s.scene_id not in spoiler_scenes
            and s.is_characterised
        ]
        
        if not alternatives:
            return False
        
        # Pick best alternative (first one for now)
        new_scene = alternatives[0]
        
        # Create replacement segment
        new_segment = self._create_replacement_segment(new_scene, segment.sequence_order, trailer.audience_promise)
        trailer.segments[segment_idx] = new_segment
        
        self.decision_logger.log(
            component="repair_engine",
            decision_type="replace_segment",
            description=f"Replaced spoiler scene {segment.video} with {new_scene.scene_id}",
            evidence=[f"old_scene:{segment.video}", f"new_scene:{new_scene.scene_id}", f"check:{segment.segment_id}"],
            confidence=0.7,
        )
        
        return True

    def _repair_rights(
        self,
        trailer: TrailerPlan,
        segment_idx: int,
        segment: "Segment",
        story_map: StoryMap,
        rules: list[Rule],
        capability_report: CapabilityReport,
    ) -> bool:
        """Replace asset that violates rights."""
        # Try alternative audio
        if segment.audio.startswith("music_"):
            # Try dialogue instead
            new_segment = self._create_replacement_segment(
                next(s for s in story_map.scenes if s.scene_id == segment.video),
                segment.sequence_order,
                trailer.audience_promise,
            )
            new_segment.audio = "dialogue"
            trailer.segments[segment_idx] = new_segment
            return True
        
        # Try alternative scene
        used_scenes = {s.video for s in trailer.segments}
        alternatives = [s for s in story_map.scenes if s.scene_id not in used_scenes and s.is_characterised]
        
        if alternatives:
            new_scene = alternatives[0]
            new_segment = self._create_replacement_segment(new_scene, segment.sequence_order, trailer.audience_promise)
            trailer.segments[segment_idx] = new_segment
            return True
        
        return False

    def _repair_safety(
        self,
        trailer: TrailerPlan,
        segment_idx: int,
        segment: "Segment",
        story_map: StoryMap,
        rules: list[Rule],
        capability_report: CapabilityReport,
    ) -> bool:
        """Replace scene that violates audience safety."""
        # Similar to spoiler repair - find safer alternative
        used_scenes = {s.video for s in trailer.segments}
        alternatives = [s for s in story_map.scenes if s.scene_id not in used_scenes and s.is_characterised]
        
        if alternatives:
            new_scene = alternatives[0]
            new_segment = self._create_replacement_segment(new_scene, segment.sequence_order, trailer.audience_promise)
            trailer.segments[segment_idx] = new_segment
            return True
        
        return False

    def _repair_source_accuracy(
        self,
        trailer: TrailerPlan,
        segment_idx: int,
        segment: "Segment",
        story_map: StoryMap,
    ) -> bool:
        """Fix timecode bounds issues."""
        scene = next((s for s in story_map.scenes if s.scene_id == segment.video), None)
        if not scene:
            return False
        
        # Clamp timecodes to scene bounds
        new_in = max(segment.source_in, scene.timecode_in)
        new_out = min(segment.source_out, scene.timecode_out)
        
        if new_in < new_out:
            segment.source_in = new_in
            segment.source_out = new_out
            segment.duration_ms = new_out.normalised_ms - new_in.normalised_ms
            return True
        
        return False

    def _create_replacement_segment(
        self, 
        scene: "Scene", 
        sequence_order: int, 
        promise: "AudiencePromise"
    ) -> "Segment":
        """Create a replacement segment for a scene."""
        from src.models.segment import Segment, TransitionType
        import uuid
        
        return Segment(
            segment_id=f"seg_{scene.scene_id}_repaired_{uuid.uuid4().hex[:6]}",
            sequence_order=sequence_order,
            source_in=scene.timecode_in,
            source_out=scene.timecode_out,
            video=scene.scene_id,
            audio="dialogue",
            subtitle=None,
            text_card=None,
            voice_over=None,
            transition=TransitionType.CUT if sequence_order > 0 else None,
            reason=f"Repaired replacement for {promise.narrative_arc[min(sequence_order, len(promise.narrative_arc)-1)]} phase",
            evidence=[f"scene:{scene.scene_id}", "repair:true"],
            risk_flags=["repaired"],
            duration_ms=scene.duration_ms,
        )