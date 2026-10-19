"""Swappable language-model providers. The engine never depends on one vendor.

NullProvider   - no AI: callers fall back to code-only behaviour.
FakeProvider   - fixed answers, for tests.
GeminiProvider - Google Gemini REST API (free tier). Key comes from the GEMINI_API_KEY environment variable
                 (read from engine/.env, which git ignores). The key is never logged or sent anywhere but Google.
Only summaries are ever sent: column names and statistics, never rows, customer names or free text.
"""
from __future__ import annotations
import json
import os
import time
import urllib.error
import urllib.request


class ProviderError(RuntimeError):
    pass


class Provider:
    name = "base"

    def complete_json(self, system: str, payload: dict) -> dict:
        raise NotImplementedError


class NullProvider(Provider):
    name = "none"

    def complete_json(self, system: str, payload: dict) -> dict:
        raise ProviderError("No AI provider configured.")


class FakeProvider(Provider):
    name = "fake"

    def __init__(self, answer: dict | None = None, fail: bool = False):
        self.answer, self.fail, self.calls = answer or {}, fail, []

    def complete_json(self, system: str, payload: dict) -> dict:
        self.calls.append(payload)
        if self.fail:
            raise ProviderError("simulated outage")
        return self.answer


class GeminiProvider(Provider):
    name = "gemini"

    def __init__(self, api_key: str | None = None, model: str | None = None, timeout: int = 40):
        self.key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self.model = model or os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
        self.timeout = timeout
        if not self.key:
            raise ProviderError("GEMINI_API_KEY is not set.")

    def complete_json(self, system: str, payload: dict) -> dict:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        body = json.dumps({
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": json.dumps(payload)}]}],
            "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
        }).encode()
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json", "x-goog-api-key": self.key})
        last: Exception | None = None
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    data = json.load(r)
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                return json.loads(text)
            except urllib.error.HTTPError as e:
                last = e
                if e.code in (429, 500, 503):
                    time.sleep(2 * (attempt + 1))
                    continue
                break
            except (urllib.error.URLError, KeyError, IndexError, json.JSONDecodeError, TimeoutError) as e:
                last = e
                time.sleep(1)
        raise ProviderError(f"Gemini call failed: {type(last).__name__}")


def default_provider() -> Provider:
    """Gemini when a key exists, otherwise no AI (the engine still works)."""
    try:
        return GeminiProvider()
    except ProviderError:
        return NullProvider()


class ScriptedProvider(Provider):
    """Test double: returns the given answers in order (a callable answer receives the payload)."""
    name = "scripted"

    def __init__(self, answers: list):
        self.answers, self.calls = list(answers), []

    def complete_json(self, system: str, payload: dict) -> dict:
        self.calls.append({"system": system, "payload": payload})
        if not self.answers:
            raise ProviderError("script exhausted")
        a = self.answers.pop(0)
        return a(payload) if callable(a) else a
