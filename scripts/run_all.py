"""
scripts/run_all.py – TrustTest Multi-Agent Process Manager

Starts all 5 TrustTest uAgents as background subprocesses, redirecting logs to
logs/<agent>.log, and prints each agent's Bech32 address and Inspector URL.

Note: In development and for manual mailbox connection, agents can also be started
individually in separate terminals. This script provides convenient multi-process orchestration.
"""

from __future__ import annotations

import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

# Safe utf-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Add project root to sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

LOGS_DIR = ROOT / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

AGENTS = [
    ("Orchestrator", ROOT / "agents" / "orchestrator.py", LOGS_DIR / "orchestrator.log", 8001),
    ("Parser", ROOT / "agents" / "parser_agent.py", LOGS_DIR / "parser.log", 8005),
    ("Data", ROOT / "agents" / "data_agent.py", LOGS_DIR / "data.log", 8002),
    ("Backtest", ROOT / "agents" / "backtest_agent.py", LOGS_DIR / "backtest.log", 8003),
    ("Skeptic", ROOT / "agents" / "skeptic_agent.py", LOGS_DIR / "skeptic.log", 8004),
]


def extract_info(log_path: Path) -> tuple[str, str]:
    """Scan log file for agent address and inspector URL."""
    address, inspector_url = "Starting...", "Starting..."
    if not log_path.exists():
        return address, inspector_url

    try:
        content = log_path.read_text(encoding="utf-8", errors="replace")
        addr_match = re.search(r"Starting agent with address:\s*(agent1[0-9a-z]+)", content)
        if addr_match:
            address = addr_match.group(1)

        insp_match = re.search(r"Agent inspector available at\s*(https://agentverse\.ai/inspect/\?[^\s\n]+)", content)
        if insp_match:
            inspector_url = insp_match.group(1)
    except Exception:
        pass

    return address, inspector_url


def main():
    print("=" * 80)
    print("  🛡️  TrustTest Multi-Agent Runner (Fetch-A-Thon 3.0)")
    print("=" * 80)
    print("Launching 5 worker agents...")

    python_exe = sys.executable
    processes: list[subprocess.Popen] = []

    try:
        for name, script_path, log_path, port in AGENTS:
            # Truncate old log file
            log_file = open(log_path, "w", encoding="utf-8")
            proc = subprocess.Popen(
                [python_exe, str(script_path)],
                cwd=str(ROOT),
                stdout=log_file,
                stderr=subprocess.STDOUT,
            )
            processes.append(proc)
            print(f"  • Started {name:<12} (PID: {proc.pid}) on port {port} -> {log_path.name}")

        print("\nWaiting for agents to initialize and register...")
        time.sleep(4.0)

        print("\n" + "=" * 80)
        print("  ACTIVE AGENT ENDPOINTS & INSPECTOR URLS")
        print("=" * 80)
        fmt = "{:<12} | {:<20} | {:<42}"

        for name, _, log_path, port in AGENTS:
            addr, insp = extract_info(log_path)
            print(f"\n[{name} Agent - Port {port}]")
            print(f"  Address:   {addr}")
            print(f"  Inspector: {insp}")

        print("\n" + "=" * 80)
        print("All 5 agents running. Press CTRL+C to terminate all processes.")
        print("=" * 80)

        while True:
            time.sleep(1.0)

    except KeyboardInterrupt:
        print("\nShutting down all agents...")
    finally:
        for p in processes:
            try:
                p.terminate()
                p.wait(timeout=2.0)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass
        print("All processes terminated cleanly.")


if __name__ == "__main__":
    main()
