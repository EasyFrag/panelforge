"""Readable factory delivery folders; source assets remain immutable and reachable."""
from datetime import datetime
import hashlib
import os
from pathlib import Path
import re
import shutil
import tempfile
import unicodedata


class VideoFactoryOutputs:
    def __init__(self, root, assets):
        self.root = Path(root).resolve()
        self.assets = assets

    def _path(self, path):
        path = Path(path)
        if not path.is_absolute() or not path.resolve().is_relative_to(self.root) or path.is_symlink():
            raise ValueError("Le résultat sort du dossier de l’usine.")
        return path

    def plan(self, item, material, previous):
        identity, asset_id = item["id"], material["asset_id"]
        if not re.fullmatch(r"factory-[0-9a-f]{32}", identity) or not re.fullmatch(r"asset-[0-9a-f]{32}", asset_id):
            raise ValueError("Identifiant de résultat invalide.")
        if material["family"] not in {"Petits hommes", "Levres", "Histoire", "Autres"}:
            raise ValueError("Famille de résultat invalide.")
        if previous.get("asset_id") == asset_id and previous.get("folder"):
            # IG may finish after midnight; retain the folder assigned to this video.
            folder = self._path(previous["folder"])
            stem = Path(previous["video_path"]).stem
            suffix = "_DLSS" if material["stage"] == "dlss" else "_Video"
            stem = stem.removesuffix(suffix)
        else:
            day = datetime.fromisoformat(material["completed_at"]).astimezone().date().isoformat()
            folder = self.root / material["family"] / day
            name = unicodedata.normalize("NFKD", material["name"]).encode("ascii", "ignore").decode()
            name = re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_.")[:70] or "video"
            stem = f"{name}_{identity[-8:]}_{asset_id[-8:]}"
            suffix = "_DLSS" if material["stage"] == "dlss" else "_Video"
        video_folder = folder if material["stage"] == "dlss" else folder / "base video"
        video = self._path(video_folder / (stem + suffix + ".mp4"))
        text = self._path(folder / (stem + "_Instagram.txt"))
        return dict(key=material["key"], asset_id=asset_id, stage=material["stage"],
                    folder=str(folder), video_path=str(video), text_path=str(text),
                    text_sha256=previous.get("text_sha256") if previous.get("asset_id") == asset_id else None,
                    status="copying", error=None, has_text=False)

    def publish(self, delivery, material):
        folder = self._path(delivery["folder"])
        folder.mkdir(parents=True, exist_ok=True)
        self._path(folder)  # Recheck after creation, including any parent junction.
        target = self._path(delivery["video_path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        self._path(target)  # The base-video subfolder must also stay inside the output root.
        source = self.assets.verified_path(material["asset_id"])
        if target.exists():
            if not os.path.samefile(source, target) and self._digest(source) != self._digest(target):
                raise ValueError("Un autre fichier occupe le nom de cette vidéo.")
        else:
            try:
                os.link(source, target)
            except FileExistsError:
                if self._digest(source) != self._digest(target):
                    raise ValueError("Un autre fichier occupe le nom de cette vidéo.")
            except OSError:
                # Different volumes or filesystems may not support hard links.
                self._copy(source, target)
        text_digest = delivery.get("text_sha256")
        if material["text"]:
            content = material["text"].encode("utf-8")
            text_digest = hashlib.sha256(content).hexdigest()
            self._write_text(self._path(delivery["text_path"]), content, delivery.get("text_sha256"))
        return dict(delivery, status="succeeded", error=None, has_text=bool(material["text"]),
                    text_sha256=text_digest)

    @staticmethod
    def _digest(path):
        with path.open("rb") as stream:
            return hashlib.file_digest(stream, "sha256").hexdigest()

    def _copy(self, source, target):
        descriptor, temporary = tempfile.mkstemp(prefix=".factory-", dir=target.parent)
        try:
            with os.fdopen(descriptor, "wb") as output, source.open("rb") as content:
                shutil.copyfileobj(content, output)
                output.flush()
                os.fsync(output.fileno())
            if target.exists():
                if self._digest(source) != self._digest(target):
                    raise ValueError("Un autre fichier occupe le nom de cette vidéo.")
            else:
                os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def _write_text(self, target, content, previous_digest):
        if target.exists():
            digest = self._digest(target)
            if digest == hashlib.sha256(content).hexdigest():
                return
            if not previous_digest or digest != previous_digest:
                raise ValueError("Le fichier Instagram a été modifié ; conservez-le avant de reprendre l’export.")
        descriptor, temporary = tempfile.mkstemp(prefix=".factory-", dir=target.parent)
        try:
            with os.fdopen(descriptor, "wb") as output:
                output.write(content)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def open_folder(self, delivery):
        folder = self._path(delivery["folder"])
        if not folder.is_dir():
            raise FileNotFoundError("Le dossier de résultat n’est pas encore disponible.")
        if os.name != "nt":
            raise ValueError("Copiez le chemin du dossier sur cette machine.")
        os.startfile(str(folder))
