"""Visual evidence for a French video intention, independent of render recipes."""
from dataclasses import dataclass
import math

MAX_FRAMES = 16
MAX_CLIP_SECONDS = 60
MIN_TARGET_SECONDS = 5
MAX_TARGET_SECONDS = 15
ANALYSIS_VERSION = "1.0.1"
SPEECH_ANALYSIS_VERSION = "1.1.1"
SPEECH_MODEL = "large-v3-turbo"
SPEECH_ENGINE = "purfview-faster-whisper-xxl"
SPEECH_LANGUAGES = ("en", "fr", "auto", "es", "de", "it", "pt", "ja", "zh")


def number(value, label, minimum=0, maximum=86_400):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError(f"{label} doit être un nombre entre {minimum} et {maximum}.")


@dataclass(frozen=True)
class AnalysisFrame:
    asset_id: str
    label: str
    time_seconds: float | None = None

    def __post_init__(self):
        if not isinstance(self.asset_id, str) or not self.asset_id or len(self.asset_id) > 128:
            raise ValueError("Identifiant d’image invalide.")
        if not isinstance(self.label, str) or not self.label.strip() or len(self.label) > 240:
            raise ValueError("Nom d’image invalide.")
        if self.time_seconds is not None:
            number(self.time_seconds, "Le temps de l’image")


@dataclass(frozen=True)
class SpeechInput:
    clip_start_seconds: float
    clip_end_seconds: float
    language: str = "en"
    device: str = "cpu"

    def __post_init__(self):
        number(self.clip_start_seconds, "Le début de l’extrait audio")
        number(self.clip_end_seconds, "La fin de l’extrait audio")
        if not .1 <= self.duration_seconds <= MAX_CLIP_SECONDS:
            raise ValueError("Choisissez un extrait audio de 0,1 à 60 secondes.")
        if self.language not in SPEECH_LANGUAGES or self.device not in ("cuda", "cpu"):
            raise ValueError("Langue ou processeur de transcription invalide.")

    @property
    def duration_seconds(self):
        return self.clip_end_seconds - self.clip_start_seconds


@dataclass(frozen=True)
class TranscriptSegment:
    start_seconds: float
    end_seconds: float
    text: str

    def __post_init__(self):
        number(self.start_seconds, "Le début de la réplique", maximum=MAX_CLIP_SECONDS)
        number(self.end_seconds, "La fin de la réplique", maximum=MAX_CLIP_SECONDS)
        if self.end_seconds < self.start_seconds or not isinstance(self.text, str) or not self.text.strip() or len(self.text) > 4000:
            raise ValueError("Réplique transcrite invalide.")


@dataclass(frozen=True)
class MediaTranscript:
    text: str
    original_text: str
    segments: tuple[TranscriptSegment, ...]
    clip_start_seconds: float
    clip_end_seconds: float
    language: str = "en"
    detected_language: str | None = None
    device: str = "cpu"
    keep_dialogue: bool = False
    engine: str = SPEECH_ENGINE
    model: str = SPEECH_MODEL

    def __post_init__(self):
        source = SpeechInput(self.clip_start_seconds, self.clip_end_seconds, self.language, self.device)
        if any(not isinstance(t, str) or len(t) > 12_000 for t in (self.text, self.original_text)):
            raise ValueError("La transcription est limitée à 12 000 caractères.")
        if type(self.keep_dialogue) is not bool or self.engine != SPEECH_ENGINE or self.model != SPEECH_MODEL:
            raise ValueError("Options de transcription invalides.")
        if self.detected_language is not None and (not isinstance(self.detected_language, str) or len(self.detected_language) > 64):
            raise ValueError("Langue détectée invalide.")
        if not isinstance(self.segments, tuple) or len(self.segments) > 500 or any(not isinstance(s, TranscriptSegment) for s in self.segments):
            raise ValueError("Segments de transcription invalides.")
        if any(s.end_seconds > source.duration_seconds + .001 for s in self.segments) or any(b.start_seconds < a.start_seconds for a, b in zip(self.segments, self.segments[1:])):
            raise ValueError("Les paroles doivent être horodatées dans l’extrait sélectionné, à partir de zéro.")

    @classmethod
    def from_dict(cls, value):
        try:
            data = dict(value)
            data["segments"] = tuple(TranscriptSegment(**segment) for segment in data["segments"])
            return cls(**data)
        except (KeyError, TypeError) as error:
            raise ValueError("Transcription incomplète ou invalide.") from error


