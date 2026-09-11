"""On-demand video LoRA metadata, reusing the resource card metadata store.

The inventory is supplied by H3's existing cached catalog. No filesystem scan,
model hash, CivitAI lookup or model loading is performed when listing metadata.
"""

from pathlib import Path

from .krea2_resources import LocalKrea2ResourceCatalog, Krea2ResourceKind


class H3LoraResourceCatalog(LocalKrea2ResourceCatalog):
    def __init__(self, *, workspace_root, inventory, comfy=None, civitai=None):
        # The inherited annotation/remote-cache behavior is shared; discovery
        # and resource reloading below are remote-only, never use these roots.
        super().__init__(models_root=workspace_root, loras_root=workspace_root,
                         workspace_root=workspace_root, comfy=comfy, civitai=civitai)
        self._state_path = Path(workspace_root).resolve() / "h3_lora_resources.json"
        self._inventory = inventory

    def _scan(self, kind):
        if kind is not Krea2ResourceKind.LORA:
            return ()
        names, warning = self._inventory()
        if warning and not names:
            raise ValueError(warning)
        with self._lock:
            state = self._load_state()
            return tuple(self._remote_resource(name, kind=kind, state=state) for name in names)

    def _reload_resource(self, resource, state):
        return self._remote_resource(resource.comfy_name, kind=resource.kind, state=state)

    def get_by_name(self, name):
        for resource in self.list_loras():
            if resource.comfy_name == name:
                return resource
        raise KeyError(name)
