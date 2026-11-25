"""OpenAI-compatible chat-completions adapter.

Works with DeepSeek, DashScope compatible mode, OpenAI, Moonshot, vLLM, Ollama
(``/v1``) and any other endpoint that implements ``POST /chat/completions``.
"""

from __future__ import annotations

import time
from typing import Any

from .base import BaseLLM, ModelError

try:  # pragma: no cover - import guard
    import requests
except ImportError:  # pragma: no cover
    requests = None  # type: ignore[assignment]


class OpenAICompatibleLLM(BaseLLM):
    def __init__(
        self,
        model: str,
        base_url: str,
        api_key: str,
        temperature: float = 0.0,
        max_tokens: int = 512,
        timeout: int = 60,
        max_retries: int = 3,
        name: str | None = None,
    ) -> None:
        if not base_url:
            raise ModelError("base_url is required for openai_compatible provider")
        if not model:
            raise ModelError("model is required for openai_compatible provider")
        if not api_key:
            raise ModelError(
                "API key is missing. Set JAILFORGE_API_KEY or OPENAI_API_KEY."
            )
        if requests is None:  # pragma: no cover
            raise ModelError("requests is not installed; run pip install requests")
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.max_retries = max_retries
        self.name = name or f"{model}"

    @property
    def _endpoint(self) -> str:
        if self.base_url.endswith("/chat/completions"):
            return self.base_url
        return f"{self.base_url}/chat/completions"

    def generate(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature if temperature is None else temperature,
            "max_tokens": self.max_tokens if max_tokens is None else max_tokens,
            "stream": False,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = requests.post(
                    self._endpoint,
                    json=payload,
                    headers=headers,
                    timeout=self.timeout,
                )
            except requests.RequestException as exc:  # type: ignore[union-attr]
                last_error = exc
                if attempt < self.max_retries:
                    time.sleep(min(8, 2**attempt))
                    continue
                raise ModelError(f"request failed: {exc}") from exc

            if response.status_code in {429, 500, 502, 503, 504} and attempt < self.max_retries:
                time.sleep(min(8, 2**attempt))
                continue
            if response.status_code >= 400:
                detail = response.text[:500]
                raise ModelError(
                    f"HTTP {response.status_code} from {self._endpoint}: {detail}"
                )
            try:
                data = response.json()
                message = data["choices"][0]["message"]
                content = message.get("content") or message.get("reasoning_content") or ""
            except (ValueError, KeyError, IndexError, TypeError) as exc:
                raise ModelError(f"unexpected response shape: {response.text[:300]}") from exc
            if not content.strip():
                raise ModelError("model returned empty content")
            return content

        raise ModelError(f"request failed after retries: {last_error}")

    def health(self) -> dict[str, Any]:
        if requests is None:  # pragma: no cover
            return {"ok": False, "error": "requests is not installed"}
        try:
            response = requests.get(
                f"{self.base_url}/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=min(15, self.timeout),
            )
            return {
                "ok": response.status_code < 400,
                "model": self.model,
                "status_code": response.status_code,
                "endpoint": self.base_url,
            }
        except requests.RequestException as exc:  # type: ignore[union-attr]
            return {"ok": False, "model": self.model, "error": str(exc)}
