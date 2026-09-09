"""Keep DLSS media in the visible output folder; assets contain references only."""

import hashlib
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import tempfile


class DlssOutputs:
    def __init__(self, root, assets, *, fallback_roots=()):
        self.root = Path(root).resolve()
        self.assets = assets
        self.roots = (self.root, *(Path(path).resolve() for path in fallback_roots))

    def save(self, job, content, *, role, source=None):
        job_id = job["job_id"]
        if not re.fullmatch(r"dlss-[0-9a-f]{32}", job_id) or role not in {"enhanced", "result"}:
            raise ValueError("Identifiant de résultat DLSS invalide.")
        digest = hashlib.sha256(content).hexdigest()
        media_type = job["snapshot"]["media_type"]
        if source is not None:
            path = self._comfy_path(source)
        else:
            # Resizing/remasking produces a genuinely different image, not a duplicate.
            if media_type != "image/png":
                raise ValueError("Une vidéo DLSS doit référencer sa sortie Comfy existante.")
            path = self.root / "dlss" / f"{job_id}_{role}.png"
            if not path.resolve().is_relative_to(self.root) or path.is_symlink():
                raise ValueError("Le résultat DLSS sort de son dossier configuré.")
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                    raise ValueError("Un autre résultat DLSS occupe déjà ce nom : " + str(path))
            else:
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
        asset = self.assets.register_file(path, media_type, source_run_id=job_id, expected_sha256=digest)
        return asset, str(path)

    def _comfy_path(self, source):
        filename, subfolder = source.get("filename"), source.get("subfolder", "")
        if not isinstance(filename, str) or not filename or any(c in filename for c in "/\\:"):
            raise ValueError("Nom de sortie Comfy DLSS invalide.")
        if not isinstance(subfolder, str) or source.get("type", "output") != "output":
            raise ValueError("Dossier de sortie Comfy DLSS invalide.")
        for value in (PureWindowsPath(subfolder), PurePosixPath(subfolder)):
            if value.is_absolute() or value.drive or ".." in value.parts:
                raise ValueError("La sortie DLSS doit rester dans son dossier configuré.")
        for root in self.roots:
            candidate = (root / subfolder / filename)
            if not candidate.resolve().is_relative_to(root):
                raise ValueError("La sortie DLSS sort de son dossier configuré.")
            if candidate.is_file():
                return candidate
        raise FileNotFoundError(
            "Sortie DLSS locale introuvable. Vérifie --dlss-output-root : "
            + ", ".join(str(root / subfolder / filename) for root in self.roots))
