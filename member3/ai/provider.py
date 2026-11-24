"""LLM provider interface. Business logic only ever sees complete_json()."""
import json
import os
import urllib.error
import urllib.request

from ..settings import load_settings


class ProviderError(RuntimeError):
    """The provider is missing, slow, unreachable or returned something unusable."""


class Provider:
    name = "base"

    def complete_json(self, prompt):
        """Return the JSON object produced for the prompt, or raise ProviderError."""
        raise NotImplementedError


class GeminiProvider(Provider):
    URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def __init__(self, api_key, model, timeout):
        self.name = f"gemini:{model}"
        self._key, self._model, self._timeout = api_key, model, timeout

    def complete_json(self, prompt):
        body = {"contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"responseMimeType": "application/json", "temperature": 0}}
        request = urllib.request.Request(
            self.URL.format(model=self._model), data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "x-goog-api-key": self._key})
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                reply = json.load(response)
            return parse_json_object(reply["candidates"][0]["content"]["parts"][0]["text"])
        except urllib.error.HTTPError as error:  # its text never contains the key, which is a header
            raise ProviderError(f"{self.name}: HTTP {error.code}") from error
        except (OSError, ValueError, KeyError, IndexError, TypeError) as error:
            raise ProviderError(f"{self.name}: {type(error).__name__}") from error


def parse_json_object(text):
    try:
        value = json.loads(text)
    except ValueError as error:
        raise ProviderError("response is not valid JSON") from error
    if not isinstance(value, dict):
        raise ProviderError("response is not a JSON object")
    return value


def _gemini(ai):
    key = os.environ.get("GEMINI_API_KEY")
    return GeminiProvider(key, os.environ.get("GEMINI_MODEL") or ai["model"], ai["timeout_seconds"]) if key else None


PROVIDERS = {"gemini": _gemini}


def get_provider():
    """The configured provider, or None in demo mode (no API key)."""
    ai = load_settings()["ai"]
    return PROVIDERS[ai["provider"]](ai)
