"""Load the explicitly versioned long-story editorial package."""
from pathlib import Path
import json

from panelforge.domain.long_stories import ENGINE, PROFILES, fingerprint


class LongStoryRecipes:
    def __init__(self, root):
        self.root = Path(root)
        from .story_editions import StoryEditions
        self.editions = StoryEditions(self.root / "editions")

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
        roles = {}
        paths = manifest.get("role_prompts", {})
        if paths and set(paths) != {"common", "compose", "edit", "write", "review", "discuss"}:
            raise ValueError("Consignes par rôle incomplètes.")
        for key, filename in paths.items():
            path = (self.root / filename).resolve()
            if path.parent != self.root.resolve():
                raise ValueError("Source éditoriale hors de la recette.")
            roles[key] = path.read_text(encoding="utf-8")
        quality = {}
        quality_paths = manifest.get("quality_prompts", {})
        if quality_paths and set(quality_paths) != {"common", "compose", "edit", "write", "review"}:
            raise ValueError("Consignes de qualité incomplètes.")
        for key, filename in quality_paths.items():
            path = (self.root / filename).resolve()
            if path.parent != self.root.resolve():
                raise ValueError("Source éditoriale hors de la recette.")
            quality[key] = path.read_text(encoding="utf-8")
        tones = {}
        for identity, sources in manifest.get("tone_profiles", {}).items():
            if identity != "black_comedy_street_v1" or set(sources) != {"common", "compose", "write", "review"}:
                raise ValueError("Profil de ton inconnu ou incomplet.")
            tones[identity] = {}
            for role, filename in sources.items():
                path = (self.root / filename).resolve()
                if path.parent != self.root.resolve():
                    raise ValueError("Source éditoriale hors de la recette.")
                text = path.read_text(encoding="utf-8")
                if not text.strip():
                    raise ValueError("Consigne de ton vide.")
                tones[identity][role] = text
        sources = [manifest, prompts, roles, quality]
        if tones:
            sources.append(tones)
        return {"revision": 8 if tones else 7 if quality else 6 if roles else 5, "engine": ENGINE.copy(), "prompts": prompts,
                "role_prompts": roles, "quality_prompts": quality, "tone_profiles": tones,
                "profiles": manifest["profiles"], "fingerprint": fingerprint(sources)}
