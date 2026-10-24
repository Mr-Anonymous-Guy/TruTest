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

## Phase 4 – Reliability, Fault Tolerance & Tracing ⏱ 0.5 h

- [x] Pure-Python reliability primitives (`agents/reliability.py`): Error taxonomy (`UserError`, `TransientError`, `InternalError`), `call_with_retry` (1 retry on transient), `RequestBudget` (120s countdown), `MessageDeduplicator` (LRU 2000), `ConcurrencyGuard`, `RateLimiter` (6 req/min), `BoundedSessionStore` (30m TTL, max 1000 items), `sanitize_input`
- [x] Centralized user-facing copy (`agents/messages.py`)
- [x] Step-by-step trace logger (`agents/trace.py`) with 5MB log rotation & CLI visualizer (`scripts/show_trace.py`)
- [x] Worker hardening: `HealthRequest`/`HealthResponse` handlers, input validation, never-raise handlers on all 4 workers
- [x] Orchestrator `status` health command (fast multi-agent health ping table, no LLM call)
- [x] Graceful partial results when Skeptic is unavailable/timed out (unvalidated disclaimer, zero made-up numbers)
- [x] Fault injection framework (`agents/faults.py`): `data_live_fail`, `data_fail`, `backtest_fail`, `skeptic_timeout`, `llm_fail`, `llm_badjson`
- [x] Market data edge cases: future end date clamped, start in future rejected, start >= end rejected, difflib ticker suggestions
- [x] LLM resilience: 3-failure circuit breaker (60s open window), transient retries, clean code fence & prose extraction
- [x] Rule-based fallback parser for offline execution (MA crossover, RSI, years, fees)
- [x] Supervisor mode in `scripts/run_all.py` with exponential backoff (max 5 restarts per 10m)
- [x] Timing footer on full pipeline results (`Took 8.4s (parse 2.1, data 0.8, backtest 0.2, audit 5.3)`)
- [x] Comprehensive test suite expanded to 60 passing tests including soak testing (200 seq + 20 interleaved across 10 senders)

---

## Phase 5 – ASI:One Interactive Cards (Protocol v1) ⏱ 0.5 h

- [x] ASI:One Card Protocol v1 schemas via `MetadataContent` in `agents/cards.py`
- [x] Card 1: Strategy Picker `CarouselCardPayload` on greeting / "hi" with Demo A, Demo B, and Form CTAs
- [x] Card 2: Headline Results `DetailCardPayload` with metrics and Skeptic verdict badge
- [x] Card 3: Adversarial Breakdown `DetailCardPayload` with 4 test findings and "Back to Results" CTA
- [x] Card 4: Parameter Form `FormCardPayload` with field validation (fast < slow MA) and error title display
- [x] `CardResultCache` bounded in-memory LRU store with TTL for instant card tab toggling
- [x] Sample card payloads exported to `docs/cards/*.json` for ASI:One Card Playground verification
- [x] Graceful text fallback when `TRUSTTEST_CARDS=off` or for partial results
- [x] Future monetization plan documented in `README.md` (free backtest, paid audit)
- [x] 68/68 unit & integration tests passing (`pytest tests/ -v`)

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
