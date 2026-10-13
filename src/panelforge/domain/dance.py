"""Immutable motion-reference contract; image and performance have separate roles."""
from dataclasses import dataclass
import math


@dataclass(frozen=True, slots=True)
class DanceReference:
    source_asset_id: str
    clip_asset_id: str
    label: str
    start_seconds: float
    duration_seconds: float
    frame_count: int
    has_audio: bool
    keep_audio: bool = True
    version: str = '1.0.0'

    def __post_init__(self):
        for text in (self.source_asset_id, self.clip_asset_id, self.label):
            if not isinstance(text, str) or not text.strip() or len(text) > 240:
                raise ValueError('Référence de danse incomplète.')
        if self.version != '1.0.0' or type(self.has_audio) is not bool or type(self.keep_audio) is not bool:
            raise ValueError('Contrat de danse invalide.')
        if (isinstance(self.start_seconds, bool) or not isinstance(self.start_seconds, (int, float)) or not math.isfinite(self.start_seconds)
                or self.start_seconds < 0):
            raise ValueError('Début d’extrait invalide.')
        if (type(self.frame_count) is not int or not 124 <= self.frame_count <= 345
                or self.frame_count % 17 != 5):
            raise ValueError('L’extrait doit suivre la grille H3 entre 5 et 15 secondes.')
        if (isinstance(self.duration_seconds, bool) or not isinstance(self.duration_seconds, (int, float))
                or not math.isclose(self.duration_seconds, self.frame_count / 24, rel_tol=0, abs_tol=1e-8)):
            raise ValueError('La durée ne correspond pas aux images de l’extrait.')


def excerpt_frames(start, requested_duration, source_duration):
    for value in (start, requested_duration, source_duration):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError('Repères d’extrait invalides.')
    if start < 0 or not 5 <= requested_duration <= 15 or start + requested_duration > source_duration + .05:
        raise ValueError('Choisissez un extrait de 5 à 15 secondes dans la vidéo.')
    available = math.floor(min(requested_duration, source_duration - start) * 24 + 1e-6)
    frames = 5 + 17 * ((available - 5) // 17)
    if frames < 124:
        raise ValueError('Choisissez au moins 5,2 secondes pour la grille du moteur H3.')
    return min(frames, 345)


def validate_dance_attempt(stage, source_attempt_id, latent_asset_ids):
    if stage not in ('full', 'draft', 'refine'):
        raise ValueError('Étape de danse inconnue.')
    if (stage == 'refine') != (source_attempt_id is not None):
        raise ValueError('La finition doit désigner son brouillon.')
    if source_attempt_id is not None and (not isinstance(source_attempt_id, str) or not source_attempt_id.strip()):
        raise ValueError('Identifiant du brouillon invalide.')
    if not isinstance(latent_asset_ids, tuple) or len(latent_asset_ids) not in (0, 2):
        raise ValueError('Les latents vidéo et audio doivent être conservés ensemble.')
    if latent_asset_ids and (stage != 'draft' or any(not isinstance(x, str) or not x for x in latent_asset_ids)):
        raise ValueError('Latents de brouillon invalides.')
