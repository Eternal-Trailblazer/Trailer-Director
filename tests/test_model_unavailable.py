"""Test: Model unavailable fallback."""

import pytest
from src.providers import FallbackChain, MockProvider, ModelProvider, ModelResponse, Message


class FailingProvider(ModelProvider):
    """Provider that always fails."""
    def complete(self, messages, schema=None, budget_tag=""):
        raise ConnectionError("Provider unavailable")
    
    async def complete_async(self, messages, schema=None, budget_tag=""):
        raise ConnectionError("Provider unavailable")
    
    def capabilities(self):
        from src.providers import ModelCapabilities
        return ModelCapabilities()


def test_model_unavailable():
    """Test that fallback chain engages alternative provider when primary fails."""
    # Create failing primary and working fallback
    failing = FailingProvider()
    working = MockProvider()
    
    chain = FallbackChain([failing, working])
    
    # Should succeed with fallback
    response = chain.complete([Message(role="user", content="test")])
    
    assert response.provider == "mock"
    assert response.text == '{"status": "mock_response"}'


def test_fallback_capability_filter():
    """Test that fallback respects required capabilities."""
    from src.providers import ModelCapabilities
    
    # Provider without vision
    no_vision = MockProvider()
    no_vision.capabilities = lambda: ModelCapabilities(
        supports_vision=False,
        supports_audio=False,
        supports_structured_output=True,
    )
    
    # Provider with vision
    with_vision = MockProvider()
    with_vision.capabilities = lambda: ModelCapabilities(
        supports_vision=True,
        supports_audio=False,
        supports_structured_output=True,
    )
    
    chain = FallbackChain([no_vision, with_vision])
    
    # Request vision - should skip first provider
    response = chain.complete(
        [Message(role="user", content="test")],
        required_capabilities=ModelCapabilities(supports_vision=True)
    )
    
    # Should use second provider
    assert response.provider == "mock"