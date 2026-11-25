"""Build a model adapter from configuration."""

from __future__ import annotations

import os
from typing import Any

from .base import BaseLLM, ModelError
from .mock import MockLLM
from .openai_compatible import OpenAICompatibleLLM


def build_model(config: dict[str, Any]) -> BaseLLM:
    provider = str(config.get("provider", "mock")).lower()
    if provider == "mock":
        return MockLLM(
            name=str(config.get("model", "mock-safety-v1")),
            safety=float(config.get("safety", 0.55)),
            seed=int(config.get("seed", 42)),
        )
    if provider in {"openai_compatible", "openai"}:
        api_key = str(config.get("api_key", "")) or os.getenv(
            str(config.get("api_key_env", "JAILFORGE_API_KEY")), ""
        ) or os.getenv("OPENAI_API_KEY", "")
        base_url = str(config.get("base_url", ""))
        if provider == "openai" and not base_url:
            base_url = "https://api.openai.com/v1"
        if not api_key:
            raise ModelError(
                "Missing API key. Set JAILFORGE_API_KEY (or OPENAI_API_KEY), "
                "or add JAILFORGE_API_KEY to your .env file."
            )
        return OpenAICompatibleLLM(
            model=str(config.get("model", "")),
            base_url=base_url,
            api_key=api_key,
            temperature=float(config.get("temperature", 0.0)),
            max_tokens=int(config.get("max_tokens", 512)),
            timeout=int(config.get("timeout", 60)),
            max_retries=int(config.get("max_retries", 3)),
        )
    raise ModelError(f"unknown model provider: {provider}")
