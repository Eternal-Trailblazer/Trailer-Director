"""Test: Spoiler detection."""

import pytest
from src.verifier import VerifierOrchestrator
from src.providers import MockProvider
from src.rule_compiler import RuleEvaluator
from src.observability import DecisionLogger
from src.models.spoiler import SpoilerFact


def test_spoiler_detection(sample_trailer, sample_story_map, sample_rules, capability_report):
    """Test that spoiler check fails when segment contains spoiler scene."""
    # Create a spoiler fact for the scene used in trailer
    spoiler_fact = SpoilerFact(
        fact_id="spoiler_death",
        fact_type="outcome",
        description="Main character death revealed in scene_01",
        involved_entities=["char_01"],
        involved_scenes=["scene_01"],  # This is the scene in our trailer
        reveal_boundary=0.7,
        evidence=["event_03"],
        confidence=0.9,
    )
    
    provider = MockProvider()
    evaluator = RuleEvaluator()
    logger = DecisionLogger()
    verifier = VerifierOrchestrator(provider, evaluator, logger)
    
    result = verifier.verify(
        sample_trailer,
        sample_story_map,
        [spoiler_fact],
        sample_rules,
        capability_report,
    )
    
    # Check that spoiler check fails
    spoiler_checks = [c for c in result.validation.checks if c.check_type == "spoiler"]
    assert len(spoiler_checks) > 0
    
    fail_checks = [c for c in spoiler_checks if c.verdict == "FAIL"]
    assert len(fail_checks) > 0
    
    # Verify the failure mentions direct reveal
    fail_check = fail_checks[0]
    assert "Direct spoiler reveal" in fail_check.details or "spoiler_death" in fail_check.details