"""Test: Rights restriction enforcement."""

import pytest
from src.verifier import VerifierOrchestrator
from src.providers import MockProvider
from src.rule_compiler import RuleEvaluator
from src.observability import DecisionLogger
from src.models.rule import Rule, RuleScope, RuleEffect, RuleCondition


def test_rights_restriction(sample_trailer, sample_story_map, capability_report):
    """Test that rights check fails when DENY rule applies to segment."""
    # Create a rule that denies the scene used in the trailer
    deny_rule = Rule(
        rule_id="deny_scene_01",
        source_contract_id="contract_actor",
        source_span="Actor in scene_01 cannot appear in promo",
        scope=RuleScope.SCENE,
        effect=RuleEffect.DENY,
        conditions=[RuleCondition(field="scene_id", operator="eq", value="scene_01")],
    )
    
    provider = MockProvider()
    evaluator = RuleEvaluator()
    logger = DecisionLogger()
    verifier = VerifierOrchestrator(provider, evaluator, logger)
    
    result = verifier.verify(
        sample_trailer,
        sample_story_map,
        [],  # no spoiler facts
        [deny_rule],
        capability_report,
    )
    
    # Check that rights check fails
    rights_checks = [c for c in result.validation.checks if c.check_type == "rights"]
    assert len(rights_checks) > 0
    
    fail_checks = [c for c in rights_checks if c.verdict == "FAIL"]
    assert len(fail_checks) > 0
    
    # Verify the failure mentions the deny rule
    fail_check = fail_checks[0]
    assert "DENY rule" in fail_check.details or "deny_scene_01" in fail_check.details