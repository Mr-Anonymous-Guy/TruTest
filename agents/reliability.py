"""
agents/reliability.py – Pure-Python Reliability & Fault-Tolerant Primitives
==========================================================================
Zero uagents imports. Pure Python, fully unit-testable with deterministic clocks.

Provides:
  1. Error Taxonomy (UserError, TransientError, InternalError)
  2. BoundedSessionStore (TTL-based idle expiration, max-size LRU eviction)
  3. MessageDeduplicator (bounded LRU message ID deduplication)
  4. ConcurrencyGuard (single active pipeline per sender)
  5. RateLimiter (sliding window quota protector)
  6. InputSanitizer (control char stripping, bounds check, length cap)
  7. RequestBudget (per-request deadline countdown)
  8. call_with_retry (one-shot transient retry with backoff)
"""

from __future__ import annotations

import collections
import logging
import re
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("trusttest.reliability")


# ---------------------------------------------------------------------------
# 1. Error Taxonomy
# ---------------------------------------------------------------------------

class TrustTestError(Exception):
    """Base exception for all TrustTest errors."""


class UserError(TrustTestError):
    """
    Error fixable by the user (invalid ticker, dates in future, short history,
    ambiguous parameters). MUST NOT be retried. Re-asks user.
    """


class TransientError(TrustTestError):
    """
    Temporary or operational failure (timeout, network dropped, worker unreachable,
    rate limit 429, 5xx server error). Candidate for one-shot retry with backoff.
    """


class InternalError(TrustTestError):
    """
    Unexpected bug or fatal logic failure. Apologize with error_id and log trace.
    """
    def __init__(self, message: str, error_id: Optional[str] = None) -> None:
        super().__init__(message)
        self.error_id = error_id or f"err-{int(time.time() * 1000) % 1000000:06d}"


# ---------------------------------------------------------------------------
# 2. Input Sanitization
# ---------------------------------------------------------------------------

# Matches non-printable control characters except standard whitespace (\n, \r, \t)
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]")


def sanitize_input(text: Optional[str], max_chars: int = 1000) -> Tuple[bool, str, Optional[str]]:
    """
    Sanitize raw user text:
      - Strips control characters
      - Normalizes whitespace
      - Enforces min length (> 0) and max length (<= max_chars)

    Returns:
        (ok, sanitized_text, error_message)
    """
    if text is None:
        return False, "", "empty"

    # Strip control characters
    cleaned = _CONTROL_CHAR_RE.sub("", text).strip()

    if not cleaned:
        return False, "", "empty"

    if len(cleaned) > max_chars:
        return False, cleaned[:max_chars], "too_long"

    return True, cleaned, None


# ---------------------------------------------------------------------------
# 3. Message Deduplicator
# ---------------------------------------------------------------------------

class MessageDeduplicator:
    """
    Bounded LRU set of processed message IDs to handle at-least-once delivery
    from ASI:One without redundant execution or state corruption.
    """

    def __init__(self, max_size: int = 2000) -> None:
        self.max_size = max_size
        self._seen: collections.OrderedDict[str, float] = collections.OrderedDict()

    def is_duplicate(self, msg_id: Optional[str]) -> bool:
        """Returns True if msg_id was already seen, otherwise marks as seen."""
        if not msg_id:
            return False

        if msg_id in self._seen:
            # Move to end (most recently accessed)
            self._seen.move_to_end(msg_id)
            return True

        self._seen[msg_id] = time.time()
        if len(self._seen) > self.max_size:
            # Evict oldest
            self._seen.popitem(last=False)
        return False

    def clear(self) -> None:
        self._seen.clear()


# ---------------------------------------------------------------------------
# 4. Concurrency Guard
# ---------------------------------------------------------------------------

class ConcurrencyGuard:
    """
    Ensures only one active pipeline executes per sender at any time.
    Prevents race conditions on session state and double spending of compute.
    """

    def __init__(self) -> None:
        self._active_senders: Set[str] = set()

    def acquire(self, sender: str) -> bool:
        """Returns True if lock acquired, False if sender already running a request."""
        if sender in self._active_senders:
            return False
        self._active_senders.add(sender)
        return True

    def release(self, sender: str) -> None:
        """Releases the lock for sender."""
        self._active_senders.discard(sender)

    def is_busy(self, sender: str) -> bool:
        return sender in self._active_senders


# ---------------------------------------------------------------------------
# 5. Sliding-Window Rate Limiter
# ---------------------------------------------------------------------------

class RateLimiter:
    """
    In-memory sliding-window rate limiter per sender.
    Protects downstream LLM quota and yfinance endpoints.
    """

    def __init__(self, max_requests: int = 6, window_seconds: float = 60.0) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._history: Dict[str, collections.deque[float]] = collections.defaultdict(collections.deque)

    def allow(self, sender: str, current_time: Optional[float] = None) -> bool:
        now = current_time if current_time is not None else time.time()
        q = self._history[sender]

        # Purge timestamps outside the sliding window
        cutoff = now - self.window_seconds
        while q and q[0] <= cutoff:
            q.popleft()

        if len(q) >= self.max_requests:
            return False

        q.append(now)
        return True

    def cleanup_idle(self, max_idle: float = 300.0, current_time: Optional[float] = None) -> None:
        now = current_time if current_time is not None else time.time()
        stale_keys = [
            k for k, q in self._history.items()
            if not q or (now - q[-1]) > max_idle
        ]
        for k in stale_keys:
            del self._history[k]


