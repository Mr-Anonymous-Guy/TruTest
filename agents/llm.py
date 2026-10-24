"""
agents/llm.py – ASI:One LLM Client (OpenAI-compatible)

Communicates with the ASI:One chat completions API using OpenAI client or requests.
Reads ASI_ONE_API_KEY, ASI_ONE_BASE_URL, and ASI_ONE_MODEL from the environment.
Logs latency and never logs API keys.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional
import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("trusttest.llm")

DEFAULT_BASE_URL = "https://api.asi1.ai/v1"
DEFAULT_MODEL = "asi1"


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


def call_llm(
    messages: List[Dict[str, str]],
    temperature: float = 0.0,
    timeout: int = 20,
    max_retries: int = 1,
) -> Optional[str]:
    """
    Call the ASI:One chat completion endpoint.
    Returns the string content of the response message, or raises an error.
    """
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
                    return choices[0].get("message", {}).get("content", "")
                raise ValueError("No choices returned from ASI:One API.")
            else:
                resp.raise_for_status()
        except Exception as exc:
            elapsed = time.perf_counter() - t0
            logger.warning("ASI:One LLM call attempt %d failed in %.2fs: %s", attempt + 1, elapsed, exc)
            last_exc = exc
            if attempt < max_retries:
                time.sleep(1.0)

    raise last_exc or RuntimeError("ASI:One LLM call failed after retries.")
