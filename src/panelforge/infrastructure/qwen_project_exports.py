"""Portable Qwen projects, including references, conversation and exact attempts."""

from copy import deepcopy
from io import BytesIO
from pathlib import Path
import re
import zipfile

from .storage.local import _atomic_write, _json_bytes


def project_files(project, assets, store):
    asset_ids = set()

    def collect(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key.endswith("asset_id") and isinstance(child, str):
                    asset_ids.add(child)
                else:
                    collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)

    collect(project)
    record = deepcopy(project)
    record["asset_files"] = {}
    for asset_id in sorted(asset_ids):
        asset = assets.get(asset_id)
        extension = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}[asset.media_type]
        filename = f"medias/{asset_id}{extension}"
        record["asset_files"][asset_id] = filename
        yield filename, assets.read_bytes(asset_id)
    for stage in project["stages"]:
        if stage["source_asset_id"] and stage["index"] == 1:
            yield "00_original/00_original.png", assets.read_bytes(stage["source_asset_id"])
        accepted = next((a for a in stage["attempts"] if a["id"] == stage["accepted_attempt_id"]), None)
        if accepted:
            offset = 1 if project["stages"][0]["mode"] == "composition" else 0
            folder = "00_base" if stage["mode"] == "composition" else f"{stage['index'] - offset:02d}_{_slug(stage['label'])}"
            yield f"{folder}/{folder}.png", assets.read_bytes(accepted["output_asset_id"])
            yield f"{folder}/{folder}.json", _json_bytes(accepted)
        for attempt in stage["attempts"]:
            if attempt.get("workflow_sha256"):
                yield f"workflows/{attempt['id']}.json", store.read_workflow(project["id"], attempt["id"])
    yield "project.json", _json_bytes(record)


def project_zip(project, assets, store):
    content = BytesIO()
    with zipfile.ZipFile(content, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for filename, data in project_files(project, assets, store):
            archive.writestr(filename, data)
    return content.getvalue()


class LocalQwenProjectExporter:
    def __init__(self, root):
        self.root = Path(root).expanduser().resolve()

    def export(self, project, assets, store):
        # Keep an existing destination stable when the project is renamed.
        previous = Path(project["export_path"]) if project.get("export_path") else None
        directory = previous if previous and previous.parent == self.root else self.root / f"{_slug(project['name'])}__{project['id'][-8:]}"
        directory.mkdir(parents=True, exist_ok=True)
        if directory.is_symlink():
            raise ValueError("Lien de dossier d’export interdit.")
        for filename, data in project_files(project, assets, store):
            target = directory / filename
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.resolve().is_relative_to(directory.resolve()):
                raise ValueError("Chemin d’export invalide.")
            _atomic_write(target, data)
        return str(directory)


def _slug(value):
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:48] or "modification"
