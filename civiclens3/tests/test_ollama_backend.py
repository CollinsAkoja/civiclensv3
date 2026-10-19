import io
import json
import urllib.error

import pytest

from core.classifier import ClassificationError, LLMUnavailable
from core.llm_ollama import OllamaBackend

REPORT = {"title": "Pothole", "description": "A deep pothole on the road.",
          "state": "Lagos", "lga": "Ikeja", "community": "GRA"}


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def reply(obj):
    return lambda *a, **k: FakeResponse(json.dumps(obj).encode())


def test_parses_model_json(monkeypatch):
    content = json.dumps({"category": "Roads and potholes"})
    monkeypatch.setattr("core.llm_ollama.urllib.request.urlopen",
                        reply({"message": {"content": content}}))
    assert OllamaBackend().classify(REPORT) == {"category": "Roads and potholes"}


def test_request_pins_model_schema_and_temperature(monkeypatch):
    seen = {}

    def fake(request, timeout=None):
        seen["body"] = json.loads(request.data)
        seen["url"] = request.full_url
        return FakeResponse(json.dumps({"message": {"content": "{}"}}).encode())

    monkeypatch.setattr("core.llm_ollama.urllib.request.urlopen", fake)
    OllamaBackend().classify(REPORT)
    assert seen["url"].endswith("/api/chat")
    assert seen["body"]["model"] == "llama3.2:3b"
    assert seen["body"]["stream"] is False
    assert seen["body"]["options"]["temperature"] == 0
    assert "properties" in seen["body"]["format"]


def test_connection_error_means_unavailable(monkeypatch):
    def boom(*a, **k):
        raise urllib.error.URLError("refused")
    monkeypatch.setattr("core.llm_ollama.urllib.request.urlopen", boom)
    with pytest.raises(LLMUnavailable):
        OllamaBackend().classify(REPORT)


def test_non_json_model_content_is_classification_error(monkeypatch):
    monkeypatch.setattr("core.llm_ollama.urllib.request.urlopen",
                        reply({"message": {"content": "Sure! Here you go"}}))
    with pytest.raises(ClassificationError):
        OllamaBackend().classify(REPORT)


def test_is_available_checks_model_is_pulled(monkeypatch):
    monkeypatch.setattr("core.llm_ollama.urllib.request.urlopen",
                        reply({"models": [{"name": "llama3.2:3b"}]}))
    assert OllamaBackend().is_available() is True
    assert OllamaBackend(model="llama3.2:1b").is_available() is False


def test_is_available_false_when_ollama_off(monkeypatch):
    def boom(*a, **k):
        raise urllib.error.URLError("refused")
    monkeypatch.setattr("core.llm_ollama.urllib.request.urlopen", boom)
    assert OllamaBackend().is_available() is False
