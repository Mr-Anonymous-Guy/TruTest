"""
agents/trace.py – Step-by-Step Pipeline Trace Logger with Rotation
=================================================================
Writes structured audit trail events for every inter-agent hop.
Guarantees max size (~5MB) with automatic rotation.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("trusttest.trace")

MAX_TRACE_LOG_BYTES = 5 * 1024 * 1024  # 5 MB


def _get_logs_dir() -> Path:
    root = Path(__file__).resolve().parent.parent
    logs_dir = root / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir


def record_hop_event(
    request_id: str,
    sender: str,
    step: str,
    status: str,
    elapsed_ms: float,
    attempt: int = 1,
    note: Optional[str] = None,
) -> None:
    """
    Append a structured JSON line trace to logs/trace.jsonl.
    Rotates logs/trace.jsonl to logs/trace.jsonl.1 if size > 5 MB.
    """
    logs_dir = _get_logs_dir()
    trace_file = logs_dir / "trace.jsonl"

    short_sender = sender
    if len(sender) > 16:
        short_sender = f"{sender[:8]}...{sender[-6:]}"

    event = {
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
        "request_id": request_id,
        "sender": short_sender,
        "step": step,
        "attempt": attempt,
        "status": status,
        "elapsed_ms": round(elapsed_ms, 1),
        "note": note or "",
    }

    try:
        # Check size rotation
        if trace_file.exists() and trace_file.stat().st_size >= MAX_TRACE_LOG_BYTES:
            backup = logs_dir / "trace.jsonl.1"
            if backup.exists():
                backup.unlink()
            trace_file.rename(backup)

        with open(trace_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")
    except Exception as exc:
        logger.warning("Failed to append trace event: %s", exc)


def save_full_pipeline_trace(
    request_id: str,
    sender: str,
    user_text: str,
    steps: List[Dict[str, Any]],
    total_elapsed_ms: float,
) -> None:
    """
    Save the complete multi-hop execution record to logs/latest_trace.json
    for inspection via scripts/show_trace.py.
    """
    logs_dir = _get_logs_dir()
    latest_file = logs_dir / "latest_trace.json"

    short_sender = sender
    if len(sender) > 16:
        short_sender = f"{sender[:8]}...{sender[-6:]}"

    # Truncate user text to max 200 chars to avoid leaking massive payloads or secrets
    clean_text = (user_text[:200] + "...") if len(user_text) > 200 else user_text

    record = {
        "request_id": request_id,
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "sender": short_sender,
        "user_text": clean_text,
        "total_latency_ms": round(total_elapsed_ms, 1),
        "steps": steps,
    }

    try:
        latest_file.write_text(json.dumps(record, indent=2), encoding="utf-8")
    except Exception as exc:
        logger.warning("Failed to save latest trace: %s", exc)
