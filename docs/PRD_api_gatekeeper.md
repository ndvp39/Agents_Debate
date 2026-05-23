# PRD — API Gatekeeper
**Version:** 1.00  
**Date:** 2026-05-23  
**File:** `src/debate/shared/gatekeeper.py`

---

## 1. Description & Theoretical Background

The API Gatekeeper is a centralized proxy layer through which **all** external API calls must pass. No agent, tool, or service may call an external API directly. This design enforces:

- **Cost control**: Token usage is tracked per call and accumulated across the session.
- **Rate limiting**: Calls are metered against configured limits (requests/minute, requests/hour, concurrent max).
- **Resilience**: Transient failures trigger automatic retries with exponential back-off.
- **Observability**: Every call is logged with its inputs, outputs, latency, and token usage.
- **Fairness**: When rate limits are hit, excess calls are queued (FIFO) rather than dropped.

This pattern is known as the **Circuit Breaker + Queue** pattern in distributed systems, adapted here for a local multi-agent architecture.

---

## 2. Responsibilities

- Check rate limits before every external call.
- Execute the call if within limits; queue it if the limit is reached.
- Retry on transient failures (HTTP 429, 500, 502, 503, 504) with exponential back-off.
- Log every call: timestamp, service name, token count (in/out), latency, success/failure.
- Drain the queue as rate windows reset.
- Provide a `get_queue_status()` method for monitoring.
- Provide a `get_cost_summary()` method returning accumulated token costs.

---

## 3. Interface

```python
class ApiGatekeeper:
    """Centralized API call manager — all external calls go through here."""

    def __init__(self, config: RateLimitConfig):
        """Load rate limits and queue settings from RateLimitConfig."""

    def execute(self, api_call: Callable, *args, **kwargs) -> Any:
        """
        Execute api_call through the gatekeeper.
        - Check rate limits; queue if limit reached
        - Retry on transient failures (max_retries from config)
        - Log all calls
        """

    def get_queue_status(self) -> dict:
        """Return current queue depth, pending calls, and window reset time."""

    def get_cost_summary(self) -> dict:
        """Return accumulated token counts and estimated cost per service."""
```

---

## 4. Rate Limit Configuration

All values loaded from `config/rate_limits.json` — never hardcoded.

```json
{
  "rate_limits": {
    "version": "1.00",
    "services": {
      "default": {
        "requests_per_minute": 30,
        "requests_per_hour": 500,
        "concurrent_max": 5,
        "retry_after_seconds": 30,
        "max_retries": 3,
        "queue_max_depth": 50
      }
    }
  }
}
```

| Parameter | Description |
|-----------|-------------|
| `requests_per_minute` | Max calls in any 60-second window |
| `requests_per_hour` | Max calls in any 3600-second window |
| `concurrent_max` | Max simultaneous in-flight calls |
| `retry_after_seconds` | Base wait before first retry |
| `max_retries` | Maximum retry attempts per call |
| `queue_max_depth` | Maximum calls waiting in the FIFO queue |

---

## 5. Queue Management on Overflow

When a rate limit is reached:
1. The call is placed at the back of the **FIFO queue** (not dropped).
2. The queue is bounded by `queue_max_depth`; if the queue is full, a `BackpressureError` is raised.
3. A background drain loop checks the rate window every second and processes the front of the queue when capacity is available.
4. The calling code awaits the result transparently — from its perspective, `execute()` simply returned after a short wait.

```
[execute() called]
      │
      ▼
[rate limit check]──── OK ────▶ [call API] ──▶ [return result]
      │
   LIMIT HIT
      │
      ▼
[queue depth < max?]──── YES ──▶ [enqueue] ──▶ [drain loop picks up] ──▶ [return result]
      │
      NO
      │
      ▼
[raise BackpressureError]
```

---

## 6. Retry Logic

On transient failure (HTTP 429, 500, 502, 503, 504 or equivalent SDK exceptions):
- Wait `retry_after_seconds * (2 ^ attempt)` (exponential back-off).
- Retry up to `max_retries` times.
- On exhaustion of retries: raise `GatekeeperMaxRetriesError`.
- Non-transient errors (400, 401, 403): do not retry; raise immediately.

---

## 7. Token Tracking & Cost Estimation

Every LLM API call response includes token counts (input tokens, output tokens). The gatekeeper accumulates:

```python
@dataclass
class CostAccumulator:
    service: str
    total_input_tokens: int
    total_output_tokens: int
    total_calls: int
    estimated_cost_usd: float
```

Cost per token is loaded from `config/setup.json` (model pricing section) — never hardcoded.

---

## 8. Logging

Every call is logged via `DebateLogger`:

```
[2026-05-23 14:32:01] GATEKEEPER | service=llm | status=success | input_tokens=412 | output_tokens=289 | latency_ms=1820 | queue_depth=0
[2026-05-23 14:32:45] GATEKEEPER | service=web_search | status=retry_1 | error=HTTP_429 | wait_s=30
```

---

## 9. Performance Requirements

| Metric | Target |
|--------|--------|
| Overhead per call (gatekeeper logic only) | < 5ms |
| Queue drain check interval | 1 second |
| Max queue depth before backpressure | Configurable (default 50) |

---

## 10. Constraints

- **Every** external API call (LLM, web-search) MUST use `gatekeeper.execute()`.
- Rate limits MUST be loaded from `config/rate_limits.json` — never hardcoded.
- Queue MUST be FIFO — no priority reordering.
- On queue full: raise `BackpressureError` — do NOT silently drop the call.
- The Gatekeeper is a **singleton** within each process — one instance shared across all tools and skills.

---

## 11. Alternatives Considered

| Alternative | Reason Rejected |
|-------------|----------------|
| Each agent manages its own rate limits | Duplicate logic; no global view of total API usage |
| Drop calls on overflow | Causes silent data loss; violates requirement |
| Hard-code rate limits | Violates project guidelines; untestable configuration |
| Use a third-party rate-limiter library | Adds dependency; simpler to implement given spec requirements |

---

## 12. Success Criteria

- [ ] All LLM and web-search calls are routed through the gatekeeper (verifiable via logs).
- [ ] A burst of 35 calls in 1 minute (limit=30) queues 5 calls and processes them after the window resets.
- [ ] A transient HTTP 429 triggers retry with exponential back-off; call eventually succeeds.
- [ ] After `max_retries` exhausted, `GatekeeperMaxRetriesError` is raised.
- [ ] `get_cost_summary()` returns correct accumulated token counts after a session.
- [ ] Queue full → `BackpressureError` raised, no calls dropped silently.

---

## 13. Test Scenarios

| Scenario | Expected Outcome |
|----------|-----------------|
| 5 calls within rate limit | All execute immediately; queue depth = 0 |
| 35 calls when limit = 30/min | First 30 execute; 5 queued; processed after window reset |
| HTTP 429 on first call | Retry fired after back-off; succeeds on retry 2 |
| 3 retries exhausted | `GatekeeperMaxRetriesError` raised |
| Queue at max_depth, new call arrives | `BackpressureError` raised |
| `get_cost_summary()` after 10 LLM calls | Correct total input/output tokens; non-zero cost estimate |
