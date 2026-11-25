"""Abstract model interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ModelError(RuntimeError):
    """Raised when a model provider cannot complete a request."""


class BaseLLM(ABC):
    name: str = "base"

    @abstractmethod
    def generate(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Return the assistant text for a chat-style message list."""

    def health(self) -> dict[str, Any]:
        return {"ok": True, "model": self.name}
