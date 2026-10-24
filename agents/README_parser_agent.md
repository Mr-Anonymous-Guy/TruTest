# TrustTest Strategy Parser Agent

![AgentChatProtocol](https://img.shields.io/badge/Chat_Protocol-v0.3.0-blue)
![Inspector](https://img.shields.io/badge/Agentverse-Inspector-orange)

The **TrustTest Strategy Parser Agent** translates unstructured plain-English trading strategies into structured `StrategySpec` JSON objects. It integrates with the **ASI:One LLM API** (`model="asi1"`) for natural language understanding, validates quantitative constraints, handles conversational context across multiple turns, and incorporates deterministic heuristic fallback for offline execution.

- **Input**: `ParseRequest(request_id, text, context: Optional[dict])`
- **Output**: `ParseResponse(request_id, ok, spec: Optional[dict], missing: list, question: Optional[str], assumptions: list, error: Optional[str])`