# ---------------------------------------------------------------------------
# 6. Bounded Session Store with TTL
# ---------------------------------------------------------------------------

class BoundedSessionStore:
    """
    Session storage with idle TTL eviction and maximum capacity limit.
    Prevents memory leaks from unbounded multi-user interaction.
    """

    def __init__(self, max_sessions: int = 1000, ttl_seconds: float = 1800.0) -> None:
        self.max_sessions = max_sessions
        self.ttl_seconds = ttl_seconds
        # Maps sender -> {"data": dict, "last_accessed": float}
        self._sessions: collections.OrderedDict[str, Dict[str, Any]] = collections.OrderedDict()

    def get_or_create(self, sender: str, current_time: Optional[float] = None) -> Dict[str, Any]:
        now = current_time if current_time is not None else time.time()
        self._evict_expired(now)

        if sender in self._sessions:
            item = self._sessions[sender]
            item["last_accessed"] = now
            self._sessions.move_to_end(sender)
            return item["data"]

        # Evict oldest if capacity reached
        while len(self._sessions) >= self.max_sessions:
            self._sessions.popitem(last=False)

        new_data: Dict[str, Any] = {
            "partial_spec": None,
            "created_at": now,
        }
        self._sessions[sender] = {
            "data": new_data,
            "last_accessed": now,
        }
        return new_data

    def update_partial_spec(self, sender: str, partial_spec: Optional[Dict[str, Any]], current_time: Optional[float] = None) -> None:
        sess = self.get_or_create(sender, current_time=current_time)
        sess["partial_spec"] = partial_spec

    def clear(self, sender: str) -> None:
        self._sessions.pop(sender, None)

    def _evict_expired(self, now: float) -> None:
        cutoff = now - self.ttl_seconds
        expired = [s for s, it in self._sessions.items() if it["last_accessed"] < cutoff]
        for s in expired:
            del self._sessions[s]

    def __len__(self) -> int:
        return len(self._sessions)


# ---------------------------------------------------------------------------
# 7. Request Budget / Total Deadline
# ---------------------------------------------------------------------------

class RequestBudget:
    """
    Tracks elapsed time against a total request deadline (e.g. 120s),
    ensuring cascading timeouts cannot exceed the maximum allowed duration.
    """

    def __init__(self, total_seconds: float = 120.0, start_time: Optional[float] = None) -> None:
        self.total_seconds = total_seconds
        self.start_time = start_time if start_time is not None else time.perf_counter()

    def elapsed(self, current_time: Optional[float] = None) -> float:
        now = current_time if current_time is not None else time.perf_counter()
        return max(0.0, now - self.start_time)

    def remaining(self, current_time: Optional[float] = None) -> float:
        return max(0.0, self.total_seconds - self.elapsed(current_time))

    def clamp_timeout(self, step_timeout: float, current_time: Optional[float] = None) -> float:
        """Returns step_timeout clamped to the remaining budget, or raises TransientError if exhausted."""
        rem = self.remaining(current_time)
        if rem <= 0.5:
            raise TransientError("Total request deadline exhausted.")
        return min(step_timeout, rem)


# ---------------------------------------------------------------------------
# 8. Retries with Backoff
# ---------------------------------------------------------------------------

def call_with_retry(
    step_name: str,
    action_fn: Callable[[], Any],
    retries: int = 1,
    backoff: float = 1.0,
    sleeper: Callable[[float], None] = time.sleep,
) -> Any:
    """
    Execute action_fn with up to `retries` additional attempts on TransientError.
    Never retries UserError or business logic failures (ok=False).

    Args:
        step_name: Name of the pipeline step for logging
        action_fn: Zero-arg callable returning the response or raising an exception
        retries: Number of retry attempts (default 1)
        backoff: Delay in seconds between retries (multiplied by attempt)
        sleeper: Sleep function, replaceable for deterministic testing
    """
    last_exc: Optional[Exception] = None

    for attempt in range(retries + 1):
        try:
            return action_fn()
        except UserError:
            # User errors must NEVER be retried
            raise
        except TransientError as e:
            last_exc = e
            if attempt < retries:
                delay = backoff * (attempt + 1)
                logger.warning("[%s] Transient error on attempt %d/%d: %s. Retrying in %.1fs...", step_name, attempt + 1, retries + 1, e, delay)
                sleeper(delay)
            else:
                logger.error("[%s] All %d attempts failed. Last transient error: %s", step_name, retries + 1, e)
                raise
        except Exception as e:
            # Unclassified unexpected error
            raise InternalError(f"Unexpected error in {step_name}: {e}") from e

    if last_exc:
        raise last_exc
