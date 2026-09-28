"""Explicit immutable editorial packages. No discovery and no executable archives."""
from copy import deepcopy
from pathlib import Path
import hashlib
import json


class StoryEditions:
    def __init__(self, root):
        self.root = Path(root)

    def catalog(self):
        # A running v1/v2 process still reads catalog.json. Activate v3 only
        # when this reader is loaded, without invalidating concurrent work.
        path = self.root / "catalog-v3.json"
        if not path.is_file():
            path = self.root / "catalog.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        identities = [item["id"] for item in data["editions"]]
        if len(identities) != len(set(identities)) or data["latest"] not in identities:
            raise ValueError("Catalogue des versions d’écriture invalide.")
        return data

    def get(self, identity=None):
        catalog = self.catalog()
        identity = catalog["latest"] if identity in {None, "latest"} else identity
        item = next((i for i in catalog["editions"] if i["id"] == identity), None)
        if item is None:
            raise ValueError("Cette version d’écriture n’est pas installée. Choisis une version disponible.")
        path = (self.root / item["file"]).resolve()
        if path.parent != self.root.resolve():
            raise ValueError("Version d’écriture hors du catalogue.")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != item["sha256"]:
            raise ValueError("Une version d’écriture archivée a été modifiée. Restaure son fichier avant de continuer.")
        package = json.loads(raw)
        if package["fingerprint"] != item["fingerprint"] or package["policy_version"] not in {1, 2, 3}:
            raise ValueError("Version d’écriture incompatible.")
        package["edition"] = {key: item[key] for key in ("id", "label", "date", "summary", "fingerprint")}
        package["edition"]["policy_version"] = package["policy_version"]
        return package

    def identify(self, fingerprint):
        item = next((i for i in self.catalog()["editions"] if i["fingerprint"] == fingerprint), None)
        return self.get(item["id"]) if item else None

    def public_catalog(self):
        data = self.catalog()
        return dict(latest=data["latest"], editions=[deepcopy(self.get(i["id"])["edition"]) for i in data["editions"]])
