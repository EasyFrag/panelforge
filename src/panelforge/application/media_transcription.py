"""An optional, short-lived speech engine, independent of all generation queues."""
from threading import Lock


class TranscriptionBusy(ValueError):
    pass


class TranscriptionCancelled(Exception):
    pass


class MediaTranscriptionService:
    def __init__(self, engine):
        self.engine = engine
        self._lock = Lock()

    def availability(self):
        return self.engine.availability()

    def transcribe(self, source, request, cancelled, progress):
        if not self._lock.acquire(blocking=False):
            raise TranscriptionBusy("Une transcription locale est déjà en cours. Réessayez après sa fin.")
        try:
            if cancelled.is_set():
                raise TranscriptionCancelled()
            return self.engine.transcribe(source, request, cancelled, progress)
        finally:
            self._lock.release()
