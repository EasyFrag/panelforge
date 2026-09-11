"""Atomic, independently versioned analysis records. No user-project migration."""
from copy import deepcopy
from datetime import datetime, UTC
import json
import os
from pathlib import Path
import re
import tempfile
from threading import RLock


class LocalMediaAnalysisStore:
    def __init__(self, workspace_root):
        self.root = Path(workspace_root).resolve() / "media_analysis"
        self._lock = RLock()

    def _path(self, analysis_id):
        if not isinstance(analysis_id, str) or not re.fullmatch(r"analysis-[a-f0-9]{32}", analysis_id):
            raise ValueError("Identifiant d’analyse invalide.")
        path = self.root / f"{analysis_id}.json"
        if path.is_symlink():
            raise ValueError("Lien de stockage non autorisé.")
        return path

    def get(self, analysis_id):
        with self._lock:
            value = json.loads(self._path(analysis_id).read_text(encoding="utf-8"))
        if value.get("schema_version") not in (1, 2) or value.get("analysis_id") != analysis_id:
            raise ValueError("Format d’analyse indisponible.")
        return value

    def save(self, record):
        with self._lock:
            path = self._path(record["analysis_id"])
            self.root.mkdir(parents=True, exist_ok=True)
            value = deepcopy(record)
            value["updated_at"] = datetime.now(UTC).isoformat()
            value.setdefault("created_at", value["updated_at"])
            value["schema_version"] = 2
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.root, delete=False) as file:
                    temporary = file.name
                    json.dump(value, file, ensure_ascii=False, indent=2, allow_nan=False)
                    file.flush()
                    os.fsync(file.fileno())
                os.replace(temporary, path)
            finally:
                if temporary and os.path.exists(temporary):
                    os.unlink(temporary)
            return value

    def list(self, limit=3):
        if type(limit) is not int or not 1 <= limit <= 30:
            raise ValueError("Limite d’historique invalide.")
        if not self.root.exists():
            return []
        files = sorted(self.root.glob("analysis-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        result = []
        for path in files:
            try:
                result.append(self.get(path.stem))
            except (ValueError, OSError):
                continue
            if len(result) == limit:
                break
        return result
