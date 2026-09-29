"""Test: Missing scene detection."""

import pytest
from src.verifier import VerifierOrchestrator
from src.providers import MockProvider
from src.rule_compiler import RuleEvaluator
from src.observability import DecisionLogger


def test_missing_scene(sample_trailer, sample_story_map, sample_rules, capability_report):
    """Test that source_accuracy check fails when segment references non-existent scene."""
    # Modify trailer to reference non-existent scene
    sample_trailer.segments[0].video = "scene_99"  # Doesn't exist
    
    # Create verifier with mock provider
    provider = MockProvider()
    evaluator = RuleEvaluator()
    logger = DecisionLogger()
    verifier = VerifierOrchestrator(provider, evaluator, logger)
    
    result = verifier.verify(
        sample_trailer, 
        sample_story_map, 
        [],  # no spoiler facts
        sample_rules,
        capability_report,
    )
    
    # Check that source_accuracy check fails
    source_accuracy_checks = [c for c in result.validation.checks if c.check_type == "source_accuracy"]
    assert len(source_accuracy_checks) > 0
    
    fail_checks = [c for c in source_accuracy_checks if c.verdict == "FAIL"]
    assert len(fail_checks) > 0
    
    # Verify the failure is about missing scene
    fail_check = fail_checks[0]
    assert "non-existent scene" in fail_check.details or "scene_99" in fail_check.details