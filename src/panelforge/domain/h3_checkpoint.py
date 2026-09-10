"""Saved video-model selection; independent of the prompt preparation family."""
from dataclasses import dataclass


def validate_h3_checkpoint(value: str | None) -> None:
    if value is None:
        return
    if (not isinstance(value, str) or not value or len(value) > 512
            or value != value.strip() or "\\" in value or ":" in value
            or any(part in {"", ".", ".."} for part in value.split("/"))
            or any(ord(char) < 32 for char in value)
            or not value.endswith(".safetensors")):
        raise ValueError("Identifiant de checkpoint vidéo invalide.")


@dataclass(frozen=True, slots=True)
class H3ModelLoading:
    checkpoint: str
    strategy: str = "direct"
    overlay: str | None = None

    def __post_init__(self) -> None:
        validate_h3_checkpoint(self.checkpoint)
        if self.checkpoint is None:
            raise ValueError("Un modèle effectif est requis.")
        validate_h3_checkpoint(self.overlay)
        if self.strategy not in {"direct", "hybrid"}:
            raise ValueError("Chargement vidéo inconnu.")
        if (self.strategy == "hybrid") != (self.overlay is not None):
            raise ValueError("Chargement vidéo et modèle overlay incohérents.")


def validate_h3_model_selection(checkpoint: str | None, loading: H3ModelLoading | None) -> None:
    validate_h3_checkpoint(checkpoint)
    if loading is not None and not isinstance(loading, H3ModelLoading):
        raise TypeError("model_loading must be H3ModelLoading or None")
    if checkpoint is not None and loading != H3ModelLoading(checkpoint):
        raise ValueError("Le checkpoint choisi doit être chargé directement.")
