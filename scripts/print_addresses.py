"""
scripts/print_addresses.py – Derive and Print Public Agent Addresses

Derives each agent's Bech32 address deterministically from its seed in .env
without running or starting any agent. Can append address variables to .env.
"""

import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(str(Path(__file__).resolve().parent.parent)))

from dotenv import load_dotenv
from uagents.crypto import Identity

load_dotenv()

AGENT_CONFIGS = [
    ("Orchestrator", "ORCHESTRATOR_SEED", "ORCHESTRATOR_AGENT_ADDRESS", "trusttest_orchestrator_seed_hackathon_fetchathon3"),
    ("Parser", "PARSER_SEED", "PARSER_AGENT_ADDRESS", "trusttest_parser_agent_seed_fetchathon3_2026"),
    ("Data", "DATA_SEED", "DATA_AGENT_ADDRESS", "trusttest_data_agent_seed_fetchathon3_2026"),
    ("Backtest", "BACKTEST_SEED", "BACKTEST_AGENT_ADDRESS", "trusttest_backtest_agent_seed_fetchathon3_2026"),
    ("Skeptic", "SKEPTIC_SEED", "SKEPTIC_AGENT_ADDRESS", "trusttest_skeptic_agent_seed_fetchathon3_2026"),
]


def derive_address(seed: str) -> str:
    """Derive Bech32 agent address from a seed string without starting an agent."""
    identity = Identity.from_seed(seed, 0)
    return identity.address


def main():
    append_mode = "--append" in sys.argv or "-a" in sys.argv
    print("=" * 80)
    print("  TrustTest Agent Addresses (Derived Deterministically from Seeds)")
    print("=" * 80)
    fmt = "{:<14} | {:<24} | {:<42}"
    print(fmt.format("Role", "Env Variable", "Derived Public Bech32 Address"))
    print("-" * 80)

    derived = {}
    lines_to_add = []

    for name, seed_var, addr_var, default_seed in AGENT_CONFIGS:
        seed = os.getenv(seed_var, default_seed)
        addr = derive_address(seed)
        derived[addr_var] = addr
        print(fmt.format(name, addr_var, addr))

        curr_in_env = os.getenv(addr_var)
        if not curr_in_env:
            lines_to_add.append(f"{addr_var}={addr}\n")

    print("=" * 80)

    if lines_to_add:
        if append_mode or not sys.stdin.isatty():
            with open(".env", "a", encoding="utf-8") as f:
                f.write("\n# Agent Addresses (Auto-derived)\n")
                f.writelines(lines_to_add)
            print(f"\nAppended {len(lines_to_add)} missing agent address variables to .env.")
        else:
            print(f"\nMissing address variables in .env: {len(lines_to_add)}. Run with --append to write them.")
    else:
        print("\nAll agent addresses are already present in .env.")


if __name__ == "__main__":
    main()
