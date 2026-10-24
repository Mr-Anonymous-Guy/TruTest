"""
agents/llm.py – Resilient ASI:One LLM Client (Phase 4)
======================================================
Communicates with the ASI:One chat completions API with:
  1. Circuit breaker: 3 consecutive failures -> open circuit for 60s
  2. Transient retries (1 retry with 1.0s backoff for 429/5xx/timeout)
  3. Clean JSON and markdown code fence extraction
  4. Fault injection integration (TRUSTTEST_FAULT=llm_fail / llm_badjson)
  5. Safe secret handling (never logs API keys)
"""

from __future__ import annotations

import logging
import os
import re
import time
from typing import Any, Dict, List, Optional
import requests
from dotenv import load_dotenv

from agents.faults import is_fault_active

load_dotenv()

logger = logging.getLogger("trusttest.llm")

DEFAULT_BASE_URL = "https://api.asi1.ai/v1"
DEFAULT_MODEL = "asi1"

# Circuit Breaker State (In-Memory)
_consecutive_failures = 0
_circuit_open_until = 0.0


def reset_circuit_breaker() -> None:
    """Reset circuit breaker state (useful for tests)."""
    global _consecutive_failures, _circuit_open_until
    _consecutive_failures = 0
    _circuit_open_until = 0.0


def is_circuit_open() -> bool:
    """Return True if circuit breaker is currently open."""
    return time.time() < _circuit_open_until


def get_llm_config() -> Dict[str, str]:
    """Retrieve LLM configuration from environment variables."""
    api_key = os.getenv("ASI_ONE_API_KEY", "").strip()
    base_url = os.getenv("ASI_ONE_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    model = os.getenv("ASI_ONE_MODEL", DEFAULT_MODEL)
    return {
        "api_key": api_key,
        "base_url": base_url,
        "model": model,
    }


def clean_llm_json_response(raw_text: str) -> str:
    """
    Extract pure JSON from LLM response, stripping markdown code fences
    (e.g. ```json ... ```) and leading/trailing conversational text.
    """
    if not raw_text:
        return ""
    text = raw_text.strip()
    # Strip markdown code fences
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()

    # If wrapped in conversational prose, find outer { ... }
    brace_start = text.find("{")
    brace_end = text.rfind("}")
    if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
        return text[brace_start : brace_end + 1]

    return text


def call_llm(
    messages: List[Dict[str, str]],
    temperature: float = 0.0,
    timeout: int = 20,
    max_retries: int = 1,
) -> Optional[str]:
    """
    Call the ASI:One chat completion endpoint with circuit breaker and retry.
    Returns the string content of the response message, or raises an error.
    """
    global _consecutive_failures, _circuit_open_until

    # 1. Circuit breaker check
    if is_circuit_open():
        rem = round(_circuit_open_until - time.time(), 1)
        logger.warning("LLM Circuit Breaker is OPEN (skipping call for %ss).", rem)
        raise RuntimeError("Language service is temporarily unavailable (circuit breaker open).")

    # 2. Fault injection check
    if is_fault_active("llm_fail"):
        logger.warning("🚨 [FAULT INJECTION ACTIVE] Simulating LLM API failure (500).")
        _consecutive_failures += 1
        if _consecutive_failures >= 3:
            _circuit_open_until = time.time() + 60.0
        raise RuntimeError("[FAULT INJECTION ACTIVE] Simulated ASI:One API failure.")

    if is_fault_active("llm_badjson"):
        logger.warning("🚨 [FAULT INJECTION ACTIVE] Simulating malformed LLM response.")
        return "I am an AI assistant and I think you want to trade: {ticker: 'RELIANCE', invalid_json"

    config = get_llm_config()
    api_key = config["api_key"]
    if not api_key or api_key in ("REPLACE_WITH_ASI_ONE_KEY", "REPLACE_ME"):
        raise ValueError("ASI_ONE_API_KEY is not set or unconfigured in .env.")

    url = f"{config['base_url']}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": config["model"],
        "messages": messages,
        "temperature": temperature,
    }

    last_exc: Optional[Exception] = None
    for attempt in range(max_retries + 1):
        t0 = time.perf_counter()
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
            elapsed = time.perf_counter() - t0
            logger.info("ASI:One LLM call [%s] completed in %.2fs (status %d)", config["model"], elapsed, resp.status_code)

            if resp.status_code == 200:
                data = resp.json()
                choices = data.get("choices", [])
                if choices:
                    content = choices[0].get("message", {}).get("content", "")
                    # Successful call: reset breaker
                    _consecutive_failures = 0
                    _circuit_open_until = 0.0
                    return content
                raise ValueError("Empty choices list returned from ASI:One API.")
            elif resp.status_code in (429, 500, 502, 503, 504):
                # Transient error: retry
                logger.warning("ASI:One LLM returned HTTP %d on attempt %d", resp.status_code, attempt + 1)
                resp.raise_for_status()
            else:
                resp.raise_for_status()

        except Exception as exc:
            elapsed = time.perf_counter() - t0
            logger.warning("ASI:One LLM call attempt %d failed in %.2fs: %s", attempt + 1, elapsed, exc)
            last_exc = exc
            if attempt < max_retries:
                time.sleep(1.0 * (attempt + 1))

    # All attempts failed: increment failure counter
    _consecutive_failures += 1
    if _consecutive_failures >= 3:
        _circuit_open_until = time.time() + 60.0
        logger.error("LLM failed 3 consecutive times. Circuit breaker OPENED for 60 seconds.")

    raise last_exc or RuntimeError("ASI:One LLM call failed after retries.")
