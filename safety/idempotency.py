"""Duplicate delivery must not duplicate records.

Telegram (and every other at-least-once transport) will redeliver. The guard is
an atomic check-and-set on the transport's own message id.
"""
from __future__ import annotations
import json
import os
import tempfile
import threading
from collections import OrderedDict
from pathlib import Path


class IdempotencyStore:
    def __init__(self, path: str | os.PathLike | None = None, capacity: int = 5000):
        self._lock = threading.Lock()
        self._seen: OrderedDict[str, bool] = OrderedDict()
        self._capacity = capacity
        self._path = Path(path) if path else None
        if self._path and self._path.exists():
            try:
                for key in json.loads(self._path.read_text())["seen"]:
                    self._seen[key] = True
            except (ValueError, KeyError, OSError):
                # A corrupt store must not stop the service. Starting empty
                # risks reprocessing recent messages; refusing to start risks
                # everything. Reprocessing is the lesser failure.
                self._seen.clear()

    @staticmethod
    def key(*parts: object) -> str:
        return ":".join(str(p) for p in parts)

    def once(self, key: str) -> bool:
        """Atomically claim a key. True the first time, False on every repeat."""
        with self._lock:
            if key in self._seen:
                return False
            self._seen[key] = True
            while len(self._seen) > self._capacity:
                self._seen.popitem(last=False)
            self._flush()
            return True

    def seen(self, key: str) -> bool:
        with self._lock:
            return key in self._seen

    def _flush(self) -> None:
        if not self._path:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # Write-then-rename: a crash mid-write leaves the old file intact
        # rather than a truncated one.
        fd, tmp = tempfile.mkstemp(dir=str(self._path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as fh:
                json.dump({"seen": list(self._seen)}, fh)
            os.replace(tmp, self._path)
        except OSError:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise
