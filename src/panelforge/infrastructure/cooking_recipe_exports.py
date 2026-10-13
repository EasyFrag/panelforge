"""Download ordered clips without rendering or concatenating videos."""
import json
from pathlib import Path
import re
import tempfile
import unicodedata
from zipfile import ZIP_STORED, ZipFile


def slug(value):
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", value).strip("_.")[:70] or "recette"


class CookingRecipeExports:
    def __init__(self, assets):
        self.assets = assets

    def create(self, selection):
        handle = tempfile.NamedTemporaryFile(prefix="panelforge-recette-", suffix=".zip", delete=False)
        path = Path(handle.name)
        handle.close()
        try:
            manifest = dict(selection, clips=[])
            with ZipFile(path, "w", compression=ZIP_STORED, allowZip64=True) as archive:
                for clip in selection["clips"]:
                    asset = self.assets.get(clip["asset_id"])
                    if asset.media_type not in {"video/mp4", "video/webm"}:
                        raise ValueError("Le résultat choisi n’est pas une vidéo exportable.")
                    extension = ".webm" if asset.media_type == "video/webm" else ".mp4"
                    name = f"{clip['index']:02d}_{slug(clip['title'])}{extension}"
                    archive.write(self.assets.verified_path(clip["asset_id"]), arcname=name)
                    manifest["clips"].append(dict(clip, filename=name))
                archive.writestr("ordre_des_clips.json", json.dumps(manifest, ensure_ascii=False, indent=2))
            return path, slug(selection["name"]) + "_clips.zip"
        except BaseException:
            path.unlink(missing_ok=True)
            raise
