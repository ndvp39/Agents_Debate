"""FIFO rotating structured logger for the debate system."""

import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from debate.shared.config import ConfigManager

_LEVELS: dict[str, int] = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3}


class DebateLogger:
    """Thread-safe, FIFO rotating file logger.

    Writes structured log entries to sequentially numbered files.
    Rotates when a file reaches max_lines_per_file; deletes the
    oldest file when total files exceeds max_files.
    """

    def __init__(self, config: ConfigManager) -> None:
        cfg = config.get_logging_config()["logging"]
        self._max_files: int = cfg["max_files"]
        self._max_lines: int = cfg["max_lines_per_file"]
        self._log_dir = Path(cfg["log_dir"])
        self._min_level: int = _LEVELS.get(cfg.get("level", "INFO"), 1)
        self._prefix: str = cfg.get("file_prefix", "debate_log_")
        self._ext: str = cfg.get("file_extension", ".log")
        self._seq_max: int = cfg.get("sequence_max", 999)
        self._lock = threading.Lock()
        self._current_file: Path | None = None
        self._line_count: int = 0
        self._seq: int = 0
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._open_new_file()

    def _open_new_file(self) -> None:
        self._seq = (self._seq % self._seq_max) + 1
        name = f"{self._prefix}{self._seq:03d}{self._ext}"
        self._current_file = self._log_dir / name
        self._line_count = 0

    def _prune_old_files(self) -> None:
        files = sorted(self._log_dir.glob(f"{self._prefix}*{self._ext}"))
        while len(files) > self._max_files:
            files[0].unlink(missing_ok=True)
            files.pop(0)

    def _format_entry(self, level: str, component: str, message: str, **extra: Any) -> str:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        parts = [f"[{ts}]", f"{level:<7}", f"| component={component}", f"| message={message}"]
        parts += [f"| {k}={v}" for k, v in extra.items()]
        return " ".join(parts)

    def _write(self, entry: str) -> None:
        try:
            assert self._current_file is not None
            with open(self._current_file, "a", encoding="utf-8") as fh:
                fh.write(entry + "\n")
            self._line_count += 1
            if self._line_count >= self._max_lines:
                self._open_new_file()
                self._prune_old_files()
        except OSError as exc:
            print(f"Logger write failed: {exc}", file=sys.stderr)

    def log(self, level: str, component: str, message: str, **extra: Any) -> None:
        """Write a structured log entry (thread-safe)."""
        if _LEVELS.get(level, 0) < self._min_level:
            return
        entry = self._format_entry(level, component, message, **extra)
        with self._lock:
            self._write(entry)

    def get_current_file(self) -> str:
        """Return the path of the current active log file."""
        return str(self._current_file)

    def get_all_files(self) -> list[str]:
        """Return sorted list of all existing log files."""
        return sorted(str(p) for p in self._log_dir.glob(f"{self._prefix}*{self._ext}"))
