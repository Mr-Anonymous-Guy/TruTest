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
- [x] Load `ORCHESTRATOR_SEED` from `.env`, helper `create_text_chat`, structured logging
- [x] Write `agents/README_orchestrator.md` for Agentverse profile
- [x] Compile and verify locally (`python -m py_compile agents/orchestrator.py`)
- [x] Launch agent and obtain Agent address & Inspector URL
- [ ] Connect mailbox in Inspector URL (manual user action)
- [ ] Set Agentverse Profile and test in ASI:One chat (manual user action)

---

## Phase 2 – Pure logic in `core/` ⏱ 1.5 h

- [x] `core/data.py` – cached CSV loader with DataQualityError and price validation
- [x] `core/backtest.py` – pandas engine, signal shift, fees/slippage, Sharpe / maxDD / CAGR / trades
- [x] `core/skeptic.py` – OOS split, param perturbation, cost 2x, Monte Carlo baseline, verdict logic
- [x] Unit tests: `tests/test_backtest.py`, `tests/test_data.py`, `tests/test_skeptic.py` (15/15 passing)
- [x] Demo pair script: `scripts/demo_pair.py` producing `data/demo_pair.json` & `data/demo_pair_results.json`
- [x] Core documentation: `core/README.md` for Phase 3 agent wiring

---

## Phase 3 – Add agents one at a time ⏱ 2 h

- [x] `agents/models.py` – typed uagents message models (27.7 KB 5y payload, well within 1MB limit)
- [x] `agents/data_agent.py` (port 8002) – live yfinance + local CSV fallback (`agents/data_source.py`)
- [x] `agents/backtest_agent.py` (port 8003) – lookahead-free quantitative simulation engine
- [x] `agents/skeptic_agent.py` (port 8004) – adversarial stress testing (0.03s Demo A / 0.04s Demo B)
- [x] `agents/parser_agent.py` (port 8005) – ASI:One LLM API client + heuristic fallback (`agents/llm.py`)
- [x] `agents/orchestrator.py` & `agents/pipeline.py` (port 8001) – 4-hop pipeline wired with per-hop timeouts
- [x] `scripts/print_addresses.py` – deterministic address derivation from seeds
- [x] `scripts/run_all.py` – 5-agent multi-process runner with Inspector URL extraction
- [x] 33/33 unit & integration tests passing (`pytest tests/ -v`)

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
