"""Test: Hallucinated scene detection."""

import pytest
from src.verifier import VerifierOrchestrator
from src.providers import MockProvider
from src.rule_compiler import RuleEvaluator
from src.observability import DecisionLogger
from src.models.trailer import TrailerPlan
from src.models.audience import AudiencePromise
from src.models.segment import Segment
from src.models.story_map import StoryMap, EmotionalBeat
from src.models.scene import Scene
from src.models.capability import CapabilityReport
from src.models.timecode import Timecode, TimecodeFormat, ms_to_timecode


def test_hallucinated_scene():
    """Test that source-accuracy check catches non-existent scene references."""
    # Create a minimal story map with only 3 scenes
    scenes = [
        Scene(
            scene_id=f"scene_{i:02d}",
            timecode_in=ms_to_timecode(i*30000, TimecodeFormat.MILLISECONDS),
            timecode_out=ms_to_timecode((i+1)*30000, TimecodeFormat.MILLISECONDS),
            duration_ms=30000,
            description=f"Scene {i}",
            entities=[],
            content_tags=[],
            is_characterised=True,
        )
        for i in range(1, 4)
    ]
    
    story_map = StoryMap(
        episode_id="ep_01",
        scenes=scenes,
        entities=[],
        major_events=[],
        emotional_arc=[],
        total_duration_ms=90000,
    )
    
    # Create trailer with hallucinated scene (scene_99 doesn't exist)
    promise = AudiencePromise(
        audience_id="test",
        promise_text="Test",
        intended_emotions=["curiosity"],
        narrative_arc=["setup", "tension", "hook"],
        tone="neutral",
        avoid=[],
        evidence=[],
    )
    
    trailer = TrailerPlan(
        trailer_id="trailer_hallucinated",
        audience="test",
        audience_promise=promise,
        duration_seconds=10.0,
        segments=[
            Segment(
                segment_id="seg_hallucinated",
                sequence_order=0,
                source_in=Timecode(raw="0", hours=0, minutes=0, seconds=0, fractional=0, source_format=TimecodeFormat.MILLISECONDS, normalised_ms=0),
                source_out=Timecode(raw="0", hours=0, minutes=0, seconds=10, fractional=0, source_format=TimecodeFormat.MILLISECONDS, normalised_ms=10000),
                video="scene_99",  # Hallucinated - doesn't exist
                audio="dialogue",
                reason="Hallucinated scene",
                evidence=["scene:scene_99"],
                duration_ms=10000,
            )
        ],
        estimated_cost=0.01,
    )
    
    capability_report = CapabilityReport(
        has_video=False, has_audio=False, has_scene_descriptions=True,
        has_source_dialogue=False, dialect_tracks=[], has_policies=False,
        has_contracts=False, has_audience_profiles=False, has_historic_data=False,
        has_cost_sheet=False, warnings=[], degraded_checks=[]
    )
    
    provider = MockProvider()
    evaluator = RuleEvaluator()
    logger = DecisionLogger()
    verifier = VerifierOrchestrator(provider, evaluator, logger)
    
    result = verifier.verify(
        trailer,
        story_map,
        [],  # no spoiler facts
        [],  # no rules
        capability_report,
    )
    
    # Check that source_accuracy check fails
    source_checks = [c for c in result.validation.checks if c.check_type == "source_accuracy"]
    fail_checks = [c for c in source_checks if c.verdict == "FAIL"]
    
    assert len(fail_checks) > 0
    fail_check = fail_checks[0]
    assert "non-existent scene" in fail_check.details or "scene_99" in fail_check.details