"""Test: Changed contract handling."""

import pytest
from src.change_handler import ChangeHandler
from src.generator import TrailerGenerator
from src.verifier import VerifierOrchestrator
from src.repair_engine import RepairEngine
from src.observability import DecisionLogger
from src.providers import MockProvider
from src.rule_compiler import RuleEvaluator
from src.models.change_event import ChangeEvent, ChangeEventType
from src.models.trailer import TrailerPlan
from src.models.audience import AudiencePromise
from src.models.segment import Segment
from src.models.story_map import StoryMap
from src.models.rule import Rule, RuleScope, RuleEffect, RuleCondition
from src.models.capability import CapabilityReport
from src.models.timecode import Timecode, TimecodeFormat


def test_changed_contract(sample_story_map, capability_report):
    """Test that change handler revises affected segments when contract expires."""
    # Setup initial state with a music track allowed
    from src.models.audience import AudiencePromise
    from src.models.trailer import TrailerPlan
    from src.models.segment import Segment
    
    # Create initial rules allowing music
    initial_rules = [
        Rule(
            rule_id="music_allow",
            source_contract_id="contract_music_01",
            source_span="Music track 01 allowed for promo",
            scope=RuleScope.MUSIC_TRACK,
            effect=RuleEffect.ALLOW,
            conditions=[RuleCondition(field="music_track", operator="eq", value="music_01")],
        )
    ]
    
    # Create trailer using music_01
    promise = AudiencePromise(
        audience_id="family",
        promise_text="Family trailer",
        intended_emotions=["joy"],
        narrative_arc=["setup", "tension", "hook"],
        tone="uplifting",
        avoid=[],
        evidence=[],
    )
    
    trailer = TrailerPlan(
        trailer_id="trailer_01",
        audience="family",
        audience_promise=promise,
        duration_seconds=10.0,
        segments=[
            Segment(
                segment_id="seg_01",
                sequence_order=0,
                source_in=Timecode(raw="0", hours=0, minutes=0, seconds=0, fractional=0, source_format=TimecodeFormat.MILLISECONDS, normalised_ms=0),
                source_out=Timecode(raw="0", hours=0, minutes=0, seconds=10, fractional=0, source_format=TimecodeFormat.MILLISECONDS, normalised_ms=10000),
                video="scene_01",
                audio="music_01",  # Uses the music track
                reason="Opening with music",
                evidence=["scene:scene_01", "music:music_01"],
                duration_ms=10000,
            )
        ],
        estimated_cost=0.01,
    )
    
    # Create components
    provider = MockProvider()
    evaluator = RuleEvaluator()
    logger = DecisionLogger()
    generator = TrailerGenerator(provider, evaluator, logger)
    verifier = VerifierOrchestrator(provider, evaluator, logger)
    repair_engine = RepairEngine(generator, verifier, logger)
    change_handler = ChangeHandler(generator, verifier, repair_engine, logger)
    
    # Initialize dependency graph
    change_handler.initialize_graph(sample_story_map, [], initial_rules, [trailer])
    
    # Create change event: music contract expires
    change_event = ChangeEvent(
        event_id="change_01",
        event_type=ChangeEventType.ASSET_EXPIRED,
        description="Music track music_01 license expired",
        affected_entity_ids=["music_01"],
        source="rights_management",
    )
    
    # Create new rules with music denied
    new_rules = [
        Rule(
            rule_id="music_deny",
            source_contract_id="contract_music_01",
            source_span="Music track 01 license expired",
            scope=RuleScope.MUSIC_TRACK,
            effect=RuleEffect.DENY,
            conditions=[RuleCondition(field="music_track", operator="eq", value="music_01")],
        )
    ]
    
    # Handle change
    result = change_handler.handle_change(
        change_event,
        [trailer],
        sample_story_map,
        [],  # no spoiler facts
        new_rules,
        capability_report,
    )
    
    # Check that trailer was updated
    updated_trailer = result.updated_trailers[0]
    
    # Verify the segment was revised (music changed or segment replaced)
    revised_segments = [s for s in updated_trailer.segments if "revised" in s.risk_flags]
    assert len(revised_segments) > 0 or updated_trailer.segments[0].audio != "music_01"
    
    # Verify changelog recorded the change
    assert len(result.changelog) > 0
    change_entry = result.changelog[0]
    assert change_entry["event_id"] == "change_01"
    assert change_entry["event_type"] == "asset_expired"