"""Import reviewed batch images by explicit IDs; never infer poses from filenames.

Run with ``python -m panelforge.infrastructure.personal_pose_import --help``.
The default is a dry run. No network, model or running service is involved.
"""
import argparse
from contextlib import contextmanager
from datetime import UTC, datetime
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re

from PIL import Image

from .pose_catalog import LocalPoseCatalog, MAX_IMAGE_BYTES, MAX_INDEX_BYTES, PERSONAL_INDEX_NAME, validate_personal_index
from .storage.local import LocalAssetStore, _atomic_write, _json_bytes


def digest(data):
    return hashlib.sha256(data).hexdigest()


def identity(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", value):
        raise ValueError("Identifiant d’import invalide.")
    return value


def local_path(root, relative):
    path = root / relative
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("Chemin d’import hors du catalogue personnel.")
    return path


def read_index(path):
    if path.is_symlink():
        raise ValueError("Le catalogue personnel ne peut pas être un lien.")
    if not path.exists():
        return None
    if path.stat().st_size > MAX_INDEX_BYTES:
        raise ValueError("Catalogue personnel trop volumineux.")
    data = path.read_bytes()
    validate_personal_index(json.loads(data))
    return data


@contextmanager
def import_lock(root):
    root.mkdir(parents=True, exist_ok=True)
    path = root / ".import.lock"
    try:
        stream = path.open("x", encoding="utf-8")
    except FileExistsError as error:
        raise ValueError("Un import de poses est déjà en cours (.import.lock).") from error
    try:
        with stream:
            stream.write(datetime.now(UTC).isoformat())
        yield
    finally:
        path.unlink()


def prepare(workspace, manifest):
    """Validate source provenance and prepare originals and small PNG thumbnails."""
    if (not isinstance(manifest, dict) or manifest.get("schema_version") != 1
            or not isinstance(manifest.get("entries"), list) or not 1 <= len(manifest["entries"]) <= 1000):
        raise ValueError("Manifeste d’import vide ou invalide.")
    import_id = identity(manifest.get("import_id"))
    batch_id = identity(manifest.get("batch_id"))
    batch = json.loads((workspace / "creation_batches" / (batch_id + ".json")).read_bytes())
    if batch.get("batch_id") != batch_id:
        raise ValueError("Identité du lot incompatible.")
    items = {item["item_id"]: item for item in batch["items"]}
    excluded = set(manifest.get("exclude_entire_items", []))
    excluded_initial = set(manifest.get("exclude_initial_only", []))
    assets = LocalAssetStore(workspace)
    entries, files, sources = [], {}, set()
    for reviewed in manifest["entries"]:
        entry = dict(reviewed)
        source = entry.get("provenance", {})
        item_id, render_id = source.get("item_id"), source.get("render_id")
        source_key = (item_id, render_id)
        if source.get("batch_id") != batch_id or source_key in sources:
            raise ValueError("Source d’image absente ou dupliquée.")
        if item_id in excluded or (item_id in excluded_initial and render_id == "initial"):
            raise ValueError("Une image exclue figure dans le manifeste.")
        sources.add(source_key)
        item = items.get(item_id)
        render = item if render_id == "initial" else next((r for r in (item or {}).get("renders", []) if r["render_id"] == render_id), None)
        if not render or render.get("image_status" if render_id == "initial" else "status") != "succeeded":
            raise ValueError("Le rendu sélectionné n’est pas terminé.")
        if render.get("attempt_id") != source.get("attempt_id") or render.get("output_asset_id") != source.get("asset_id"):
            raise ValueError("Les identifiants du rendu sélectionné ont changé.")
        asset, content = assets.read_verified(source["asset_id"])
        if len(content) > MAX_IMAGE_BYTES or digest(content) != entry.get("sha256") or asset.media_type != "image/png":
            raise ValueError("L’image source ne correspond plus à la revue.")
        with Image.open(BytesIO(content)) as image:
            if image.format != "PNG" or image.width * image.height > 40_000_000:
                raise ValueError("Format ou dimensions de source invalides.")
            image.verify()
        with Image.open(BytesIO(content)) as image:
            image.thumbnail((320, 480), Image.Resampling.LANCZOS)
            output = BytesIO()
            image.save(output, "PNG")
        thumbnail = output.getvalue()
        entry["original"] = f"img/{identity(entry['id'])}.png"
        entry["thumbnail"] = f"thumbs/{entry['id']}.png"
        entry["thumbnail_sha256"] = digest(thumbnail)
        entry["import_id"] = import_id
        files[entry["original"]], files[entry["thumbnail"]] = content, thumbnail
        entries.append(entry)
    index = dict(schema_version=1, source="personal", entries=entries, revision=digest(_json_bytes(entries)))
    validate_personal_index(index)
    return entries, files


def import_poses(workspace, manifest, *, apply=False):
    workspace = Path(workspace).resolve()
    root = LocalPoseCatalog(workspace).root / "personal"
    if not root.resolve().is_relative_to(workspace) or root.is_symlink():
        raise ValueError("Catalogue personnel hors du workspace.")
    entries, files = prepare(workspace, manifest)
    index_path = root / PERSONAL_INDEX_NAME

    def read_current():
        return read_index(index_path if index_path.exists() else root / "catalog.json")

    def plan():
        before = read_current()
        current = json.loads(before)["entries"] if before else []
        by_id = {e["id"]: e for e in current}
        added = []
        for entry in entries:
            if entry["id"] in by_id:
                if entry != by_id[entry["id"]]:
                    raise ValueError("Une fiche existante porte le même ID avec un autre contenu.")
                if any(not local_path(root, entry[key]).is_file() for key in ("original", "thumbnail")):
                    raise ValueError("Import déjà indexé mais fichier manquant : restauration nécessaire.")
            else:
                added.append(entry)
        for relative, content in files.items():
            path = local_path(root, relative)
            if path.exists() and digest(path.read_bytes()) != digest(content):
                raise ValueError("Un fichier existant porte le même ID avec un autre contenu.")
        merged = current + added
        index = dict(schema_version=1, source="personal", entries=merged, revision=digest(_json_bytes(merged)))
        validate_personal_index(index)
        after = _json_bytes(index)
        if len(after) > MAX_INDEX_BYTES:
            raise ValueError("Catalogue fusionné trop volumineux.")
        return before, after, added

    before, after, added = plan()
    report = dict(import_id=manifest["import_id"], applied=False, selected_images=len(entries),
                  selected_poses=len({e["pose_id"] for e in entries}), added_images=len(added),
                  unchanged_images=len(entries)-len(added))
    if not apply:
        return report
    with import_lock(root):
        before, after, added = plan()
        # Existing identical entries are retained without rewriting their index.
        if not added:
            for relative in files:
                if not local_path(root, relative).is_file():
                    raise ValueError("Import déjà indexé mais fichier manquant : restauration nécessaire.")
            return {**report, "added_images": 0, "unchanged_images": len(entries), "applied": True}
        backup = local_path(root, "imports/" + identity(manifest["import_id"]))
        receipt = dict(import_id=manifest["import_id"], before_exists=before is not None,
                       before_sha256=digest(before) if before else None, after_sha256=digest(after),
                       added_ids=[e["id"] for e in added], created_at=datetime.now(UTC).isoformat())
        if backup.exists():
            previous = json.loads((backup / "receipt.json").read_bytes())
            if (previous["before_sha256"] != receipt["before_sha256"]
                    or previous["after_sha256"] != receipt["after_sha256"]
                    or json.loads((backup / "manifest.json").read_bytes()) != manifest):
                raise ValueError("Identifiant d’import déjà utilisé pour une autre sélection.")
        else:
            backup.mkdir(parents=True)
            if before is not None:
                _atomic_write(backup / "before.catalog.json", before)
            _atomic_write(backup / "after.catalog.json", after)
            _atomic_write(backup / "manifest.json", _json_bytes(manifest))
            _atomic_write(backup / "receipt.json", _json_bytes(receipt))
        for relative, content in files.items():
            path = local_path(root, relative)
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                _atomic_write(path, content)
        if read_current() != before:
            raise ValueError("Le catalogue a changé pendant l’import ; fusion interrompue.")
        # Publish only once every referenced file is in place. Old media stay intact.
        _atomic_write(index_path, after)
    return {**report, "applied": True, "added_images": len(added),
            "unchanged_images": len(entries)-len(added), "backup": str(backup)}


def rollback(workspace, import_id, *, apply=False):
    workspace = Path(workspace).resolve()
    root = LocalPoseCatalog(workspace).root / "personal"
    if not root.resolve().is_relative_to(workspace) or root.is_symlink():
        raise ValueError("Catalogue personnel hors du workspace.")
    backup = local_path(root, "imports/" + identity(import_id))
    receipt = json.loads((backup / "receipt.json").read_bytes())
    before = (backup / "before.catalog.json").read_bytes() if receipt["before_exists"] else None
    if before is not None:
        validate_personal_index(json.loads(before))
        if digest(before) != receipt["before_sha256"]:
            raise ValueError("Sauvegarde modifiée.")

    def check():
        current = read_index(root / PERSONAL_INDEX_NAME)
        if current is None or digest(current) != receipt["after_sha256"]:
            raise ValueError("Le catalogue a changé depuis cet import ; retour arrière refusé.")

    check()
    if apply:
        with import_lock(root):
            check()
            if before is None:
                (root / PERSONAL_INDEX_NAME).unlink()
            else:
                _atomic_write(root / PERSONAL_INDEX_NAME, before)
    return dict(import_id=import_id, rollback=True, applied=apply, images_removed_from_index=len(receipt["added_ids"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--manifest", type=Path)
    source.add_argument("--rollback", metavar="IMPORT_ID")
    parser.add_argument("--apply", action="store_true", help="Commit the validated import or rollback; otherwise dry-run only.")
    args = parser.parse_args()
    try:
        result = (rollback(args.workspace, args.rollback, apply=args.apply) if args.rollback else
                  import_poses(args.workspace, json.loads(args.manifest.read_text(encoding="utf-8")), apply=args.apply))
    except (ValueError, KeyError, TypeError, OSError) as error:
        parser.exit(2, str(error) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
