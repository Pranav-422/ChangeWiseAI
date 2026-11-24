"""LLM provider interface. Business logic only ever sees complete_json()."""
import json
import logging
import os
import time

from ..settings import load_settings

log = logging.getLogger("changewise.ai")


class ProviderError(RuntimeError):
    """The provider is missing, slow, unreachable or returned something unusable."""


class Provider:
    name = "base"

    def complete_json(self, prompt, schema=None):
        """Return the JSON object produced for the prompt, or raise ProviderError."""
        raise NotImplementedError


class GeminiProvider(Provider):
    """Google Gen AI SDK, Interactions API with structured output. Nothing is stored on Google's side."""
    ATTEMPTS = 2  # the SDK retries rate limits, server errors and dropped connections

    def __init__(self, api_key, model, timeout, client=None, **options):
        self.name = f"gemini:{model}"
        self._model, self._timeout = model, timeout
        if client is None:
            from google import genai  # only the cloud backend and a keyed demo need the SDK
            client = genai.Client(api_key=api_key, http_options={
                "retry_options": {"attempts": self.ATTEMPTS, "initial_delay": 1.0}, **options})
        self._client = client

    def complete_json(self, prompt, schema=None):
        wanted = {"type": "text", "mime_type": "application/json", **({"schema": schema} if schema else {})}
        started = time.perf_counter()
        try:
            reply = self._client.interactions.create(
                model=self._model, input=prompt, response_format=wanted, store=False, timeout=self._timeout)
            text = reply.output_text
        except Exception as error:  # the SDK has no single public base class for its failures
            status = getattr(error, "status_code", None)
            log.warning("ai_call_failed", extra={"fields": {"provider": self.name, "status": status,
                                                            "error": type(error).__name__}})
            # only the type and status: a message could echo the request
            raise ProviderError(f"{self.name}: {f'HTTP {status}' if status else type(error).__name__}") from error
        usage = getattr(reply, "usage", None)
        log.info("ai_call", extra={"fields": {
            "provider": self.name, "ms": round((time.perf_counter() - started) * 1000),
            "tokens": getattr(usage, "total_tokens", None)}})
        return parse_json_object(text)


def parse_json_object(text):
    try:
        value = json.loads(text)
    except (ValueError, TypeError) as error:
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
