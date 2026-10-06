"""Lightweight Ollama LLM client for LC."""
import logging
from typing import Any, Dict, Generator, List, Optional

import httpx

from lc.config import OLLAMA_HOST, DEFAULT_MODEL

logger = logging.getLogger("lc.engine.llm")


class LLMUnavailableError(RuntimeError):
    """Raised when the local Ollama server cannot fulfil a request.

    Carries a message meant for a human, so callers can surface the real cause
    instead of an opaque HTTP error from deep inside a fallback path.
    """


class LLMClient:
    """Manages chat requests and streaming responses to local Ollama."""

    def __init__(self, host: str = OLLAMA_HOST, model: str = DEFAULT_MODEL):
        self.host = host.rstrip("/")
        self.model = model

    def is_available(self) -> bool:
        """Check if local Ollama server is reachable."""
        try:
            r = httpx.get(f"{self.host}/api/tags", timeout=3.0)
            return r.status_code == 200
        except Exception:
            return False

    def list_models(self) -> List[str]:
        """List locally downloaded models."""
        try:
            r = httpx.get(f"{self.host}/api/tags", timeout=4.0)
            if r.status_code == 200:
                data = r.json()
                return [m["name"] for m in data.get("models", [])]
        except Exception:
            pass
        return []

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.2,
        max_tokens: Optional[int] = None
    ) -> str:
        """Send chat messages and return full response text.

        Prefers the ollama SDK, then falls back to the raw HTTP endpoint, and
        reports the *original* failure if both fail -- the fallback's own error
        (usually a bare 404) says nothing about why the first attempt broke.
        """
        options: Dict[str, Any] = {"temperature": temperature}
        if max_tokens:
            options["num_predict"] = max_tokens

        sdk_error: Optional[Exception] = None
        try:
            import ollama
            client = ollama.Client(host=self.host)
            response = client.chat(
                model=self.model,
                messages=messages,
                options=options
            )
            return response["message"]["content"]
        except Exception as exc:
            sdk_error = exc
            logger.warning("Ollama SDK call failed (%s); falling back to HTTP", exc)

        try:
            return self._http_chat(messages, options)
        except Exception as exc:
            raise LLMUnavailableError(
                f"Could not reach Ollama at {self.host} for model '{self.model}'.\n"
                f"  SDK error    : {sdk_error}\n"
                f"  HTTP error   : {exc}\n"
                "Is `ollama serve` running, and is the model pulled?\n"
                f"  Run: ollama pull {self.model}"
            ) from exc

    def chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.2
    ) -> Generator[str, None, None]:
        """Stream response tokens chunk by chunk.

        The fallback is deliberately *not* attempted mid-stream: emitting a
        partial answer and then the full one would show the user the text twice.
        A failure before the first token can still fall back cleanly.
        """
        options = {"temperature": temperature}
        emitted = 0

        try:
            import ollama
            client = ollama.Client(host=self.host)
            stream = client.chat(
                model=self.model,
                messages=messages,
                options=options,
                stream=True
            )
            for chunk in stream:
                token = chunk.get("message", {}).get("content", "")
                if token:
                    emitted += 1
                    yield token
            return
        except Exception as exc:
            if emitted:
                logger.error("Stream broke after %d token(s): %s", emitted, exc)
                raise
            logger.warning("Ollama SDK stream unavailable (%s); falling back to HTTP", exc)

        try:
            yield self._http_chat(messages, options)
        except Exception as exc:
            raise LLMUnavailableError(
                f"Could not stream from Ollama at {self.host} for model '{self.model}': {exc}\n"
                f"  Run: ollama pull {self.model}"
            ) from exc

    def _http_chat(self, messages: List[Dict[str, str]], options: Dict[str, Any]) -> str:
        """Direct HTTP fallback to Ollama chat endpoint."""
        url = f"{self.host}/api/chat"
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": options
        }
        with httpx.Client(timeout=180.0) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["message"]["content"]
