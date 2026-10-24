"""
TrustTest – Multi-Agent Bureau Runner
====================================
Runs all 5 TrustTest uAgents in a single process using the uagents Bureau:
  1. trusttest_orchestrator  (Agent Chat Protocol 0.3.0)
  2. trusttest_parser        (Plain English -> StrategySpec)
  3. trusttest_data          (Market Data Loader with Live/Cache)
  4. trusttest_backtest      (Backtest Engine)
  5. trusttest_skeptic       (Adversarial Skeptic Auditor)

Usage:
    python trusttest/scripts/run_all.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Safe utf-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Ensure project root is in sys.path
ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from uagents import Bureau

from trusttest.agents.backtest_agent import agent as backtest_agent
from trusttest.agents.data_agent import agent as data_agent
from trusttest.agents.orchestrator import agent as orchestrator_agent
from trusttest.agents.parser_agent import agent as parser_agent
from trusttest.agents.skeptic_agent import agent as skeptic_agent

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("trusttest.bureau")


def main() -> None:
    print("=" * 70)
    print("  🛡️  TrustTest Multi-Agent Bureau (Fetch-A-Thon 3.0)")
    print("=" * 70)
    print("Initializing 5 uAgents:")
    print(f"  • Orchestrator: {orchestrator_agent.address}")
    print(f"  • Parser:       {parser_agent.address}")
    print(f"  • Data:         {data_agent.address}")
    print(f"  • Backtest:     {backtest_agent.address}")
    print(f"  • Skeptic:      {skeptic_agent.address}")
    print("\nStarting Bureau...")

    bureau = Bureau(port=8000)
    bureau.add(orchestrator_agent)
    bureau.add(parser_agent)
    bureau.add(data_agent)
    bureau.add(backtest_agent)
    bureau.add(skeptic_agent)

    bureau.run()


if __name__ == "__main__":
    main()
