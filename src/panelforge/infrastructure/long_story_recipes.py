"""Load the explicitly versioned long-story editorial package."""
from pathlib import Path
import json

from panelforge.domain.long_stories import ENGINE, PROFILES, fingerprint


class LongStoryRecipes:
    def __init__(self, root):
        self.root = Path(root)

    def snapshot(self):
        manifest = json.loads((self.root / "manifest.json").read_text(encoding="utf-8"))
        if manifest.get("engine") != ENGINE or set(manifest.get("prompts", {})) != {"common", "ideas", "outline", "write", "review"}:
            raise ValueError("Recette longue V2 inconnue ou incomplète.")
        profiles = manifest.get("profiles", {})
        if set(profiles) != set(PROFILES) or any(not isinstance(value, str) or not value.strip() for value in profiles.values()):
            raise ValueError("Profils narratifs V2 incomplets.")
        prompts = {}
        for key, filename in manifest["prompts"].items():
            path = (self.root / filename).resolve()
            if path.parent != self.root.resolve():
                raise ValueError("Source éditoriale hors de la recette.")
            prompts[key] = path.read_text(encoding="utf-8")
        return {"revision": 4, "engine": ENGINE.copy(), "prompts": prompts,
                "profiles": manifest["profiles"], "fingerprint": fingerprint([manifest, prompts])}
