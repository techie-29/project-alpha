"""Swappable language-model providers. The engine never depends on one vendor.

NullProvider   - no AI: callers fall back to code-only behaviour.
FakeProvider   - fixed answers, for tests.
OpenRouterProvider - OpenRouter (DeepSeek etc.), key from OPENROUTER_API_KEY.
GeminiProvider - Google Gemini REST API (free tier). Key comes from the GEMINI_API_KEY environment variable
                 (read from engine/.env, which git ignores). The key is never logged or sent anywhere but Google.
Only summaries are ever sent: column names and statistics, never rows, customer names or free text.
"""
from __future__ import annotations
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request


class ProviderError(RuntimeError):
    pass


class ProviderFatal(ProviderError):
    """An error that retrying cannot fix (no credit, bad key, unknown model). The provider switches itself off for the
    rest of the analysis so nothing keeps calling it, and the message says what to do."""


class BudgetExceeded(ProviderError):
    """The per-analysis call or cost limit was reached; callers fall back to what they already have."""


FATAL_HELP = {401: "The OpenRouter key was refused. Check OPENROUTER_API_KEY in engine/.env.",
              402: "The OpenRouter account has run out of credit. Add credit at openrouter.ai/settings/credits, or lower AI_MAX_TOKENS in engine/.env.",
              403: "OpenRouter refused this request for this key or model (check the model's access and your account's limits).",
              404: "The model name was not found on OpenRouter. Check OPENROUTER_MODEL in engine/.env."}


_LOCK = threading.Lock()

# How hard the model thinks at each step. Most of the AI's time goes into thinking, and picking calculations or checking
# a column's meaning needs little of it; writing the findings gets more. AI_REASONING in engine/.env overrides all steps
# (low | medium | high), or 'model' leaves it to the model's own default.
# In this app the AI writes its own code at 'understand', 'plan', 'dig' and 'fix_setup', so those keep medium thinking:
# a bug costs a retry, which is slower than the thinking saved. Steps not listed use the model's own default.
STEP_EFFORT = {"understand": "medium", "fix_setup": "medium", "plan": "medium", "dig": "medium", "write": "medium",
               "ask-plan": "medium", "ask-answer": "medium", "read-columns": "low", "read-meanings": "low", "check": "low"}


class Meter:
    """What one analysis spent on the AI: calls, tokens, cost, time, and the limits that stop it."""

    def __init__(self, max_calls: int | None = None, max_cost: float | None = None):
        self.max_calls = int(os.environ.get("AI_MAX_CALLS", "60")) if max_calls is None else max_calls
        self.max_cost = float(os.environ.get("AI_MAX_COST_USD", "0.50")) if max_cost is None else max_cost
        self.calls = self.failed = 0
        self.tokens_in = self.tokens_out = 0
        self.cost = 0.0
        self.seconds = 0.0
        self.log: list[dict] = []

    def check(self) -> None:
        if self.calls >= self.max_calls:
            raise BudgetExceeded(f"AI call limit reached ({self.max_calls} calls for this analysis; AI_MAX_CALLS in engine/.env).")
        if self.cost >= self.max_cost:
            raise BudgetExceeded(f"AI cost limit reached (${self.cost:.3f} of ${self.max_cost:.2f} for this analysis; AI_MAX_COST_USD in engine/.env).")

    def add(self, purpose: str, seconds: float, tin: int | None, tout: int | None, cost: float | None, error: str | None = None) -> None:
        with _LOCK:                                   # calls may finish at the same time (several asked at once)
            self._add(purpose, seconds, tin, tout, cost, error)

    def _add(self, purpose, seconds, tin, tout, cost, error) -> None:
        self.calls += 1
        self.failed += 1 if error else 0
        self.tokens_in += int(tin or 0); self.tokens_out += int(tout or 0)
        self.cost += float(cost or 0.0); self.seconds += seconds
        self.log.append({"purpose": purpose, "seconds": round(seconds, 1), "in": tin, "out": tout, "cost": cost, **({"error": error[:160]} if error else {})})

    def summary(self) -> dict:
        return {"calls": self.calls, "failed": self.failed, "tokens_in": self.tokens_in, "tokens_out": self.tokens_out, "cost_usd": round(self.cost, 5),
                "seconds": round(self.seconds, 1), "limits": {"calls": self.max_calls, "cost_usd": self.max_cost}, "log": self.log[-80:]}


class Provider:
    name = "base"
    model = ""

    def __init__(self):
        self.meter = Meter()
        self.disabled: str | None = None

    def complete_json(self, system: str, payload: dict, purpose: str = "") -> dict:
        raise NotImplementedError


