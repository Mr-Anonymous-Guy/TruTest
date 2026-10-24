"""
scripts/run_all.py – TrustTest Multi-Agent Process Manager & Supervisor (Phase 4)
================================================================================
Starts all 5 TrustTest uAgents as supervised background subprocesses:
  1. Redirects logs to logs/<agent>.log
  2. Extracts and displays Bech32 addresses and Inspector URLs
  3. Supervisor Mode: automatically restarts crashed agents with exponential backoff
     (max 5 restarts per 10 minutes per agent)
  4. Note: Deterministic seeds ensure restarted agents retain identical addresses.
     Always verify mailbox reconnection in the agent log after a restart.
"""

from __future__ import annotations

import collections
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List

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


def launch_process(script_path: Path, log_path: Path, python_exe: str) -> subprocess.Popen:
    """Launch an agent process, appending logs."""
    log_file = open(log_path, "a", encoding="utf-8")
    proc = subprocess.Popen(
        [python_exe, str(script_path)],
        cwd=str(ROOT),
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )
    return proc


def main():
    print("=" * 80)
    print("  🛡️  TrustTest Multi-Agent Runner & Supervisor (Fetch-A-Thon 3.0)")
    print("=" * 80)
    print("Launching 5 worker agents in supervised mode...")

    python_exe = sys.executable
    processes: List[subprocess.Popen] = []
    restart_history: Dict[str, collections.deque] = collections.defaultdict(collections.deque)

    try:
        for name, script_path, log_path, port in AGENTS:
            # Clear old log file for fresh run
            open(log_path, "w", encoding="utf-8").close()
            proc = launch_process(script_path, log_path, python_exe)
            processes.append(proc)
            print(f"  • Started {name:<12} (PID: {proc.pid}) on port {port} -> {log_path.name}")

        print("\nWaiting for agents to initialize and register...")
        time.sleep(4.0)

        print("\n" + "=" * 80)
        print("  ACTIVE AGENT ENDPOINTS & INSPECTOR URLS")
        print("=" * 80)

        for name, _, log_path, port in AGENTS:
            addr, insp = extract_info(log_path)
            print(f"\n[{name} Agent - Port {port}]")
            print(f"  Address:   {addr}")
            print(f"  Inspector: {insp}")

        print("\n" + "=" * 80)
        print("All 5 agents running in Supervisor mode. Press CTRL+C to terminate.")
        print("=" * 80 + "\n")

        # Supervisor Monitoring Loop
        while True:
            time.sleep(2.0)
            now = time.time()

            for idx, (name, script_path, log_path, port) in enumerate(AGENTS):
                p = processes[idx]
                if p.poll() is not None:
                    # Process exited!
                    exit_code = p.returncode
                    history = restart_history[name]

                    # Purge restarts older than 10 minutes (600s)
                    while history and (now - history[0]) > 600.0:
                        history.popleft()

                    if len(history) < 5:
                        backoff = min(30.0, 2.0 ** len(history))
                        print(
                            f"⚠️ [SUPERVISOR] Agent '{name}' exited with code {exit_code}. "
                            f"Restarting in {backoff:.1f}s (Restart {len(history) + 1}/5 in 10m)..."
                        )
                        time.sleep(backoff)
                        new_proc = launch_process(script_path, log_path, python_exe)
                        processes[idx] = new_proc
                        history.append(now)
                        print(
                            f"✅ [SUPERVISOR] Agent '{name}' restarted with PID {new_proc.pid}. "
                            f"Verify mailbox reconnection in logs/{log_path.name}."
                        )
                    else:
                        print(
                            f"❌ [SUPERVISOR] Agent '{name}' exceeded max 5 restarts within 10 minutes. "
                            f"Halting restarts. Check logs/{log_path.name}."
                        )

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
