"""Ollama backend (local Llama). Uses only the standard library."""
import json
import os
import urllib.error
import urllib.request

from core.classifier import (
    RESPONSE_SCHEMA, ClassificationError, LLMUnavailable, build_messages,
)

DEFAULT_MODEL = "llama3.2:3b"
DEFAULT_HOST = "http://localhost:11434"


class OllamaBackend:
    def __init__(self, model=None, host=None, timeout=180):
        self.name = model or os.environ.get("CIVICLENS_MODEL", DEFAULT_MODEL)
        self.host = (host or os.environ.get("OLLAMA_HOST_URL", DEFAULT_HOST)).rstrip("/")
        self.timeout = timeout

    def classify(self, report: dict) -> dict:
        body = {
            "model": self.name,
            "messages": build_messages(report),
            "stream": False,
            "format": RESPONSE_SCHEMA,  # constrains output to our JSON schema
            "options": {"temperature": 0},
        }
        request = urllib.request.Request(
            f"{self.host}/api/chat",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as resp:
                payload = json.load(resp)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise LLMUnavailable(f"Could not reach Ollama: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise ClassificationError("Ollama returned an unreadable response.") from exc

        try:
            return json.loads(payload["message"]["content"])
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise ClassificationError("Model did not return valid JSON.") from exc

    def is_available(self) -> bool:
        """True if Ollama is running and our model has been pulled."""
        try:
            with urllib.request.urlopen(f"{self.host}/api/tags", timeout=2) as resp:
                tags = json.load(resp)
            names = {m.get("name") for m in tags.get("models", [])}
            return self.name in names
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            return False
