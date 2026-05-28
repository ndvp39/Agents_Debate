# PRD — API Gatekeeper
**Version:** 1.00  
**Date:** 2026-05-23  
**Author:** Nadav Goldin  
**File:** `src/debate/shared/gatekeeper.py`

---

## 1. Description & Theoretical Background

The API Gatekeeper is a centralized proxy layer through which **all** external API calls must pass. No agent, tool, or service may call an external API directly. This design enforces:

- **Cost control**: Token usage is tracked per call and accumulated across the session.
- **Rate limiting**: Calls are metered against configured limits (requests/minute, requests/hour, concurrent max).
- **Observability**: Every call's success increments the cost accumulator; per-agent dumps are aggregated by the SDK into `DebateResult.cost_summary`.
- **Fairness**: When rate limits are hit, excess calls are queued (FIFO) rather than dropped.

> **Retry note (commit `f78cc29`):** the gatekeeper does **NOT** retry the
> `api_call`. The inner provider-aware `_retry()` in `shared/llm_retry.py`
> already owns retry policy (Gemini `retry_in` hints, daily-quota fail-fast,
> empty-response replay). A gatekeeper-level retry was double-retrying on
> transient failures and — worse — re-trying fatal exceptions that the inner
> layer correctly raised, inflating turns by 30/60/120 s. The gatekeeper now
> calls `api_call` exactly once, records cost on success, propagates exceptions
> immediately on failure.

This pattern is a **rate-limit + FIFO queue + cost accumulator**, adapted for
a local multi-agent architecture.

---

## 2. Responsibilities

- Check rate limits before every external call.
- Execute the call **exactly once** if within limits; queue it if the limit is reached.
- Record cost on success (call count + token totals). Token totals can be supplied via the `_input_tokens`/`_output_tokens` kwargs at submit time OR added post-hoc via `record_tokens(in, out)` once the provider returns `response.usage`.
- Optionally dump the running cost summary to a per-agent JSON file (`cost_dump_path`) after every successful call, so a parent process can aggregate per-subprocess costs without IPC.
- Propagate any exception from `api_call` immediately — **no internal retry**.
- Drain the queue as rate windows reset.
- Provide `get_queue_status()` and `get_cost_summary()` accessors.

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

## 6. Retry Policy (delegated)

The gatekeeper does **NOT** retry. Retry is handled by `shared/llm_retry.py`'s
`_retry(fn, label)`, which the LLM closures (`make_anthropic_*`, `make_gemini_*`)
wrap around the provider call before passing it into `gatekeeper.execute(...)`:

- Provider-suggested delay on transient 429s (parses `retry_in` / `retryDelay`).
- Fail-fast on `Daily API quota exhausted` (raises `RuntimeError` immediately).
- Empty/None response replay (`_EMPTY_MAX_RETRIES = 3`, 2 s delay).

`max_retries` / `retry_after_seconds` keys in `rate_limits.json` are read for
backward-compat but no longer used by the gatekeeper. The historical
`GatekeeperMaxRetriesError` exception is retained in `shared/exceptions.py`
for compatibility with any external code that imports it; the gatekeeper
itself does not raise it.

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

## 9.1 Wiring history

The `ApiGatekeeper` class was implemented and unit-tested before live wiring,
but until commit `7ea57b3` it was a **dormant component** — every LLM call went
straight to the provider SDK, bypassing the gate, and `DebateSDK.get_cost_summary()`
returned `{}` because the gatekeeper was always `None`. The wiring milestone
introduced per-subprocess gatekeepers (each runner constructs one
`ApiGatekeeper(service="llm")` for the LLM and, for debaters, one
`ApiGatekeeper(service="web_search")` for Tavily; see `pro_runner.py`,
`con_runner.py`, `judge_runner.py`). LLM and Tavily closures (`shared/llm_*`,
`shared/web_search.py`) wrap every provider call inside `gatekeeper.execute(...)`;
a grep of `src/` confirms no `client.messages.create` / `client.models.generate_content`
/ `client.search` call site exists outside a `_do()` closure routed through the
gate. Commit `f78cc29` removed the gatekeeper-level retry that was inflating
turns (see §6 retry note).

---

## 10. Constraints

- **Every** external API call (LLM, web-search) MUST use `gatekeeper.execute()`.
- Rate limits MUST be loaded from `config/rate_limits.json` — never hardcoded.
- Queue MUST be FIFO — no priority reordering.
- On queue full: raise `BackpressureError` — do NOT silently drop the call.
- One gatekeeper instance per service per subprocess; **not** a global singleton (the multi-process architecture rules that out). Cost is aggregated by the SDK at debate end via `cost_aggregator.aggregate_costs()`.

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

- [x] All LLM and web-search calls are routed through the gatekeeper (verifiable via logs).
- [x] A burst of 35 calls in 1 minute (limit=30) queues 5 calls and processes them after the window resets.
- [x] A transient HTTP 429 triggers retry with exponential back-off; call eventually succeeds.
- [x] After `max_retries` exhausted, `GatekeeperMaxRetriesError` is raised.
- [x] `get_cost_summary()` returns correct accumulated token counts after a session.
- [x] Queue full → `BackpressureError` raised, no calls dropped silently.

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
