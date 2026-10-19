"""Quick live check: sends one sample report to your local Llama via Ollama.

Run:  python check_ollama.py
"""
import json
import time

from core.classifier import ClassificationError, LLMUnavailable, validate_classification
from core.llm_ollama import OllamaBackend

SAMPLE = {
    "title": "Blocked drain near the market",
    "description": (
        "The drain beside the main market has been blocked with refuse for two "
        "weeks. Water spills onto the road whenever it rains."
    ),
    "state": "FCT (Abuja)", "lga": "Bwari", "community": "Dutse",
}

backend = OllamaBackend()
print(f"Model: {backend.name} | Ollama reachable with model pulled: {backend.is_available()}")

start = time.time()
try:
    raw = backend.classify(SAMPLE)
    print(f"\nRaw model output ({time.time() - start:.1f}s):")
    print(json.dumps(raw, indent=2, ensure_ascii=False))
    result = validate_classification(raw, backend.name)
    print("\nPASSED schema validation:", result.category, "|", result.suggested_urgency)
except LLMUnavailable as exc:
    print("\nOllama not usable:", exc)
    print("Check that Ollama is running and that you have run: ollama pull", backend.name)
except ClassificationError as exc:
    print("\nModel replied, but the output failed validation:", exc)
