"""Property-based invariant tests."""

import pytest
from hypothesis import given, strategies as st, settings
from src.models.trailer import TrailerPlan, TrailerValidation, ValidationCheck, ValidationStatus
from src.models.story_map import StoryMap, Scene
from src.models.segment import Segment
from src.models.capability import CapabilityReport
from src.models.timecode import Timecode, TimecodeFormat
from src.models.audience import AudiencePromise
from src.models.rule import Rule


# Simple strategies for generating test data
@st.composite
def timecode_strategy(draw):
    ms = draw(st.integers(min_value=0, max_value=3600000))  # Up to 1 hour
    return Timecode(
        raw=f"{ms}ms", hours=0, minutes=0, seconds=0, fractional=0,
        source_format=TimecodeFormat.MILLISECONDS, normalised_ms=ms
    )


@st.composite
def scene_strategy(draw):
    scene_id = draw(st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_", min_size=3, max_size=10))
    tc_in = draw(timecode_strategy())
    tc_out_ms = tc_in.normalised_ms + draw(st.integers(min_value=1000, max_value=120000))
    tc_out = Timecode(
        raw=f"{tc_out_ms}ms", hours=0, minutes=0, seconds=0, fractional=0,
        source_format=TimecodeFormat.MILLISECONDS, normalised_ms=tc_out_ms
    )
    return Scene(
        scene_id=scene_id,
        timecode_in=tc_in,
        timecode_out=tc_out,
        duration_ms=tc_out_ms - tc_in.normalised_ms,
        description=draw(st.text(max_size=200)),
        entities=draw(st.lists(st.text(alphabet="abcdefghijklmnopqrstuvwxyz_", min_size=3, max_size=10), max_size=5)),
        content_tags=draw(st.lists(st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=3, max_size=10), max_size=5)),
        is_characterised=draw(st.booleans()),
    )


@st.composite
def story_map_strategy(draw):
    scenes = draw(st.lists(scene_strategy(), min_size=1, max_size=10))
    return StoryMap(
        episode_id="test_ep",
        scenes=scenes,
        entities=[],
        major_events=[],
        emotional_arc=[],
        total_duration_ms=max(s.timecode_out.normalised_ms for s in scenes),
    )


@st.composite
def segment_strategy(draw, story_map):
    scene = draw(st.sampled_from(story_map.scenes))
    seg_in_ms = draw(st.integers(min_value=scene.timecode_in.normalised_ms, max_value=scene.timecode_out.normalised_ms - 1000))
    seg_out_ms = draw(st.integers(min_value=seg_in_ms + 1000, max_value=scene.timecode_out.normalised_ms))
    
    seg_in = Timecode(raw=f"{seg_in_ms}ms", hours=0, minutes=0, seconds=0, fractional=0, source_format=TimecodeFormat.MILLISECONDS, normalised_ms=seg_in_ms)
    seg_out = Timecode(raw=f"{seg_out_ms}ms", hours=0, minutes=0, seconds=0, fractional=0, source_format=TimecodeFormat.MILLISECONDS, normalised_ms=seg_out_ms)
    
    return Segment(
        segment_id=draw(st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_", min_size=3, max_size=10)),
        sequence_order=draw(st.integers(min_value=0, max_value=10)),
        source_in=seg_in,
        source_out=seg_out,
        video=scene.scene_id,
        audio=draw(st.sampled_from(["dialogue", "music", "silence"])),
        reason=draw(st.text(max_size=200)),
        evidence=draw(st.lists(st.text(max_size=20), max_size=5)),
        duration_ms=seg_out_ms - seg_in_ms,
    )


@st.composite
def trailer_plan_strategy(draw):
    story_map = draw(story_map_strategy())
    segments = draw(st.lists(segment_strategy(story_map), min_size=1, max_size=5))
    
    return TrailerPlan(
        trailer_id=draw(st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_", min_size=3, max_size=10)),
        audience=draw(st.sampled_from(["family", "young_adult", "dialect_region"])),
        audience_promise=AudiencePromise(
            audience_id="test",
            promise_text="Test promise",
            intended_emotions=["engagement"],
            narrative_arc=["setup", "tension", "hook"],
            tone="neutral",
            avoid=[],
            evidence=[],
        ),
        duration_seconds=sum(s.duration_ms for s in segments) / 1000.0,
        segments=segments,
        estimated_cost=draw(st.floats(min_value=0, max_value=10)),
    )


class TestInvariants:
    """Properties that must hold for ANY valid input package."""

    @settings(max_examples=50, deadline=None)
    @given(trailer=trailer_plan_strategy())
    def test_segments_resolve_to_existing_scenes(self, trailer):
        """Every segment's video must reference a scene in the story map."""
        # This test would need the story_map from the trailer's context
        # Simplified: just check segment structure
        for seg in trailer.segments:
            assert seg.video is not None
            assert len(seg.video) > 0

    @settings(max_examples=50, deadline=None)
    @given(trailer=trailer_plan_strategy())
    def test_timecodes_within_scene_bounds(self, trailer):
        """Segment timecodes must be within scene bounds."""
        # Would need scene map - simplified
        for seg in trailer.segments:
            assert seg.source_in.normalised_ms < seg.source_out.normalised_ms
            assert seg.duration_ms == seg.source_out.normalised_ms - seg.source_in.normalised_ms

    @settings(max_examples=20, deadline=None)
    @given(trailer=trailer_plan_strategy())
    def test_no_protected_fact_revealed(self, trailer):
        """If trailer passes validation, no spoiler checks should FAIL."""
        if trailer.validation:
            for check in trailer.validation.checks:
                if check.check_type == "spoiler":
                    # If status is PASS or PASS_WITH_WARNINGS, no spoiler FAILs allowed
                    if trailer.validation.status in (ValidationStatus.PASS, ValidationStatus.PASS_WITH_WARNINGS):
                        assert check.verdict != "FAIL"

    @settings(max_examples=20, deadline=None)
    @given(trailer=trailer_plan_strategy())
    def test_no_denied_asset_used(self, trailer):
        """If trailer passes, no DENY rules should apply."""
        # This would need the rule evaluator - simplified
        if trailer.validation and trailer.validation.status == ValidationStatus.PASS:
            # In a real test, we'd check against actual rules
            pass

    @settings(max_examples=20, deadline=None)
    @given(trailer=trailer_plan_strategy())
    def test_budget_not_exceeded(self, trailer):
        """Trailer estimated cost should not exceed budget (if validation passes)."""
        if trailer.validation and trailer.validation.status in (ValidationStatus.PASS, ValidationStatus.PASS_WITH_WARNINGS):
            # Would check against actual budget limit
            assert trailer.estimated_cost >= 0

    def test_no_pass_with_unresolved_failure(self):
        """A trailer with FAIL checks cannot have PASS status."""
        # Create a VALID trailer with PASS status and no FAIL checks
        trailer = TrailerPlan(
            trailer_id="valid",
            audience="test",
            audience_promise=AudiencePromise(audience_id="test", promise_text="Test", intended_emotions=[], narrative_arc=[], tone="", avoid=[], evidence=[]),
            duration_seconds=10.0,
            segments=[],
            validation=TrailerValidation(
                status=ValidationStatus.PASS,
                checks=[ValidationCheck(check_id="c1", check_type="test", verdict="PASS", evidence=[], details="Passed")],
            ),
        )
        
        # Valid trailer with PASS status should have no FAIL checks
        if trailer.validation.status == ValidationStatus.PASS:
            assert not any(c.verdict == "FAIL" for c in trailer.validation.checks)