"""Model adapters."""

from .base import BaseLLM, ModelError
from .mock import MockLLM
from .openai_compatible import OpenAICompatibleLLM
from .registry import build_model

__all__ = [
    "BaseLLM",
    "ModelError",
    "MockLLM",
    "OpenAICompatibleLLM",
    "build_model",
]
