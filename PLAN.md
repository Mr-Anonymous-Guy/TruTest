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

- [ ] Implement `agents/orchestrator.py` with `chat_proto` (ACP 0.3.0)
- [ ] Handle `StartSessionContent`, `ChatMessage`, `EndSessionContent`
- [ ] Register on Agentverse; confirm address
- [ ] Add Agentverse address to README agents table
- [ ] Smoke-test: send "hello" from ASI:One chat, get a reply

---

## Phase 2 – Pure logic in `core/` ⏱ 1.5 h

- [ ] `core/backtest.py` – pandas engine, signal shift, fees/slippage, Sharpe / maxDD / CAGR / trades
- [ ] `core/skeptic.py` – OOS split, param perturbation, cost 2x, Monte Carlo, verdict logic
- [ ] Unit tests: `tests/test_backtest.py`, `tests/test_skeptic.py` pass with synthetic data
- [ ] Run tests: `python -m pytest tests/ -v`

---

## Phase 3 – Add agents one at a time ⏱ 2 h

- [ ] `agents/parser_agent.py` – ASI:One LLM → StrategySpec JSON
- [ ] `agents/data_agent.py` – DataRequest → PriceData (live/cache, report source)
- [ ] `agents/backtest_agent.py` – StrategySpec + PriceData → BacktestResult
- [ ] `agents/skeptic_agent.py` – BacktestResult + raw data → AuditReport
- [ ] Wire full pipeline through Orchestrator
- [ ] End-to-end test with a known strategy (e.g., SMA 50/200 cross on RELIANCE.NS)

---

## Phase 4 – Reliability ⏱ 0.5 h

- [ ] Timeout handling on every `ctx.send` (30 s)
- [ ] Retry logic (3 attempts) in parser and data agents
- [ ] Graceful error messages back to ASI:One
- [ ] Cache warm-up on startup (data agent)

---

## Phase 5 – Interactive result cards ⏱ 0.5 h

- [ ] Format backtest result as a markdown card with emoji verdict (✅ / ⚠️ / ❌)
- [ ] Include key metrics table + Skeptic findings in the reply
- [ ] Add disclaimer footer on every result message

---

## Phase 6 – Payment Protocol (stretch) ⏱ 0.5 h

- [ ] Integrate uagents payment / FET token gate if time allows
- [ ] Gated access: first 3 backtests free, then micro-payment

---

## Phase 7 – Submission ⏱ 0.5 h

- [ ] Final README polish (fill Agentverse addresses, demo screenshot)
- [ ] Record 60-second demo video
- [ ] Submit on Devpost / hackathon portal
- [ ] Push final commit to public GitHub

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
