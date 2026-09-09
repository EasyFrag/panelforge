"""Dated copies to the server mount, independent of rendering and local asset storage."""

from datetime import date
import hashlib
import os
from pathlib import Path
import re
import tempfile


class DlssVideoExporter:
    def __init__(self, root):
        self.root = Path(root)  # No network filesystem access during Lab startup.
        if not self.root.is_absolute():
            raise ValueError("Le dossier d’export DLSS doit être absolu.")

    def target(self, job_id, day):
        if not re.fullmatch(r"dlss-[0-9a-f]{32}", job_id) or date.fromisoformat(day).isoformat() != day:
            raise ValueError("Identifiant ou date d’export DLSS invalide.")
        return self.root / day / (job_id + ".mp4")

    def export(self, job, video, report):
        target = self.target(job["job_id"], job["video_export"]["date"])
        if str(target) != job["video_export"]["path"]:
            raise ValueError("Le dossier d’export configuré a changé ; rétablis-le avant de reprendre la copie.")
        if not self.root.parent.is_dir():
            raise OSError("Le partage vidéo du serveur n’est pas accessible.")
        target.parent.mkdir(parents=True, exist_ok=True)
        for path, content in ((target, video), (target.with_suffix(".json"), report)):
            if path.is_file():
                with path.open("rb") as existing:
                    digest = hashlib.file_digest(existing, "sha256").digest()
                if digest != hashlib.sha256(content).digest():
                    raise ValueError("Un autre fichier occupe déjà le nom d’export : " + str(path))
                continue
            descriptor, temporary = tempfile.mkstemp(prefix=".dlss-", suffix=".tmp", dir=path.parent)
            try:
                with os.fdopen(descriptor, "wb") as output:
                    output.write(content)
                    output.flush()
                    os.fsync(output.fileno())
                os.replace(temporary, path)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
        return str(target)
