# PRD — Structured Logging
**Version:** 1.00  
**Date:** 2026-05-23  
**File:** `src/debate/shared/logger.py`

---

## 1. Description & Theoretical Background

The logging system provides structured, persistent, auditable records of all system events: agent messages, Judge decisions, Gatekeeper calls, Watchdog events, and errors. Logs are the primary tool for debugging, auditing costs, and reviewing debate transcripts post-run.

The system uses a **FIFO rotating file logger**: logs are written to sequentially numbered files. When a file reaches the line limit, a new file is opened. When the total number of files reaches the maximum, the oldest file is deleted (FIFO — first in, first out). All configuration comes from `config/logging_config.json`.

This approach guarantees bounded disk usage while preserving the most recent history — critical for long-running debate sessions.

---

## 2. Responsibilities

- Accept structured log entries from any component (agents, gatekeeper, watchdog, orchestrator).
- Write entries to the current log file in a consistent, parseable format.
- Rotate to a new file when the current file reaches `max_lines_per_file`.
- Delete the oldest file when total file count exceeds `max_files`.
- Provide a thread-safe `log()` method (multiple processes/threads write concurrently).
- Support log levels: `DEBUG`, `INFO`, `WARNING`, `ERROR`.
- Filter entries below the configured minimum level.

---

## 3. Interface

```python
class DebateLogger:
    """FIFO rotating structured logger."""

    def __init__(self, config: LoggingConfig):
        """Initialize from LoggingConfig; create log_dir if it does not exist."""

    def log(self, level: str, component: str, message: str, **extra) -> None:
        """
        Write a structured log entry.
        Thread-safe via internal Lock.
        Rotates file if line limit reached.
        """

    def get_current_file(self) -> str:
        """Return path to the current log file."""

    def get_all_files(self) -> list[str]:
        """Return sorted list of all existing log files."""
```

---

## 4. Log Entry Format

Each line is a structured string:

```
[TIMESTAMP] LEVEL | component=COMPONENT | message=MESSAGE | key=value ...
```

Example entries:

```
[2026-05-23 14:32:01] INFO  | component=orchestrator | message=Debate started | topic=AI will replace jobs | rounds=10
[2026-05-23 14:32:15] INFO  | component=pro_agent | message=Argument sent | round=1 | citations=2
[2026-05-23 14:32:18] INFO  | component=judge | message=Reprimand issued | target=pro_agent | reason=no_citations
[2026-05-23 14:32:45] INFO  | component=gatekeeper | message=API call | service=llm | status=success | input_tokens=412 | output_tokens=289 | latency_ms=1820
[2026-05-23 14:33:10] WARNING | component=watchdog | message=Timeout detected | agent=con_agent | timeout_s=120
[2026-05-23 14:33:12] WARNING | component=watchdog | message=Agent restarted | agent=con_agent
[2026-05-23 14:35:00] INFO  | component=judge | message=Verdict declared | winner=con_agent | score_pro=72 | score_con=85
```

---

## 5. FIFO Rotation Logic

```
[log() called]
      │
      ▼
[write line to current file]
[increment line counter]
      │
[line counter >= max_lines_per_file?]
      │ YES
      ▼
[open new file: debate_log_NNN.log]
[reset line counter to 0]
      │
[total files > max_files?]
      │ YES
      ▼
[delete oldest file (lowest NNN)]
```

File naming: `logs/debate_log_001.log`, `logs/debate_log_002.log`, etc.
Sequence number wraps at 999 (configurable).

---

## 6. Configuration

Loaded from `config/logging_config.json`:

```json
{
  "version": "1.00",
  "logging": {
    "max_files": 20,
    "max_lines_per_file": 500,
    "log_dir": "logs/",
    "level": "INFO"
  }
}
```

| Parameter | Description |
|-----------|-------------|
| `max_files` | Maximum number of log files to retain |
| `max_lines_per_file` | Maximum lines before rotating to a new file |
| `log_dir` | Directory for log files (relative to project root) |
| `level` | Minimum log level to write (`DEBUG`/`INFO`/`WARNING`/`ERROR`) |

---

## 7. Thread Safety

Multiple agent processes and the orchestrator write logs concurrently. Thread safety is ensured by:
- A `threading.Lock` protecting the write operation and line counter.
- `log()` acquires the lock, writes, increments, checks rotation, releases the lock.
- No log entry is split across files — rotation happens between entries.

---

## 8. Performance Requirements

| Metric | Target |
|--------|--------|
| Write latency per entry | < 5ms |
| Disk space per full log set (20 files × 500 lines) | < 5MB |
| Thread contention on `log()` | No deadlock; no starvation |

---

## 9. Constraints

- All configuration MUST come from `config/logging_config.json` — no hardcoded limits.
- Log directory is created automatically if it does not exist.
- `log()` MUST NOT raise exceptions to the caller — if writing fails, the error is printed to stderr and silently swallowed.
- Log files MUST be UTF-8 encoded.
- Entries MUST include a timestamp, level, component, and message at minimum.

---

## 10. Alternatives Considered

| Alternative | Reason Rejected |
|-------------|----------------|
| Python's built-in `logging` module with `RotatingFileHandler` | Rotates by file size (bytes), not by line count; spec requires line-based rotation |
| Single log file | Unbounded disk usage; not FIFO |
| Per-component log files | Harder to correlate events across components by timestamp |
| JSON-per-line log format | Harder to read during debugging; structured string format is sufficient |

---

## 11. Success Criteria

- [ ] Writing 500 lines to a fresh logger creates exactly 1 file.
- [ ] Writing 501 lines creates 2 files; the second file contains 1 line.
- [ ] Writing enough lines to fill 21 files causes the oldest file to be deleted (max_files=20).
- [ ] Concurrent writes from 3 threads produce no interleaved or corrupted lines.
- [ ] Entries below the configured level are not written.
- [ ] A write failure does not raise an exception to the caller.

---

## 12. Test Scenarios

| Scenario | Expected Outcome |
|----------|-----------------|
| Log 500 lines | 1 file created; line count = 500 |
| Log 501 lines | 2 files; first has 500, second has 1 |
| Log enough to create 21 files (max=20) | File 1 deleted; files 2–21 retained |
| Log entry with level DEBUG when config level=INFO | Entry not written to file |
| 3 concurrent threads each log 100 entries | 300 entries in files; no corruption |
| Log directory does not exist at startup | Directory created automatically |
