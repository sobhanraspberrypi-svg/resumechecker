"""
CVRadar
Unified LLM Provider Adapter
src/llm_provider.py

Abstracts Gemini / Claude / OpenAI behind one interface.
All tracks that need an LLM call go through this module.

Key design decisions:
- One call_llm() method regardless of provider
- Identical retry logic for all providers (5 attempts, capped 30s backoff)
- 45-second per-request timeout on all calls
- Adaptive pacing: configurable inter-request delay to reduce 429/503
- Health check before main loop to surface provider issues early
- Graceful degradation: on permanent failure returns None so the
  caller can fall back to Track 1 local scoring
- Thinking capped on Gemini flash/pro (0 / 128 tokens)
- Structured JSON output enforced on all providers
"""

import json
import re
import time
import threading
from typing import Optional, Type

from pydantic import BaseModel


# =====================================================
# PROVIDER CONSTANTS
# =====================================================

GEMINI = "Gemini"
CLAUDE = "Claude"
OPENAI = "OpenAI"

PROVIDER_MODELS = {
    GEMINI: [
        "gemini-2.5-flash",
        "gemini-2.5-pro",
    ],
    CLAUDE: [
        "claude-haiku-4-5-20251001",
        "claude-sonnet-4-6",
    ],
    OPENAI: [
        "gpt-4o-mini",
        "gpt-4o",
    ],
}

# Display names for UI dropdown (model_id -> display_name)
MODEL_DISPLAY = {
    "gemini-2.5-flash": "Gemini 2.5 Flash (fast, cheap)",
    "gemini-2.5-pro": "Gemini 2.5 Pro (powerful)",
    "claude-haiku-4-5-20251001": "Claude Haiku 4.5 (fast, cheap)",
    "claude-sonnet-4-6": "Claude Sonnet 4.6 (balanced)",
    "gpt-4o-mini": "GPT-4o Mini (fast, cheap)",
    "gpt-4o": "GPT-4o (powerful)",
}

MAX_RETRIES = 5
BASE_DELAY = 5       # seconds
MAX_DELAY = 30       # cap exponential backoff here
REQUEST_TIMEOUT = 45  # seconds per call
INTER_REQUEST_DELAY = 1.5  # seconds between calls (rate limit protection)


# =====================================================
# TRANSIENT ERROR DETECTION
# =====================================================

def _is_transient(error_str: str) -> bool:
    keywords = [
        "503", "429", "500", "502", "504",
        "unavailable", "overload", "overloaded",
        "rate limit", "rate_limit", "too many requests",
        "high demand", "capacity", "timeout",
        "connection", "server error", "internal error",
        "temporarily", "try again",
    ]
    low = error_str.lower()
    return any(k in low for k in keywords)


# =====================================================
# JSON EXTRACTION HELPER
# =====================================================

def _extract_json(text: str) -> dict:
    """
    Attempts to parse JSON from model output.
    Handles markdown fences, leading/trailing text.
    """
    # Strip markdown fences
    text = re.sub(r"```(?:json)?", "", text).strip()
    text = text.strip("`").strip()

    # Try direct parse
    try:
        return json.loads(text)
    except Exception:
        pass

    # Find first {...} block
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except Exception:
            pass

    raise ValueError(f"No valid JSON found in model response: {text[:200]}")


# =====================================================
# TIMEOUT WRAPPER
# =====================================================

class _TimeoutError(Exception):
    pass


def _call_with_timeout(fn, timeout, *args, **kwargs):
    result = [None]
    error = [None]

    def target():
        try:
            result[0] = fn(*args, **kwargs)
        except Exception as e:
            error[0] = e

    t = threading.Thread(target=target, daemon=True)
    t.start()
    t.join(timeout)

    if t.is_alive():
        raise _TimeoutError(
            f"Request timed out after {timeout}s"
        )

    if error[0] is not None:
        raise error[0]

    return result[0]


# =====================================================
# GEMINI ADAPTER
# =====================================================

def _thinking_config(model: str) -> dict:
    if "pro" in model.lower():
        return {"thinking_budget": 128}
    return {"thinking_budget": 0}


def _call_gemini(
    api_key: str,
    model: str,
    prompt: str,
    response_schema: Type[BaseModel],
) -> dict:
    from google import genai

    client = genai.Client(api_key=api_key)

    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config={
            "response_mime_type": "application/json",
            "response_schema": response_schema,
            "temperature": 0.1,
            "thinking_config": _thinking_config(model),
        },
    )

    if response.parsed is not None:
        return response.parsed.model_dump()

    return _extract_json(response.text)


# =====================================================
# CLAUDE ADAPTER
# =====================================================

