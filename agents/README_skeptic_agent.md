# TrustTest Skeptic Agent

![AgentChatProtocol](https://img.shields.io/badge/Chat_Protocol-v0.3.0-blue)
![Inspector](https://img.shields.io/badge/Agentverse-Inspector-orange)

The **TrustTest Skeptic Agent** is the adversarial auditor in the TrustTest pipeline. It stress-tests candidate trading strategies against four quantitative attacks:
1. **Out-of-Sample Split (70/30)**: Detects severe regime degradation.
2. **Parameter Perturbation ($\pm 10\%$, $\pm 20\%$)**: Detects unstable parameter cliff edges.
3. **Cost Sensitivity ($2\times$ Friction)**: Tests resilience against real-world slippage and fees.
4. **Monte Carlo Random Baseline (500 runs)**: Benchmarks against identical random-trade distributions.

Outputs one of three deterministic verdicts:
- **`Trustworthy`**: Survived all four stress tests.
- **`Fragile`**: Failed exactly one stress test while beating the random baseline.
- **`Likely Overfit`**: Failed the random baseline or failed multiple stress tests.

- **Input**: `AuditRequest(request_id, spec: dict, prices: dict)`
- **Output**: `AuditResponse(request_id, ok, report: dict, error)`
