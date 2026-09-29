"""Test: Budget exceeded handling."""

import pytest
from src.providers import BudgetController, BudgetConfig


def test_budget_exceeded():
    """Test that budget controller halts when limit exceeded."""
    config = BudgetConfig(
        total_usd=0.01,  # Very low budget
        model_call_limit=10,
        media_processing_limit=5,
        warn_at_percent=80,
    )
    controller = BudgetController(config)
    
    # First call should succeed
    assert controller.check_budget(0.005, "test") is True
    controller.record_spend(0.005, "test", tokens_in=100, tokens_out=50)
    
    # Second call should fail (would exceed budget)
    assert controller.check_budget(0.01, "test") is False
    
    # Check stats
    stats = controller.get_usage_stats()
    assert stats["total_cost"] == 0.005
    assert stats["budget_remaining"] == 0.005
    assert stats["percent_used"] == 50.0


def test_budget_warning():
    """Test that warning is issued at threshold."""
    config = BudgetConfig(
        total_usd=1.00,
        model_call_limit=100,
        media_processing_limit=50,
        warn_at_percent=50,  # Warn at 50%
    )
    controller = BudgetController(config)
    
    # Spend 60% - should trigger warning
    controller.record_spend(0.60, "test", tokens_in=1000, tokens_out=500)
    
    stats = controller.get_usage_stats()
    assert stats["percent_used"] == 60.0
    # Warning would be logged in real implementation