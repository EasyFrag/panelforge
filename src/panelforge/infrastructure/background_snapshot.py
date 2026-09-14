"""Small, persisted read model with single-flight background revalidation.

Loaders only discover metadata. They must never load models or submit jobs.
"""
from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
from threading import Lock, Thread
from time import time


class BackgroundSnapshot:
    def __init__(self, loader, *, path: Path | None = None, scope="", ttl=300, clock=time, validate=lambda value: True):
        self.loader, self.path, self.scope = loader, path, scope
        self.ttl, self.clock = ttl, clock
        self._lock = Lock()
        self._persist_lock = Lock()
        self._value = None
        self._checked = 0.0
        self._retry_at = 0.0
        self._error = None
        self._refreshing = False
        self._revision = 0
        if path is not None:
            try:
                saved = json.loads(path.read_text(encoding="utf-8"))
                if saved["schema"] == 1 and saved["scope"] == scope and validate(saved["value"]):
                    self._value = saved["value"]
                    self._checked = float(saved["checked"])
            except (OSError, ValueError, TypeError, KeyError):
                pass

    def read(self, *, force=False):
        with self._lock:
            stale = self._value is None or self._error is not None or self.clock() - self._checked >= self.ttl
            if not self._refreshing and (force or (stale and self.clock() >= self._retry_at)):
                self._refreshing = True
                Thread(target=self._refresh, args=(self._revision,), daemon=True,
                       name="image-lab-catalog").start()
            return deepcopy(self._value), {
                "ready": self._value is not None, "refreshing": self._refreshing,
                "stale": stale, "checked_at": self._checked or None,
                "error": self._error, "revision": self._revision,
            }

    def patch(self, transform):
        """Publish an explicit metadata edit; discard any older in-flight scan."""
        with self._lock:
            if self._value is not None:
                self._value = transform(deepcopy(self._value))
            self._revision += 1
            if self._refreshing:
                self._checked = 0.0
        self._persist()

    def _refresh(self, revision):
        try:
            value = self.loader()
            with self._lock:
                if revision == self._revision:
                    self._value = value
                    self._checked = self.clock()
                    self._error = None
                    self._retry_at = 0.0
                    self._revision += 1
            self._persist()
        except Exception as error:
            with self._lock:
                # Keep the last good snapshot, including after a restart.
                self._error = f"Actualisation indisponible ({type(error).__name__}). " + (
                    "Catalogue précédent conservé." if self._value is not None else "Réessayez avec Actualiser les modèles.")
                self._retry_at = self.clock() + 30
        finally:
            with self._lock:
                self._refreshing = False

    def _persist(self):
        if self.path is None:
            return
        # Serialize writers, never hold the read lock during disk/network IO.
        with self._persist_lock:
            with self._lock:
                saved = {"schema": 1, "scope": self.scope, "value": deepcopy(self._value),
                         "checked": self._checked}
            if saved["value"] is None:
                return
            temporary = None
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                descriptor, temporary = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
                with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                    json.dump(saved, stream, ensure_ascii=False)
                os.replace(temporary, self.path)
            except OSError:
                # An unwritable cache must not discard an otherwise valid inventory.
                pass
            finally:
                if temporary and os.path.exists(temporary):
                    os.unlink(temporary)
