# TrustTest – Hackathon Plan (Fetch-A-Thon 3.0)

> **Motto:** Working demo > ambition. Keep it simple, keep it honest.

---

## Phase 0 – Setup & Scaffolding ⏱ 1 h

- [x] Create PLAN.md
- [x] Create full folder structure under `trusttest/`
- [x] Write `core/models.py` with all shared uagents.Model classes
- [x] Write `requirements.txt`, create `.venv`, install deps
- [x] Verify `chat_protocol_spec` name + version prints correctly
- [x] Write `.env.example` with placeholder keys/seeds
- [x] Write `.gitignore`
- [x] Write `scripts/build_cache.py` and run it (download CSVs)
- [x] Implement `core/data_loader.py` with live + cached fallback
- [x] Write offline test for `data_loader`
- [x] Write `README.md` skeleton with badges + agents table
- [x] `git init`, first commit, print push commands

---

## Phase 1 – Orchestrator live in ASI:One ⏱ 1.5 h

- [x] Implement `agents/orchestrator.py` with `chat_proto` (ACP 0.3.0)
- [x] Handle `StartSessionContent`, `ChatMessage`, `EndSessionContent`
- [x] Derive deterministic agent addresses from seeds and populate `.env`
- [x] Add agent addresses to README agents table
- [x] Smoke-test: send "hello" from ASI:One chat, get a reply

---

## Phase 2 – Pure logic in `core/` ⏱ 1.5 h

- [x] `core/backtest.py` – pandas engine, signal shift, fees/slippage, Sharpe / maxDD / CAGR / trades
- [x] `core/skeptic.py` – OOS split, param perturbation, cost 2x, Monte Carlo, verdict logic
- [x] Unit tests: `tests/test_backtest.py`, `tests/test_skeptic.py` pass with synthetic data
- [x] Run tests: `python -m pytest tests/ -v` (all passed)

---

## Phase 3 – Add agents one at a time ⏱ 2 h

- [x] `agents/parser_agent.py` – ASI:One LLM → StrategySpec JSON (with resilient heuristic fallback)
- [x] `agents/data_agent.py` – DataRequest → PriceData (live/cache, report source)
- [x] `agents/backtest_agent.py` – StrategySpec + PriceData → BacktestResult
- [x] `agents/skeptic_agent.py` – BacktestResult + raw data → AuditReport
- [x] Wire full pipeline through Orchestrator (`core/pipeline.py`)
- [x] End-to-end test with a known strategy (e.g., SMA 50/200 cross on RELIANCE.NS, RSI on TCS.NS)

---

## Phase 4 – Reliability ⏱ 0.5 h

- [x] Fallback handling between live yfinance and local cache
- [x] Hybrid parser ensuring zero-crash offline execution
- [x] Graceful error messages back to ASI:One
- [x] Cache warm-up script (`scripts/build_cache.py`) for offline resilience
- [x] Windows CP1252 stdout encoding safety configuration

---

## Phase 5 – Interactive result cards ⏱ 0.5 h

- [x] Format backtest result as a markdown card with emoji verdict (✅ / ⚠️ / ❌)
- [x] Include key metrics table + Skeptic findings in the reply
- [x] Add disclaimer footer on every result message

---

## Phase 6 – Multi-Agent Bureau & Standalone Demo ⏱ 0.5 h

- [x] Standalone CLI demo runner (`scripts/demo.py`)
- [x] Multi-agent bureau runner (`scripts/run_all.py`)
- [x] End-to-end integration test suite (`tests/test_pipeline.py`)

---

## Phase 7 – Submission ⏱ 0.5 h

- [x] Comprehensive README polish (architecture diagrams, agent tables, sample outputs)
- [x] 35/35 passing unit & integration tests
- [ ] Push final commit to GitHub repository

---

## Message Flow

```
User (ASI:One) ──ChatMessage──► Orchestrator
                                    │
                             ┌──────┼────────────────┐
                             ▼                        │
                       Parser Agent              (error path)
                    (plain English → StrategySpec)    │
                             │                        │
                             ▼                        │
                       Data Agent                     │
                    (ticker OHLCV data)               │
                             │                        │
                             ▼                        │
                     Backtest Agent                   │
                    (Sharpe, maxDD, CAGR…)            │
                             │                        │
                             ▼                        │
                     Skeptic Agent                    │
                    (OOS, perturb, verdict)           │
                             │                        │
                             └──────────────────────►│
                                                      │
                                             Orchestrator
                                                      │
                                       ChatMessage ◄──┘
                                    User (ASI:One)
```

---

> **Disclaimer:** TrustTest is for educational purposes only. It is NOT investment advice.
