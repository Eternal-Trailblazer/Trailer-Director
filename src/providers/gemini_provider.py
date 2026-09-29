"""Google Gemini provider implementation."""

from __future__ import annotations

import os
from typing import Any, Optional

from src.providers.base import ModelProvider, ModelResponse, Message, ModelCapabilities


class GeminiProvider(ModelProvider):
    """Google Gemini provider."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gemini-1.5-pro",
        api_key_env: str = "GEMINI_API_KEY",
    ):
        self.model = model
        self.api_key = api_key or os.getenv(api_key_env)
        if not self.api_key:
            raise ValueError(f"Gemini API key not found. Set {api_key_env} or pass api_key.")
        
        try:
            import warnings
            warnings.filterwarnings("ignore", category=FutureWarning)
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self.client = genai.GenerativeModel(model)
        except ImportError:
            raise ImportError("google-generativeai package not installed. Run: pip install google-generativeai")

    def complete(
        self,
        messages: list[Message],
        schema: type | None = None,
        budget_tag: str = "",
    ) -> ModelResponse:
        """Complete a chat request."""
        # Convert messages to Gemini format
        system_prompt = ""
        user_messages = []
        
        for msg in messages:
            if msg.role == "system":
                system_prompt = msg.content
            else:
                user_messages.append({"role": msg.role, "content": msg.content})
        
        # Combine system prompt with first user message if present
        if system_prompt and user_messages:
            user_messages[0]["content"] = f"{system_prompt}\n\n{user_messages[0]['content']}"
        elif system_prompt:
            user_messages.insert(0, {"role": "user", "content": system_prompt})

        # Call API
        response = self.client.generate_content(user_messages)
        
        # Extract text
        text = response.text if response.text else ""
        
        # Estimate tokens (rough approximation)
        input_tokens = sum(len(m.content.split()) for m in messages)
        output_tokens = len(text.split())
        
        # Approximate cost (Gemini 1.5 Pro pricing)
        cost = (input_tokens * 3.5 + output_tokens * 10.5) / 1_000_000

        return ModelResponse(
            text=text,
            tokens_in=input_tokens,
            tokens_out=output_tokens,
            cost=cost,
            provider="gemini",
            model=self.model,
        )

    async def complete_async(
        self,
        messages: list[Message],
        schema: type | None = None,
        budget_tag: str = "",
    ) -> ModelResponse:
        """Complete a chat request asynchronously."""
        # For now, just call sync version
        return self.complete(messages, schema, budget_tag)

    def capabilities(self) -> ModelCapabilities:
        return ModelCapabilities(
            supports_vision=True,
            supports_audio=True,
            supports_structured_output=True,
            max_context_tokens=2_000_000,
            cost_per_1k_input=3.5,
            cost_per_1k_output=10.5,
        )