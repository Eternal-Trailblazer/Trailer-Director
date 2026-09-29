"""Anthropic provider implementation."""

from __future__ import annotations

import os
from typing import Any, Optional

from src.providers.base import ModelProvider, ModelResponse, Message, ModelCapabilities


class AnthropicProvider(ModelProvider):
    """Anthropic (Claude) provider."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-3-5-sonnet-20241022",
        api_key_env: str = "ANTHROPIC_API_KEY"
    ):
        self.model = model
        self.api_key = api_key or os.getenv(api_key_env)
        if not self.api_key:
            raise ValueError(f"Anthropic API key not found. Set {api_key_env} or pass api_key.")
        
        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=self.api_key)
        except ImportError:
            raise ImportError("anthropic package not installed. Run: pip install anthropic")

    def complete(
        self,
        messages: list[Message],
        schema: type | None = None,
        budget_tag: str = ""
    ) -> ModelResponse:
        """Complete a chat request."""
        # Convert messages to Anthropic format
        system_msg = ""
        user_messages = []
        
        for msg in messages:
            if msg.role == "system":
                system_msg = msg.content
            else:
                user_messages.append({"role": msg.role, "content": msg.content})

        # Call API
        kwargs = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": user_messages,
        }
        if system_msg:
            kwargs["system"] = system_msg

        response = self.client.messages.create(**kwargs)
        
        # Calculate cost (approximate)
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        
        # Approximate pricing for Claude 3.5 Sonnet
        cost = (input_tokens * 3.0 + output_tokens * 15.0) / 1_000_000

        return ModelResponse(
            text=response.content[0].text,
            tokens_in=input_tokens,
            tokens_out=output_tokens,
            cost=cost,
            provider="anthropic",
            model=self.model,
        )

    async def complete_async(
        self,
        messages: list[Message],
        schema: type | None = None,
        budget_tag: str = ""
    ) -> ModelResponse:
        """Complete a chat request asynchronously."""
        # For now, just call sync version
        return self.complete(messages, schema, budget_tag)

    def capabilities(self) -> ModelCapabilities:
        return ModelCapabilities(
            supports_vision=True,
            supports_audio=False,
            supports_structured_output=True,
            max_context_tokens=200000,
            cost_per_1k_input=3.0,
            cost_per_1k_output=15.0,
        )