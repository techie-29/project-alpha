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


def parse_json_text(text: str) -> dict:
    """Models sometimes wrap JSON in code fences or add a sentence around it; take the JSON object out."""
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        t = t[t.find("{"):] if "{" in t else t
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        a, b = t.find("{"), t.rfind("}")
        if a >= 0 and b > a:
            return json.loads(t[a:b + 1])
        raise


def _jsonable(o):
    try:
        import numpy as np
        if isinstance(o, np.integer):
            return int(o)
        if isinstance(o, np.floating):
            return float(o)
    except Exception:
        pass
    return str(o)


class GeminiProvider(Provider):
    name = "gemini"
    _last_call = 0.0

    def __init__(self, api_key: str | None = None, model: str | None = None, timeout: int = 60):
        self.key = (api_key or os.environ.get("GEMINI_API_KEY", "")).strip()
        self.model = (model or os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")).strip()
        self.timeout = timeout
        self.min_interval = float(os.environ.get("GEMINI_MIN_INTERVAL", "1.0"))
        if not self.key:
            raise ProviderError("GEMINI_API_KEY is not set.")

    def complete_json(self, system: str, payload: dict) -> dict:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        text_in = json.dumps(payload, default=_jsonable)
        if len(text_in) > 400_000:
            text_in = text_in[:400_000]
        body = json.dumps({
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": text_in}]}],
            "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json", "maxOutputTokens": 8192},
        }).encode()
        last = "unknown error"
        for attempt in range(4):
            wait = GeminiProvider._last_call + self.min_interval - time.time()
            if wait > 0:
                time.sleep(wait)
            GeminiProvider._last_call = time.time()
            req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json", "x-goog-api-key": self.key})
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    data = json.load(r)
                cand = (data.get("candidates") or [{}])[0]
                parts = (cand.get("content") or {}).get("parts") or []
                text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
                if not text:
                    last = f"empty answer (finish reason {cand.get('finishReason', 'unknown')})"
                    continue
                return parse_json_text(text)
            except urllib.error.HTTPError as e:
                try:
                    detail = json.loads(e.read().decode("utf-8", "replace")).get("error", {})
                except Exception:
                    detail = {}
                msg = str(detail.get("message", ""))[:160]
                last = f"HTTP {e.code} {msg}".strip()
                if e.code in (429, 500, 502, 503, 504):
                    delay = 4 * (attempt + 1)
                    for d in detail.get("details", []) or []:
                        rd = str(d.get("retryDelay", ""))
                        if rd.endswith("s"):
                            try:
                                delay = min(45.0, float(rd[:-1]) + 1)
                            except ValueError:
                                pass
                    time.sleep(delay)
                    continue
                break                                   # 400 bad key / 403 / 404 model: retrying will not help
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                last = f"network: {type(e).__name__}"
                time.sleep(2)
            except (json.JSONDecodeError, KeyError, IndexError, ValueError) as e:
                last = f"unreadable answer: {type(e).__name__}"
        raise ProviderError(f"Gemini call failed: {last}")

    def check(self) -> dict:
        try:
            r = self.complete_json("Reply only with JSON.", {"task": "reply with {\"ok\": true}"})
            return {"ok": bool(r.get("ok", True)), "model": self.model}
        except ProviderError as e:
            return {"ok": False, "model": self.model, "error": str(e)}


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
