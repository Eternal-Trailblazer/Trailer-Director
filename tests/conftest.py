"""Shared test fixtures."""

import pytest
from pathlib import Path
from src.models.scene import Scene, Entity, EntityType
from src.models.timecode import Timecode, TimecodeFormat, ms_to_timecode
from src.models.story_map import StoryMap, StoryEvent, EmotionalBeat
from src.models.spoiler import SpoilerFact
from src.models.rule import Rule, RuleScope, RuleEffect, RuleCondition
from src.models.audience import AudienceDefinition, AudiencePromise
from src.models.segment import Segment, TransitionType
from src.models.trailer import TrailerPlan, TrailerValidation, ValidationCheck, ValidationStatus
from src.models.capability import CapabilityReport


@pytest.fixture
def sample_scene():
    return Scene(
        scene_id="scene_01",
        timecode_in=Timecode(raw="00:00:00.000", hours=0, minutes=0, seconds=0, fractional=0, source_format=TimecodeFormat.MILLISECONDS, normalised_ms=0),
        timecode_out=Timecode(raw="00:00:30.000", hours=0, minutes=0, seconds=30, fractional=0, source_format=TimecodeFormat.MILLISECONDS, normalised_ms=30000),
        duration_ms=30000,
        description="Opening scene introducing main character",
        entities=["char_01"],
        content_tags=["introduction"],
        emotional_tone="neutral",
        is_characterised=True,
    )


@pytest.fixture
def sample_entity():
    return Entity(
        entity_id="char_01",
        entity_type=EntityType.CHARACTER,
        name="Priya",
        aliases=["Pri"],
        first_appearance_scene="scene_01",
    )


@pytest.fixture
def sample_story_map(sample_scene, sample_entity):
    scenes = [sample_scene]
    for i in range(2, 9):
        tc_in = ms_to_timecode((i-1)*30000, TimecodeFormat.MILLISECONDS)
        tc_out = ms_to_timecode(i*30000, TimecodeFormat.MILLISECONDS)
        scenes.append(Scene(
            scene_id=f"scene_{i:02d}",
            timecode_in=tc_in,
            timecode_out=tc_out,
            duration_ms=30000,
            description=f"Scene {i} description",
            entities=[f"char_{i}"] if i <= 4 else [],
            content_tags=[],
            is_characterised=True,
        ))
    
    entities = [sample_entity]
    for i in range(2, 5):
        entities.append(Entity(entity_id=f"char_{i}", entity_type=EntityType.CHARACTER, name=f"Character {i}"))
    
    return StoryMap(
        episode_id="episode_01",
        scenes=scenes,
        entities=entities,
        major_events=[
            StoryEvent(event_id="event_01", description="Introduction", scene_id="scene_01", involved_entities=["char_01"], event_type="setup", normalised_position=0.05),
            StoryEvent(event_id="event_02", description="Conflict", scene_id="scene_04", involved_entities=["char_01", "char_02"], event_type="conflict", normalised_position=0.4),
            StoryEvent(event_id="event_03", description="Climax", scene_id="scene_07", involved_entities=["char_01", "char_02", "char_03"], event_type="climax", normalised_position=0.85),
        ],
        emotional_arc=[
            EmotionalBeat(scene_id="scene_01", emotion="neutral", intensity=0.3),
            EmotionalBeat(scene_id="scene_04", emotion="tension", intensity=0.8),
            EmotionalBeat(scene_id="scene_07", emotion="surprise", intensity=0.9),
        ],
        total_duration_ms=240000,
    )


@pytest.fixture
def sample_spoiler_facts():
    return [
        SpoilerFact(
            fact_id="spoiler_01",
            fact_type="outcome",
            description="Main character dies in final scene",
            involved_entities=["char_01"],
            involved_scenes=["scene_08"],
            reveal_boundary=0.7,
            evidence=["event_03"],
            confidence=0.9,
        )
    ]


@pytest.fixture
def sample_rules():
    return [
        Rule(
            rule_id="rule_01",
            source_policy_id="policy_family",
            source_span="No violence for family audience",
            scope=RuleScope.VISUAL_CONTENT,
            effect=RuleEffect.DENY,
            conditions=[RuleCondition(field="content_tags", operator="contains", value="violence")],
        ),
        Rule(
            rule_id="rule_02",
            source_contract_id="contract_music_01",
            source_span="Music track expired",
            scope=RuleScope.MUSIC_TRACK,
            effect=RuleEffect.DENY,
            conditions=[RuleCondition(field="music_track", operator="eq", value="music_01")],
        ),
    ]


@pytest.fixture
def sample_audience():
    return AudienceDefinition(
        audience_id="family",
        name="Family viewers",
        description="General family audience",
        goal="Communicate warmth and entertainment",
        special_care=["No violence", "No frightening content"],
        rating_policy_ids=["policy_family"],
    )


@pytest.fixture
def sample_audience_promise():
    return AudiencePromise(
        audience_id="family",
        promise_text="A heartwarming family adventure",
        intended_emotions=["joy", "warmth", "curiosity"],
        narrative_arc=["setup", "tension", "hook"],
        tone="uplifting",
        avoid=["violence", "death"],
        evidence=["event_01", "event_02"],
    )


@pytest.fixture
def sample_segment():
    return Segment(
        segment_id="seg_01",
        sequence_order=0,
        source_in=Timecode(raw="00:00:00.000", hours=0, minutes=0, seconds=0, fractional=0, source_format=TimecodeFormat.MILLISECONDS, normalised_ms=0),
        source_out=Timecode(raw="00:00:10.000", hours=0, minutes=0, seconds=10, fractional=0, source_format=TimecodeFormat.MILLISECONDS, normalised_ms=10000),
        video="scene_01",
        audio="dialogue",
        subtitle="en",
        reason="Establishes main character",
        evidence=["scene:scene_01", "event:event_01"],
        duration_ms=10000,
    )


@pytest.fixture
def sample_trailer(sample_audience_promise, sample_segment):
    return TrailerPlan(
        trailer_id="trailer_01",
        audience="family",
        audience_promise=sample_audience_promise,
        duration_seconds=10.0,
        segments=[sample_segment],
        estimated_cost=0.01,
    )


@pytest.fixture
def capability_report():
    return CapabilityReport(
        has_video=True,
        has_audio=True,
        has_scene_descriptions=True,
        has_source_dialogue=True,
        dialect_tracks=["hi"],
        has_policies=True,
        has_contracts=True,
        has_audience_profiles=True,
        has_historic_data=False,
        has_cost_sheet=True,
        warnings=[],
        degraded_checks=[],
    )