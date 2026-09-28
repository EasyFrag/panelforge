"""Read-only, exact-asset scene provenance for the video factory."""
from .krea2_image_metadata import recover_krea2_scene_context


class FactoryImageContext:
    def __init__(self, *, assets, projects):
        self.assets, self.projects = assets, projects

    def __call__(self, asset_id, source_id=None):
        context = dict(asset_id=asset_id, origin="none", prompt="", intention="", style="")
        # No project scans: the supplied project ID and exact output asset identify the attempt.
        attempt = None
        if source_id and source_id.startswith("krea2-create-"):
            try:
                project = self.projects.get(source_id)
                attempt = next((a for a in project.attempts if asset_id in
                                (a.output_asset_id, getattr(a, "pre_flux_asset_id", None))), None)
            except (FileNotFoundError, KeyError, ValueError):
                pass
        try:
            embedded = recover_krea2_scene_context(self.assets.read_bytes(asset_id))
        except (ValueError, OSError):
            embedded = {}
        if attempt is not None:
            context.update(origin="KREA · essai image", prompt=(attempt.canonical_prompt or attempt.prompt or "")[:12000])
            art = getattr(attempt, "art_direction", None)
            context["style"] = (getattr(art, "prompt", None) or getattr(art, "name", "") or "")[:3000]
            # A mutable project's current intention is deliberately not read.
            if (embedded.get("project_id") == source_id and
                    embedded.get("attempt_id") == attempt.attempt_id):
                context["intention"] = embedded.get("intention", "")
        elif embedded:
            context.update({key: embedded.get(key, "") for key in ("prompt", "intention", "style")})
            context["origin"] = "PNG KREA / ComfyUI"
        return context
