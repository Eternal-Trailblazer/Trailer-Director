"""Model provider abstraction layer."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional
from dataclasses import dataclass


@dataclass
class Message:
    """Chat message."""
    role: str
    content: str


@dataclass
class ModelResponse:
    """Model response."""
    text: str
    parsed: Any = None
    tokens_in: int = 0
    tokens_out: int = 0
    cost: float = 0.0
    provider: str = ""
    model: str = ""


@dataclass
class ModelCapabilities:
    """Model capabilities."""
    supports_vision: bool = False
    supports_audio: bool = False
    supports_structured_output: bool = False
    max_context_tokens: int = 4096
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0


class ModelProvider(ABC):
    """Abstract model provider."""

    @abstractmethod
    def complete(
        self, 
        messages: list[Message], 
        schema: type | None = None,
        budget_tag: str = ""
    ) -> ModelResponse:
        """Complete a chat request."""
        pass

    @abstractmethod
    async def complete_async(
        self, 
        messages: list[Message], 
        schema: type | None = None,
        budget_tag: str = ""
    ) -> ModelResponse:
        """Complete a chat request asynchronously."""
        pass

    @abstractmethod
    def capabilities(self) -> ModelCapabilities:
        """Get model capabilities."""
        pass


class MockProvider(ModelProvider):
    """Mock provider for testing without API keys."""

    def __init__(self, responses: dict[str, ModelResponse] | None = None):
        self.responses = responses or {}
        self.call_log: list[dict] = []

    def complete(
        self, 
        messages: list[Message], 
        schema: type | None = None,
        budget_tag: str = ""
    ) -> ModelResponse:
        self.call_log.append({
            "messages": [{"role": m.role, "content": m.content[:100]} for m in messages],
            "schema": schema.__name__ if schema else None,
            "budget_tag": budget_tag,
        })
        
        # Return canned response based on budget_tag or first message content
        key = budget_tag or (messages[0].content[:50] if messages else "default")
        if key in self.responses:
            return self.responses[key]
        
        # Default mock response
        return ModelResponse(
            text='{"status": "mock_response"}',
            parsed={"status": "mock_response"},
            tokens_in=100,
            tokens_out=50,
            cost=0.001,
            provider="mock",
            model="mock-model",
        )

    async def complete_async(
        self, 
        messages: list[Message], 
        schema: type | None = None,
        budget_tag: str = ""
    ) -> ModelResponse:
        return self.complete(messages, schema, budget_tag)

    def capabilities(self) -> ModelCapabilities:
        return ModelCapabilities(
            supports_vision=False,
            supports_audio=False,
            supports_structured_output=True,
            max_context_tokens=4096,
            cost_per_1k_input=0.0,
            cost_per_1k_output=0.0,
        )


class ReplayProvider(ModelProvider):
    """Replay provider - records and replays LLM calls."""

    def __init__(self, replay_file: str | None = None):
        self.replay_file = replay_file
        self.recorded_calls: list[dict] = []
        self.replay_index = 0
        self._load_replay()

    def _load_replay(self) -> None:
        if self.replay_file:
            import json
            try:
                with open(self.replay_file, "r") as f:
                    for line in f:
                        self.recorded_calls.append(json.loads(line))
            except FileNotFoundError:
                pass

    def _save_replay(self) -> None:
        if self.replay_file:
            import json
            with open(self.replay_file, "w") as f:
                for call in self.recorded_calls:
                    f.write(json.dumps(call) + "\n")

    def complete(
        self, 
        messages: list[Message], 
        schema: type | None = None,
        budget_tag: str = ""
    ) -> ModelResponse:
        call_record = {
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "schema": schema.__name__ if schema else None,
            "budget_tag": budget_tag,
        }
        
        if self.replay_index < len(self.recorded_calls):
            # Replay mode
            recorded = self.recorded_calls[self.replay_index]
            self.replay_index += 1
            return ModelResponse(
                text=recorded.get("response", ""),
                parsed=recorded.get("parsed"),
                tokens_in=recorded.get("tokens_in", 0),
                tokens_out=recorded.get("tokens_out", 0),
                cost=recorded.get("cost", 0.0),
                provider="replay",
                model=recorded.get("model", "replayed"),
            )
        else:
            # Recording mode - would call real provider
            # For now, return mock
            response = ModelResponse(
                text='{"status": "recorded"}',
                parsed={"status": "recorded"},
                tokens_in=100,
                tokens_out=50,
                cost=0.001,
                provider="recorded",
                model="recorded-model",
            )
            
            call_record["response"] = response.text
            call_record["parsed"] = response.parsed
            call_record["tokens_in"] = response.tokens_in
            call_record["tokens_out"] = response.tokens_out
            call_record["cost"] = response.cost
            call_record["model"] = response.model
            self.recorded_calls.append(call_record)
            self._save_replay()
            
            return response

    async def complete_async(
        self, 
        messages: list[Message], 
        schema: type | None = None,
        budget_tag: str = ""
    ) -> ModelResponse:
        return self.complete(messages, schema, budget_tag)

    def capabilities(self) -> ModelCapabilities:
        return ModelCapabilities(
            supports_vision=True,
            supports_audio=True,
            supports_structured_output=True,
            max_context_tokens=128000,
            cost_per_1k_input=0.01,
            cost_per_1k_output=0.03,
        )


class FallbackChain(ModelProvider):
    """Fallback chain - tries providers in order."""

    def __init__(self, providers: list[ModelProvider]):
        self.providers = providers

    def complete(
        self, 
        messages: list[Message], 
        schema: type | None = None,
        budget_tag: str = "",
        required_capabilities: ModelCapabilities | None = None
    ) -> ModelResponse:
        last_error = None
        for provider in self.providers:
            try:
                caps = provider.capabilities()
                if required_capabilities:
                    if required_capabilities.supports_vision and not caps.supports_vision:
                        continue
                    if required_capabilities.supports_audio and not caps.supports_audio:
                        continue
                    if required_capabilities.supports_structured_output and not caps.supports_structured_output:
                        continue
                
                return provider.complete(messages, schema, budget_tag)
            except Exception as e:
                last_error = e
                continue
        
        raise RuntimeError(f"All providers failed. Last error: {last_error}")

    async def complete_async(
        self, 
        messages: list[Message], 
        schema: type | None = None,
        budget_tag: str = "",
        required_capabilities: ModelCapabilities | None = None
    ) -> ModelResponse:
        last_error = None
        for provider in self.providers:
            try:
                caps = provider.capabilities()
                if required_capabilities:
                    if required_capabilities.supports_vision and not caps.supports_vision:
                        continue
                    if required_capabilities.supports_audio and not caps.supports_audio:
                        continue
                    if required_capabilities.supports_structured_output and not caps.supports_structured_output:
                        continue
                
                return await provider.complete_async(messages, schema, budget_tag)
            except Exception as e:
                last_error = e
                continue
        
        raise RuntimeError(f"All providers failed. Last error: {last_error}")

    def capabilities(self) -> ModelCapabilities:
        # Return capabilities of first provider
        return self.providers[0].capabilities() if self.providers else ModelCapabilities()