"""
scripts/smoke_llm.py – Live Smoke Test for ASI:One LLM API
"""

import os
import sys
import time
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(str(Path(__file__).resolve().parent.parent)))

from dotenv import load_dotenv
from agents.llm import call_llm, get_llm_config
from agents.parser_agent import parse_strategy_text

load_dotenv()


def main():
    config = get_llm_config()
    api_key = config["api_key"]
    if not api_key or api_key in ("REPLACE_WITH_ASI_ONE_KEY", "REPLACE_ME"):
        print("[LLM Smoke Test]: PENDING - ASI_ONE_API_KEY is not configured in .env.")
        print("Set ASI_ONE_API_KEY in your .env file to run live LLM verification.")
        return

    sample_prompt = "Backtest a 50/200 moving average crossover on RELIANCE.NS with 0.1% fees"
    print(f"Calling ASI:One endpoint ({config['base_url']}) with model '{config['model']}'...")
    print(f"Sample Prompt: \"{sample_prompt}\"")

    t0 = time.perf_counter()
    try:
        res = parse_strategy_text(sample_prompt)
        elapsed = time.perf_counter() - t0
        print(f"\n[Success! Latency: {elapsed:.2f}s]")
        print("Parsed Spec:", res.spec)
        print("Assumptions:", res.assumptions)
    except Exception as exc:
        print(f"\n[Failed]: {exc}")


if __name__ == "__main__":
    main()
