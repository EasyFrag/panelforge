"""Shared, vendor-free contracts for derived image/video results."""

from dataclasses import dataclass
import math
import re


@dataclass(frozen=True, slots=True)
class DlssSettings:
    size: str = "2"
    intensity: float = 1.0
    tone: float = 1.0
    structure: float = 1.0
    skin: float = 1.0
    style: str = "Default"
    detail: float = 1.0
    strict_neural: bool = False
    interpolate: bool = False
    hdr: bool = False
    codec: str = "H.264 (NVIDIA NVENC)"

    def __post_init__(self):
        if self.size not in {"source", "1", "1.5", "1.724", "2", "3"}:
            raise ValueError("Taille DLSS invalide.")
        for name, low, high in (("intensity", 0, 2), ("tone", 0, 2), ("structure", 0, 2),
                                ("skin", -1, 2), ("detail", 1, 2)):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
                raise ValueError(f"Réglage DLSS invalide : {name}.")
        if self.style not in {"Default", "Natural", "Cinematic"}:
            raise ValueError("Style DLSS invalide.")
        if self.codec not in {"H.264", "H.264 (NVIDIA NVENC)", "H.265 (NVIDIA NVENC)"}:
            raise ValueError("Codec DLSS invalide.")
        if any(type(getattr(self, name)) is not bool for name in ("strict_neural", "interpolate", "hdr")):
            raise ValueError("Option DLSS invalide.")
        if self.hdr and self.codec != "H.265 (NVIDIA NVENC)":
            raise ValueError("Le HDR nécessite H.265.")

    @property
    def factor(self):
        return 2.0 if self.size == "source" else float(self.size)


@dataclass(frozen=True, slots=True)
class DlssResult:
    job_id: str
    parent_attempt_id: str
    root_attempt_id: str
    input_asset_id: str
    report_asset_id: str
    width: int
    height: int
    size: str
    fps: float | None = None
    duration_seconds: float | None = None

    def __post_init__(self):
        for name in ("job_id", "parent_attempt_id", "root_attempt_id", "input_asset_id", "report_asset_id"):
            if not isinstance(getattr(self, name), str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", getattr(self, name)):
                raise ValueError(f"Identifiant DLSS invalide : {name}.")
        if any(type(v) is not int or v < 1 for v in (self.width, self.height)):
            raise ValueError("Dimensions DLSS invalides.")
        if self.size not in {"source", "1", "1.5", "1.724", "2", "3"}:
            raise ValueError("Taille DLSS invalide.")
        for v in (self.fps, self.duration_seconds):
            if v is not None and (isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0):
                raise ValueError("Cadence ou durée DLSS invalide.")


def validate_dlss_attempt(attempt):
    info = attempt.dlss
    if not isinstance(info, DlssResult) or attempt.status.value != "succeeded" or not attempt.output_asset_id:
        raise ValueError("Une variante DLSS doit être un résultat réussi et traçable.")
    if any(getattr(attempt, name, None) is not None for name in ("execution_id", "compiled_workflow_sha256", "queue_order", "error")):
        raise ValueError("L’exécution locale DLSS appartient à sa tâche, pas à la file de génération.")


def validate_dlss_lineage(attempts):
    previous = {}
    jobs = set()
    for attempt in attempts:
        info = attempt.dlss
        if info:
            parent, root = previous.get(info.parent_attempt_id), previous.get(info.root_attempt_id)
            if parent is None or root is None or parent.status.value != "succeeded" or root.status.value != "succeeded":
                raise ValueError("Origine de variante DLSS absente.")
            if info.root_attempt_id != (parent.dlss.root_attempt_id if parent.dlss else parent.attempt_id):
                raise ValueError("Origine de variante DLSS incohérente.")
            if attempt.prompt != parent.prompt or attempt.settings != parent.settings or getattr(attempt, "index", None) != getattr(parent, "index", None):
                raise ValueError("Les réglages de génération d’une variante doivent rester ceux de son parent.")
            if not getattr(attempt, "upscale", None) and info.input_asset_id != parent.output_asset_id:
                raise ValueError("Une variante DLSS doit traiter le média de son parent.")
            if info.job_id in jobs:
                raise ValueError("Tâche DLSS déjà importée.")
            jobs.add(info.job_id)
        previous[attempt.attempt_id] = attempt
