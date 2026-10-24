"""
agents/faults.py – Fault Injection Framework for TrustTest (Phase 4)
====================================================================
Controlled fault simulation for testing and demo video demonstrations.
Activated via the TRUSTTEST_FAULT environment variable.

Supported fault values:
  - data_live_fail: Live yfinance fetch fails, forcing local cache fallback
  - data_fail: Data agent fails completely, returning ok=False
  - backtest_fail: Backtest engine fails with computation error
  - skeptic_timeout: Skeptic agent sleeps past timeout, triggering unvalidated partial result
  - llm_fail: ASI:One LLM API raises connection error / 500
  - llm_badjson: LLM returns invalid / non-JSON prose

NEVER active in production unless explicitly set in .env or shell.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Optional

logger = logging.getLogger("trusttest.faults")

VALID_FAULTS = {
    "data_live_fail",
    "data_fail",
    "backtest_fail",
    "skeptic_timeout",
    "llm_fail",
    "llm_badjson",
}


def get_active_fault() -> Optional[str]:
    """Return the active fault name if valid, or None."""
    fault = os.getenv("TRUSTTEST_FAULT", "").strip().lower()
    return fault if fault in VALID_FAULTS else None


def is_fault_active(fault_name: str) -> bool:
    """Check if a specific fault is currently triggered."""
    return get_active_fault() == fault_name.lower()


def check_and_log_faults_startup(agent_name: str) -> None:
    """Log a loud warning if fault injection is active at agent startup."""
    fault = get_active_fault()
    if fault:
        logger.warning(
            "⚠️ [FAULT INJECTION ACTIVE] Agent '%s' has active fault simulation: '%s'!",
            agent_name,
            fault,
        )


def maybe_inject_fault(fault_name: str, delay_seconds: float = 0.0) -> None:
    """
    If the specified fault is active, log the event and perform the fault action
    (e.g. sleep, raise an exception).
    """
    if is_fault_active(fault_name):
        logger.warning("🚨 [FAULT INJECTION ACTIVE] Triggering simulated fault '%s'!", fault_name)
        if delay_seconds > 0:
            time.sleep(delay_seconds)
