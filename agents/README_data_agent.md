# TrustTest Data Agent

![AgentChatProtocol](https://img.shields.io/badge/Chat_Protocol-v0.3.0-blue)
![Inspector](https://img.shields.io/badge/Agentverse-Inspector-orange)

The **TrustTest Data Agent** provides reliable, adjusted historical market data for Indian NSE and global equities. It queries live data via Yahoo Finance (`auto_adjust=True`) and automatically falls back to curated offline CSV caches with gap validation.

- **Input**: `DataRequest(request_id, ticker, start, end)`
- **Output**: `PriceData(request_id, ok, ticker, source, start, end, bars, dates, closes, note, error)`
