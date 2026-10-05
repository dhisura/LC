"""Lightweight Ollama LLM client for LC."""
from typing import Generator, List, Dict, Any, Optional
import httpx
from lc.config import OLLAMA_HOST, DEFAULT_MODEL


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
        """Send chat messages and return full response text."""
        import ollama
        client = ollama.Client(host=self.host)
        
        options: Dict[str, Any] = {"temperature": temperature}
        if max_tokens:
            options["num_predict"] = max_tokens

        try:
            response = client.chat(
                model=self.model,
                messages=messages,
                options=options
            )
            return response["message"]["content"]
        except Exception as e:
            # Fallback to direct HTTP API if SDK fails
            return self._http_chat(messages, options)

    def chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.2
    ) -> Generator[str, None, None]:
        """Stream response tokens chunk by chunk."""
        import ollama
        client = ollama.Client(host=self.host)
        options = {"temperature": temperature}
        
        try:
            stream = client.chat(
                model=self.model,
                messages=messages,
                options=options,
                stream=True
            )
            for chunk in stream:
                token = chunk["message"]["content"]
                yield token
        except Exception as e:
            # Fallback to non-streaming if streaming fails
            content = self.chat(messages, temperature=temperature)
            yield content

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
