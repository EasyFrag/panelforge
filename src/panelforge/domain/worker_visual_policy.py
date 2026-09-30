"""Explicit visual-only worker contract; no description or measured scale in prose."""
from dataclasses import asdict, dataclass

VERSION = "worker.visual-only@1"


@dataclass(frozen=True, slots=True)
class WorkerVisualPolicy:
    identity_asset_id: str
    scale_asset_id: str | None = None
    depict_worker: bool = True
    version: str = VERSION

    def __post_init__(self):
        if self.version != VERSION or type(self.depict_worker) is not bool:
            raise ValueError("Contrat de référence d’ouvrier invalide.")
        for value in (self.identity_asset_id, self.scale_asset_id):
            if value is not None and (not isinstance(value, str) or not value.startswith("asset-")):
                raise ValueError("Image de référence d’ouvrier invalide.")
        if not self.identity_asset_id or self.identity_asset_id == self.scale_asset_id:
            raise ValueError("Références d’identité et d’échelle distinctes requises.")

    def as_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, value):
        if value is None:
            return None
        if (not isinstance(value, dict) or "identity_asset_id" not in value
                or set(value) - {"identity_asset_id", "scale_asset_id", "depict_worker", "version"}):
            raise ValueError("Contrat de référence d’ouvrier invalide.")
        return cls(**value)