@dataclass(frozen=True)
class MediaAnalysisInput:
    frames: tuple[AnalysisFrame, ...]
    model_id: str
    instruction: str = ""
    source_kind: str = "images"
    source_name: str = "Images"
    duration_seconds: float = 8
    clip_start_seconds: float | None = None
    clip_end_seconds: float | None = None
    source_duration_seconds: float | None = None
    transcript: MediaTranscript | None = None

    def __post_init__(self):
        if not isinstance(self.frames, tuple) or not 1 <= len(self.frames) <= MAX_FRAMES or any(not isinstance(f, AnalysisFrame) for f in self.frames):
            raise ValueError(f"Choisissez entre 1 et {MAX_FRAMES} images.")
        for value, label, limit, empty in ((self.model_id, "Modèle", 300, False), (self.instruction, "Consigne", 12_000, True), (self.source_name, "Nom du média", 240, False)):
            if not isinstance(value, str) or len(value) > limit or (not empty and not value.strip()):
                raise ValueError(f"{label} invalide.")
        number(self.duration_seconds, "La durée cible H3/REF2V", MIN_TARGET_SECONDS, MAX_TARGET_SECONDS)
        known = [frame.time_seconds for frame in self.frames if frame.time_seconds is not None]
        if any(b <= a for a, b in zip(known, known[1:])):
            raise ValueError("Les temps renseignés doivent augmenter dans l’ordre des images. Corrigez ou effacez un repère.")
        if self.source_kind == "video":
            number(self.clip_start_seconds, "Le début de l’extrait")
            number(self.clip_end_seconds, "La fin de l’extrait")
            number(self.source_duration_seconds, "La durée de la vidéo", .1)
            length = self.clip_end_seconds - self.clip_start_seconds
            if not .1 <= length <= MAX_CLIP_SECONDS or self.clip_end_seconds > self.source_duration_seconds:
                raise ValueError(f"Choisissez un extrait de 0,1 à {MAX_CLIP_SECONDS} secondes dans la vidéo.")
            if len(known) != len(self.frames) or any(t > length + .001 for t in known):
                raise ValueError("Les captures doivent être horodatées dans l’extrait, à partir de zéro.")
        elif self.source_kind == "images":
            if any(v is not None for v in (self.clip_start_seconds, self.clip_end_seconds, self.source_duration_seconds)):
                raise ValueError("Une série d’images ne possède pas d’extrait vidéo.")
            if known and known[-1] > self.duration_seconds:
                raise ValueError("La durée cible doit inclure le dernier repère temporel.")
        else:
            raise ValueError("Source attendue : images ou vidéo.")
        if self.transcript is not None:
            if not isinstance(self.transcript, MediaTranscript) or self.source_kind != "video":
                raise ValueError("La transcription doit correspondre à une vidéo.")
            if (self.transcript.clip_start_seconds, self.transcript.clip_end_seconds) != (self.clip_start_seconds, self.clip_end_seconds):
                raise ValueError("L’extrait a changé. Actualisez la transcription ou désactivez les paroles.")

    @classmethod
    def from_dict(cls, value):
        data = dict(value)
        data["frames"] = tuple(AnalysisFrame(**frame) for frame in data["frames"])
        if data.get("transcript") is not None:
            data["transcript"] = MediaTranscript.from_dict(data["transcript"])
        return cls(**data)
