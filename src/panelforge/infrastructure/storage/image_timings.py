"""Best-effort image/slow-operation journal, bounded to 6 MiB by default."""
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


class _QuietHandler(RotatingFileHandler):
    def handleError(self, record):
        # Diagnostics must not fill stderr or expose a record on write failure.
        pass


class LocalImageTimings:
    def __init__(self, workspace_root, *, max_bytes=2 * 1024 * 1024, backups=2):
        self.path = Path(workspace_root) / "system" / "image-timings.jsonl"
        self._handler = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._handler = _QuietHandler(self.path, maxBytes=max_bytes,
                                         backupCount=backups, encoding="utf-8", delay=True)
            self._handler.setFormatter(logging.Formatter("%(message)s"))
        except OSError:
            pass

    def __call__(self, record):
        if self._handler is None:
            return
        try:
            message = json.dumps(record, ensure_ascii=True, separators=(",", ":"), allow_nan=False)
            if len(message) > 64 * 1024:
                return
            self._handler.handle(logging.LogRecord("image-timings", logging.INFO, "", 0, message, (), None))
        except Exception:
            pass

    def close(self):
        if self._handler is not None:
            self._handler.close()
