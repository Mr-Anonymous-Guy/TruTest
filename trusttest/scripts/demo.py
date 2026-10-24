"""
TrustTest – Standalone CLI Demo
===============================
Runs the full TrustTest pipeline directly from the terminal without needing
an active ASI:One network session. Great for live demos, video recordings,
and rapid testing.
"""

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

from trusttest.core.pipeline import run_pipeline

SAMPLE_PROMPTS = [
    "Buy Reliance when the 50 SMA crosses above the 200 SMA from 2018 to 2024",
    "RSI below 30 buy, exit above 70 on TCS.NS from 2019 to 2023",
    "20-day momentum on AAPL",
]

def main() -> None:
    prompt = sys.argv[1] if len(sys.argv) > 1 else SAMPLE_PROMPTS[0]
    print("=" * 70)
    print("  🛡️  TrustTest – Adversarial Strategy Backtester & Skeptic Auditor")
    print("=" * 70)
    print(f"\nUser Prompt: \"{prompt}\"\n")
    print("Running pipeline: Parser -> Data Loader -> Backtest -> Skeptic Audit...\n")

    result = run_pipeline(prompt)
    print(result)


if __name__ == "__main__":
    main()
