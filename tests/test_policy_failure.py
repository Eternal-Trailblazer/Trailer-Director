"""Test: Audience safety policy failure."""

import pytest
from src.verifier import VerifierOrchestrator
from src.providers import MockProvider
from src.rule_compiler import RuleEvaluator
from src.observability import DecisionLogger
from src.models.rule import Rule, RuleScope, RuleEffect, RuleCondition
from src.models.scene import Scene
from src.models.timecode import Timecode, TimecodeFormat


def test_policy_failure(sample_story_map, sample_rules, capability_report):
    """Test that audience_safety check fails for family audience with violent content."""
    from src.models.trailer import TrailerPlan
    from src.models.audience import AudiencePromise
    from src.models.segment import Segment
    
    # Create a scene with violence tag
    violent_scene = Scene(
        scene_id="scene_violent",
        timecode_in=Timecode(raw="00:10:00.000", hours=0, minutes=10, seconds=0, fractional=0, source_format=TimecodeFormat.MILLISECONDS, normalised_ms=600000),
        timecode_out=Timecode(raw="00:10:30.000", hours=0, minutes=10, seconds=30, fractional=0, source_format=TimecodeFormat.MILLISECONDS, normalised_ms=630000),
        duration_ms=30000,
        description="Violent fight scene",
        entities=["char_01"],
        content_tags=["violence", "blood"],
        emotional_tone="tension",
        is_characterised=True,
    )
    
    # Add violent scene to story map
    sample_story_map.scenes.append(violent_scene)
    
    # Create trailer with violent scene for family audience
    promise = AudiencePromise(
        audience_id="family",
        promise_text="Family friendly adventure",
        intended_emotions=["joy", "warmth"],
        narrative_arc=["setup", "tension", "hook"],
        tone="uplifting",
        avoid=["violence", "blood"],
        evidence=["event_01"],
    )
    
    trailer = TrailerPlan(
        trailer_id="trailer_family_violent",
        audience="family",
        audience_promise=promise,
        duration_seconds=10.0,
        segments=[
            Segment(
                segment_id="seg_violent",
                sequence_order=0,
                source_in=violent_scene.timecode_in,
                source_out=violent_scene.timecode_out,
                video="scene_violent",
                audio="dialogue",
                reason="Action scene",
                evidence=["scene:scene_violent"],
                duration_ms=30000,
            )
        ],
        estimated_cost=0.01,
    )
    
    # Create policy rule: family audience + violence = DENY
    policy_rule = Rule(
        rule_id="policy_family_violence",
        source_policy_id="policy_family",
        source_span="Family-rated content must not include violence",
        scope=RuleScope.AUDIENCE,
        effect=RuleEffect.DENY,
        conditions=[
            RuleCondition(field="audience_id", operator="eq", value="family"),
            RuleCondition(field="content_tags", operator="contains", value="violence"),
        ],
    )
    
    all_rules = sample_rules + [policy_rule]
    
    provider = MockProvider()
    evaluator = RuleEvaluator()
    logger = DecisionLogger()
    verifier = VerifierOrchestrator(provider, evaluator, logger)
    
    result = verifier.verify(
        trailer,
        sample_story_map,
        [],  # no spoiler facts
        all_rules,
        capability_report,
    )
    
    # Check that audience_safety check fails
    safety_checks = [c for c in result.validation.checks if c.check_type == "audience_safety"]
    assert len(safety_checks) > 0
    
    fail_checks = [c for c in safety_checks if c.verdict == "FAIL"]
    assert len(fail_checks) > 0
    
    # Verify the failure mentions the policy violation
    fail_check = fail_checks[0]
    assert "Safety rule violation" in fail_check.details or "family" in fail_check.details