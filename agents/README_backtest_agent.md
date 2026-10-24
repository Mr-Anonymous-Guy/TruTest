# TrustTest Backtest Agent

![AgentChatProtocol](https://img.shields.io/badge/Chat_Protocol-v0.3.0-blue)
![Inspector](https://img.shields.io/badge/Agentverse-Inspector-orange)

The **TrustTest Backtest Agent** executes lookahead-free quantitative backtests with realistic transaction costs and slippage for structured trading strategies. It computes risk and return metrics including Sharpe ratio, CAGR, max drawdown, win rate, and market exposure.

- **Input**: `BacktestRequest(request_id, spec: dict, prices: dict)`
- **Output**: `BacktestResponse(request_id, ok, result: dict, error)`