class NullProvider(Provider):
    name = "none"

    def complete_json(self, system: str, payload: dict, purpose: str = "") -> dict:
        raise ProviderError("No AI provider configured.")


class FakeProvider(Provider):
    name = "fake"

    def __init__(self, answer: dict | None = None, fail: bool = False):
        super().__init__()
        self.answer, self.fail, self.calls = answer or {}, fail, []

    def complete_json(self, system: str, payload: dict, purpose: str = "") -> dict:
        self.meter.check()
        self.meter.add(purpose, 0.0, 0, 0, 0.0)
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
        super().__init__()
        self.key = (api_key or os.environ.get("GEMINI_API_KEY", "")).strip()
        self.model = (model or os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")).strip()
        self.timeout = timeout
        self.min_interval = float(os.environ.get("GEMINI_MIN_INTERVAL", "1.0"))
        if not self.key:
            raise ProviderError("GEMINI_API_KEY is not set.")

    def complete_json(self, system: str, payload: dict, purpose: str = "") -> dict:
        if self.disabled:
            raise ProviderFatal(self.disabled)
        self.meter.check()
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
            with _LOCK:
                start = max(time.time(), GeminiProvider._last_call + self.min_interval)
                GeminiProvider._last_call = start
            if start > time.time():
                time.sleep(start - time.time())
            req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json", "x-goog-api-key": self.key})
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    data = json.load(r)
                cand = (data.get("candidates") or [{}])[0]
                parts = (cand.get("content") or {}).get("parts") or []
                text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
                um = data.get("usageMetadata") or {}
                self.meter.add(purpose, 0.0, um.get("promptTokenCount"), um.get("candidatesTokenCount"), None, None if text else "empty answer")
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
                if e.code in (400, 401, 403, 404):          # bad key / no access / unknown model: retrying will not help
                    self.disabled = f"Gemini refused the request ({last}). Check GEMINI_API_KEY and GEMINI_MODEL in engine/.env."
                    raise ProviderFatal(self.disabled)
                break
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


class OpenRouterProvider(Provider):
    """OpenRouter (OpenAI-style chat API). Reaches DeepSeek and many other models with one key.
    Env: OPENROUTER_API_KEY, OPENROUTER_MODEL (default deepseek/deepseek-chat), AI_MAX_TOKENS (default 8192),
    AI_REASONING (low | medium | high | model; default: per step, see STEP_EFFORT), AI_TIMEOUT (seconds), AI_MAX_CALLS and AI_MAX_COST_USD (limits per analysis)."""
    name = "openrouter"
    _last_call = 0.0

    def __init__(self, api_key: str | None = None, model: str | None = None, timeout: int | None = None):
        super().__init__()
        self.key = (api_key or os.environ.get("OPENROUTER_API_KEY", "")).strip()
        self.model = (model or os.environ.get("OPENROUTER_MODEL", "deepseek/deepseek-chat")).strip()
        # long enough for a slow answer to arrive: a call cut off at the limit is asked again from the start, which
        # doubles the wait instead of saving it
        self.timeout = timeout or int(os.environ.get("AI_TIMEOUT", "300"))
        self.min_interval = float(os.environ.get("AI_MIN_INTERVAL", "1.0"))
        self.max_tokens = int(os.environ.get("AI_MAX_TOKENS", "8192"))
        self.reasoning = os.environ.get("AI_REASONING", "").strip().lower()
        if not self.key:
            raise ProviderError("OPENROUTER_API_KEY is not set.")

    def effort(self, purpose: str = "") -> str | None:
        if self.reasoning in ("low", "medium", "high"):
            return self.reasoning
        if self.reasoning in ("model", "default", "off", "none"):
            return None
        return STEP_EFFORT.get(purpose)

    def _body(self, system: str, text_in: str, max_tokens: int, force_low: bool = False, purpose: str = "") -> bytes:
        b = {"model": self.model,
             "messages": [{"role": "system", "content": system + "\nReply with one JSON object only."}, {"role": "user", "content": text_in}],
             "temperature": 0.2, "max_tokens": max_tokens, "response_format": {"type": "json_object"}, "usage": {"include": True}}
        e = "low" if force_low else self.effort(purpose)      # force_low: the model ran out of room while thinking
        if e:
            b["reasoning"] = {"effort": e}
        return json.dumps(b).encode()

    def complete_json(self, system: str, payload: dict, purpose: str = "") -> dict:
        if self.disabled:
            raise ProviderFatal(self.disabled)
        self.meter.check()
        url = "https://openrouter.ai/api/v1/chat/completions"
        text_in = json.dumps(payload, default=_jsonable)
        if len(text_in) > 300_000:
            text_in = text_in[:300_000]
        max_tokens = self.max_tokens
        cap = int(os.environ.get("AI_MAX_TOKENS_CAP", "32000"))
        force_low = False
        last, t0 = "unknown error", time.time()
        for attempt in range(4):
            with _LOCK:                                # calls asked at once still start at least min_interval apart
                start = max(time.time(), OpenRouterProvider._last_call + self.min_interval)
                OpenRouterProvider._last_call = start
            if start > time.time():
                time.sleep(start - time.time())
            req = urllib.request.Request(url, data=self._body(system, text_in, max_tokens, force_low, purpose), headers={
                "Content-Type": "application/json", "Authorization": f"Bearer {self.key}", "X-Title": "Project Alpha"})
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    data = json.load(r)
                u = data.get("usage") or {}
                if data.get("error"):
                    last = str((data["error"] or {}).get("message", "error"))[:160]
                    time.sleep(3 * (attempt + 1))
                    continue
                text = ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
                self.meter.add(purpose, time.time() - t0, u.get("prompt_tokens"), u.get("completion_tokens"), u.get("cost"),
                               None if text.strip() else "empty answer")
                cut_short = ((data.get("choices") or [{}])[0].get("finish_reason") == "length"
                             or (u.get("completion_tokens") or 0) >= 0.9 * max_tokens)
                if not text.strip():
                    last = "empty answer (ran out of room while thinking)" if cut_short else "empty answer"
                    self.meter.check()
                    if cut_short and max_tokens < cap:
                        max_tokens, force_low = min(max_tokens * 2, cap), True      # retry with more room and less thinking
                    continue
                try:
                    return parse_json_text(text)
                except (json.JSONDecodeError, ValueError):
                    last = "the answer was cut off" if cut_short else "the answer was not valid JSON"
                    self.meter.check()
                    if cut_short and max_tokens < cap:
                        max_tokens, force_low = min(max_tokens * 2, cap), True
                    continue
            except urllib.error.HTTPError as e:
                raw = e.read().decode("utf-8", "replace")
                try:
                    detail = json.loads(raw).get("error", {})
                except Exception:
                    detail = {}
                msg = str(detail.get("message", ""))[:200]
                last = f"HTTP {e.code} {msg}".strip()
                if e.code == 402:
                    m = re.search(r"can only afford (\d+)", msg)
                    if m and int(m.group(1)) >= 1500 and max_tokens > int(m.group(1)) and attempt == 0:
                        max_tokens = int(m.group(1)) - 64              # enough credit for a shorter answer: try once more
                        continue
                if e.code in FATAL_HELP:
                    self.disabled = FATAL_HELP[e.code] + f" ({last})"
                    self.meter.add(purpose, time.time() - t0, None, None, None, last)
                    raise ProviderFatal(self.disabled)
                if e.code in (429, 500, 502, 503, 504):
                    time.sleep(4 * (attempt + 1))
                    continue
                break
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                last = f"network: {type(e).__name__}"
                time.sleep(2)
            except (KeyError, IndexError) as e:
                last = f"unreadable answer: {type(e).__name__}"
        self.meter.add(purpose, time.time() - t0, None, None, None, last)
        raise ProviderError(f"OpenRouter call failed: {last}")

    def check(self) -> dict:
        try:
            r = self.complete_json("Reply only with JSON.", {"task": "reply with {\"ok\": true}"}, "check")
            return {"ok": bool(r.get("ok", True)), "model": self.model}
        except ProviderError as e:
            return {"ok": False, "model": self.model, "error": str(e)}


def default_provider() -> Provider:
    """OpenRouter if its key exists, else Gemini if its key exists, else no AI (the engine still works)."""
    for cls in (OpenRouterProvider, GeminiProvider):
        try:
            return cls()
        except ProviderError:
            continue
    return NullProvider()


class ScriptedProvider(Provider):
    """Test double: returns the given answers in order (a callable answer receives the payload)."""
    name = "scripted"

    def __init__(self, answers: list):
        super().__init__()
        self.answers, self.calls = list(answers), []

    def complete_json(self, system: str, payload: dict, purpose: str = "") -> dict:
        self.meter.check()
        self.meter.add(purpose, 0.0, 0, 0, 0.0)
        self.calls.append({"system": system, "payload": payload, "purpose": purpose})
        if not self.answers:
            raise ProviderError("script exhausted")
        a = self.answers.pop(0)
        return a(payload) if callable(a) else a