def _call_claude(
    api_key: str,
    model: str,
    prompt: str,
    response_schema: Type[BaseModel],
) -> dict:
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)

    schema_json = json.dumps(
        response_schema.model_json_schema(), indent=2
    )

    system_prompt = (
        f"You are a structured data extraction assistant. "
        f"Respond ONLY with a valid JSON object matching this schema "
        f"exactly. Do not include any explanation, markdown, or text "
        f"outside the JSON object.\n\nSchema:\n{schema_json}"
    )

    message = client.messages.create(
        model=model,
        max_tokens=2048,
        system=system_prompt,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text
    return _extract_json(raw)


# =====================================================
# OPENAI ADAPTER
# =====================================================

def _call_openai(
    api_key: str,
    model: str,
    prompt: str,
    response_schema: Type[BaseModel],
) -> dict:
    from openai import OpenAI

    client = OpenAI(api_key=api_key)

    schema_json = json.dumps(
        response_schema.model_json_schema(), indent=2
    )

    system_prompt = (
        f"You are a structured data extraction assistant. "
        f"Respond ONLY with a valid JSON object matching this schema "
        f"exactly. Do not include any explanation, markdown, or text "
        f"outside the JSON object.\n\nSchema:\n{schema_json}"
    )

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
    )

    raw = response.choices[0].message.content
    return _extract_json(raw)


# =====================================================
# UNIFIED PROVIDER
# =====================================================

class LLMProvider:
    """
    Single interface for all LLM calls across Gemini, Claude, OpenAI.

    Usage:
        provider = LLMProvider(provider="Gemini", model="gemini-2.5-flash",
                               api_key="...")
        result_dict = provider.call(prompt, ResponseSchema)
        # result_dict is a plain dict; cast to schema with Schema(**result_dict)
    """

    def __init__(
        self,
        provider: str,
        model: str,
        api_key: str,
        inter_request_delay: float = INTER_REQUEST_DELAY,
    ):
        if provider not in (GEMINI, CLAUDE, OPENAI):
            raise ValueError(f"Unknown provider: {provider}")

        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.inter_request_delay = inter_request_delay

        self._adapter = {
            GEMINI: _call_gemini,
            CLAUDE: _call_claude,
            OPENAI: _call_openai,
        }[provider]

    # --------------------------------------------------
    # HEALTH CHECK
    # --------------------------------------------------

    def health_check(self) -> tuple:
        """
        Fires a minimal test call before the main loop.
        Returns (ok: bool, message: str).
        """
        try:
            test_schema = type(
                "Ping",
                (BaseModel,),
                {"__annotations__": {"ok": bool}},
            )
            _call_with_timeout(
                self._adapter,
                REQUEST_TIMEOUT,
                self.api_key,
                self.model,
                "Reply with JSON: {\"ok\": true}",
                test_schema,
            )
            return True, f"{self.provider} ({self.model}) is reachable."

        except _TimeoutError:
            return False, (
                f"{self.provider} timed out during health check. "
                "The service may be under high load."
            )
        except Exception as e:
            return False, f"{self.provider} health check failed: {str(e)[:120]}"

    # --------------------------------------------------
    # MAIN CALL (with retry + pacing)
    # --------------------------------------------------

    def call(
        self,
        prompt: str,
        response_schema: Type[BaseModel],
        graceful: bool = True,
    ) -> Optional[dict]:
        """
        Makes one LLM call with retries and backoff.

        Args:
            prompt: The full prompt string.
            response_schema: Pydantic model class describing output shape.
            graceful: If True, returns None on permanent failure
                      (caller should fall back to Track 1).
                      If False, raises the exception.

        Returns:
            dict with model fields, or None on graceful failure.
        """
        delay = BASE_DELAY
        last_error = None

        for attempt in range(MAX_RETRIES):

            try:
                result = _call_with_timeout(
                    self._adapter,
                    REQUEST_TIMEOUT,
                    self.api_key,
                    self.model,
                    prompt,
                    response_schema,
                )

                # Inter-request pacing (after successful call too)
                time.sleep(self.inter_request_delay)
                return result

            except _TimeoutError as e:
                last_error = e
                # Timeout is always transient — retry with backoff
                if attempt < MAX_RETRIES - 1:
                    time.sleep(min(delay, MAX_DELAY))
                    delay = min(delay * 2, MAX_DELAY)
                continue

            except Exception as e:
                last_error = e
                transient = _is_transient(str(e))

                if transient and attempt < MAX_RETRIES - 1:
                    time.sleep(min(delay, MAX_DELAY))
                    delay = min(delay * 2, MAX_DELAY)
                    continue

                # Permanent error (bad key, schema error, etc.)
                if graceful:
                    return None
                raise e

        # Exhausted all retries
        if graceful:
            return None
        if last_error:
            raise last_error
        return None
