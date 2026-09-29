"""Test: Bias detection."""

import pytest
from src.bias_auditor import BiasAuditor
from src.models.audience import AudienceDefinition


def test_bias_detected():
    """Test that bias auditor flags proxy correlations and identity-only justifications."""
    auditor = BiasAuditor(min_sample_size=30, correlation_threshold=0.8)
    
    # Create audience profiles with perfect region->preference correlation
    profiles = [
        AudienceDefinition(
            audience_id="region_1",
            name="Region 1",
            description="Region 1 audience",
            goal="Entertainment",
            special_care=[],
            region="north",
            preferences={"genre": "action"},
            engagement_patterns={"sample_size": 100},
        ),
        AudienceDefinition(
            audience_id="region_2",
            name="Region 2",
            description="Region 2 audience",
            goal="Entertainment",
            special_care=[],
            region="south",
            preferences={"genre": "romance"},
            engagement_patterns={"sample_size": 100},
        ),
        AudienceDefinition(
            audience_id="region_3",
            name="Region 3",
            description="Region 3 audience",
            goal="Entertainment",
            special_care=[],
            region="east",
            preferences={"genre": "comedy"},
            engagement_patterns={"sample_size": 100},
        ),
        AudienceDefinition(
            audience_id="region_4",
            name="Region 4",
            description="Region 4 audience",
            goal="Entertainment",
            special_care=[],
            region="west",
            preferences={"genre": "drama"},
            engagement_patterns={"sample_size": 100},
        ),
    ]
    
    # Personalisation decisions using only identity
    decisions = [
        {
            "decision_id": "dec_01",
            "audience_id": "region_1",
            "evidence": ["region:north"],
            "reason": "Selected because audience is from north region",
        },
        {
            "decision_id": "dec_02",
            "audience_id": "region_2",
            "evidence": ["region:south"],
            "reason": "Selected because audience is from south region",
        },
    ]
    
    report = auditor.audit(profiles, decisions)
    
    # Should flag proxy correlation (region perfectly predicts genre)
    proxy_check = next((c for c in report.checks if c.check_name == "proxy_correlations"), None)
    assert proxy_check is not None
    assert proxy_check.flagged
    
    # Should flag identity-only justification
    identity_check = next((c for c in report.checks if c.check_name == "identity_only_justification"), None)
    assert identity_check is not None
    assert identity_check.flagged
    
    # Test with behavioural evidence (should not flag)
    good_decisions = [
        {
            "decision_id": "dec_03",
            "audience_id": "region_1",
            "evidence": ["engagement_pattern:action_high", "preference:genre_action"],
            "reason": "Selected based on high engagement with action genre",
        }
    ]
    
    report2 = auditor.audit(profiles, good_decisions)
    identity_check2 = next((c for c in report2.checks if c.check_name == "identity_only_justification"), None)
    assert identity_check2 is not None
    assert not identity_check2.flagged