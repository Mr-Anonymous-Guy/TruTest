"""
scripts/show_trace.py – TrustTest Pipeline Trace Visualizer (Phase 4)
====================================================================
Prints a clear, step-by-step execution timeline for the latest TrustTest
multi-agent pipeline run, showing each hop, its latency, and result details.

Usage:
    python scripts/show_trace.py latest
    python scripts/show_trace.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Safe utf-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def show_trace(trace_path: Path) -> None:
    if not trace_path.exists():
        print(f"No trace file found at: {trace_path}")
        print("Run a strategy request in ASI:One to generate a trace.")
        return

    try:
        data = json.loads(trace_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Error reading trace: {e}")
        return

    req_id = data.get("request_id", "N/A")
    timestamp = data.get("timestamp", "N/A")
    user_text = data.get("user_text", "")
    total_ms = data.get("total_latency_ms", 0.0)
    steps = data.get("steps", [])

    print("\n" + "=" * 80)
    print(f"  🛡️  TrustTest Pipeline Execution Trace: {req_id}")
    print("=" * 80)
    print(f"Timestamp: {timestamp}")
    print(f"Query:     \"{user_text}\"")
    print("-" * 80)
    print(f"{'Hop':<4}  {'Agent':<22}  {'Status':<12}  {'Latency':<10}  {'Details'}")
    print(f"{'---':<4}  {'-' * 22}  {'-' * 12}  {'-' * 10}  {'-' * 26}")

    for s in steps:
        hop = s.get("hop", "-")
        agent = s.get("agent", "Unknown")
        status = s.get("status", "UNKNOWN")
        latency = f"{s.get('latency_ms', 0):.0f}ms"
        details = s.get("details", "")

        if status == "SUCCESS":
            status_str = "🟢 PASS"
        elif status == "DEGRADED":
            status_str = "⚠️ DEGRADED"
        elif status == "CLARIFICATION":
            status_str = "💬 CLARIFY"
        else:
            status_str = "🔴 FAIL"

        print(f"{hop:<4}  {agent:<22}  {status_str:<12}  {latency:<10}  {details}")

    print("-" * 80)
    print(f"Total Pipeline Latency: {total_ms:.0f}ms")
    print("=" * 80 + "\n")


def show_jsonl_trace(jsonl_path: Path, target_id: str) -> None:
    if not jsonl_path.exists():
        print(f"No trace log found at {jsonl_path}")
        return

    matching_events = []
    try:
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                    if ev.get("request_id") == target_id:
                        matching_events.append(ev)
                except Exception:
                    continue
    except Exception as e:
        print(f"Error reading {jsonl_path}: {e}")
        return

    if not matching_events:
        print(f"No trace events found matching request_id '{target_id}' in {jsonl_path.name}")
        return

    print("\n" + "=" * 80)
    print(f"  🛡️  TrustTest Pipeline Execution Trace: {target_id}")
    print("=" * 80)
    print(f"{'Step':<24}  {'Status':<12}  {'Attempt':<8}  {'Latency':<10}  {'Details'}")
    print(f"{'-' * 24}  {'-' * 12}  {'-' * 8}  {'-' * 10}  {'-' * 20}")

    total_ms = 0.0
    for ev in matching_events:
        step = ev.get("step", "-")
        status = ev.get("status", "UNKNOWN")
        attempt = ev.get("attempt", 1)
        latency = f"{ev.get('elapsed_ms', 0):.0f}ms"
        total_ms += ev.get("elapsed_ms", 0.0)
        note = ev.get("note", "")

        if status == "ok" or status == "SUCCESS":
            status_str = "🟢 PASS"
        elif status == "degraded" or status == "DEGRADED":
            status_str = "⚠️ DEGRADED"
        elif status == "user_error":
            status_str = "💬 USER_ERR"
        elif status == "timeout":
            status_str = "⏱️ TIMEOUT"
        else:
            status_str = "🔴 FAIL"

        print(f"{step:<24}  {status_str:<12}  {attempt:<8}  {latency:<10}  {note}")

    print("-" * 80)
    print(f"Cumulative Hop Latency: {total_ms:.0f}ms")
    print("=" * 80 + "\n")


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    logs_dir = root / "logs"

    arg = sys.argv[1].strip() if len(sys.argv) > 1 else "latest"

    if arg == "latest":
        show_trace(logs_dir / "latest_trace.json")
    else:
        show_jsonl_trace(logs_dir / "trace.jsonl", arg)


if __name__ == "__main__":
    main()
