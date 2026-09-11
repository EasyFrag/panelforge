"""Purfview CLI adapter. No model imports or processes until explicitly called."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import wave

from panelforge.application.media_transcription import TranscriptionCancelled
from panelforge.domain.media_analysis import MediaTranscript, TranscriptSegment, SPEECH_MODEL, SPEECH_ENGINE


class PurfviewTranscriber:
    def __init__(self, *, executable, ffmpeg, model_directory, timeout_seconds=900):
        self.executable = Path(executable).resolve()
        self.ffmpeg = Path(ffmpeg).resolve()
        self.model_directory = Path(model_directory).resolve()
        self.timeout_seconds = timeout_seconds

    def availability(self):
        required = (self.executable, self.ffmpeg, self.model_directory / f"faster-whisper-{SPEECH_MODEL}" / "model.bin")
        available = all(path.is_file() for path in required)
        return dict(available=available, engine=SPEECH_ENGINE, model=SPEECH_MODEL,
            message="Faster Whisper XXL · large-v3-turbo · local" if available else
                "Transcription locale indisponible : configurez Faster Whisper XXL, ffmpeg et le modèle large-v3-turbo (PANELFORGE_WHISPER_ROOT).")

    def transcribe(self, source, request, cancelled, progress):
        status = self.availability()
        if not status["available"]:
            raise ValueError(status["message"])
        with tempfile.TemporaryDirectory(prefix="panelforge-speech-") as directory:
            root = Path(directory)
            audio = root / "excerpt.wav"
            progress("extracting", "Extraction du son de l’extrait…")
            self._run([str(self.ffmpeg), "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                "-ss", f"{request.clip_start_seconds:.6f}", "-i", str(source),
                "-t", f"{request.duration_seconds:.6f}", "-map", "0:a:0", "-vn", "-ac", "1", "-ar", "16000",
                "-c:a", "pcm_s16le", str(audio)], root, cancelled, "Extraction audio", timeout=120)
            try:
                with wave.open(str(audio), "rb") as wav:
                    if wav.getnframes() == 0:
                        raise ValueError("Aucun son disponible dans cet extrait.")
            except (OSError, wave.Error) as error:
                raise ValueError("Impossible de lire la piste audio de cet extrait.") from error
            progress("transcribing", "Transcription locale en cours… Vous pouvez utiliser les autres ateliers.")
            command = [str(self.executable), str(audio), "--model", SPEECH_MODEL,
                "--model_dir", str(self.model_directory), "--device", request.device,
                "--compute_type", "int8" if request.device == "cpu" else "auto",
                "--task", "transcribe", "--output_dir", str(root), "--output_format", "json",
                "--beep_off"]
            if request.language != "auto":
                command += ["--language", request.language]
            self._run(command, root, cancelled, "Faster Whisper", timeout=self.timeout_seconds)
            if cancelled.is_set():
                raise TranscriptionCancelled()
            output = root / "excerpt.json"
            if not output.is_file() or output.stat().st_size > 2 * 1024 * 1024:
                raise ValueError("Faster Whisper n’a pas produit de transcription JSON exploitable.")
            try:
                value = json.loads(output.read_text(encoding="utf-8-sig"))
                return parse_transcript(value, request)
            except (TypeError, KeyError, ValueError) as error:
                raise ValueError(f"Transcription illisible : {error}") from error

    def _run(self, command, directory, cancelled, label, *, timeout):
        if cancelled.is_set():
            raise TranscriptionCancelled()
        # File-backed output prevents pipe deadlocks; stderr is never injected into prompts.
        with tempfile.TemporaryFile() as output:
            process = subprocess.Popen(command, cwd=str(self.executable.parent), stdin=subprocess.DEVNULL,
                stdout=output, stderr=subprocess.STDOUT, shell=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                env={**os.environ, "HF_HUB_OFFLINE": "1", "HF_HUB_DISABLE_TELEMETRY": "1"})
            try:
                deadline = time.monotonic() + timeout
                while process.poll() is None:
                    if cancelled.wait(.2):
                        raise TranscriptionCancelled()
                    if time.monotonic() > deadline:
                        raise ValueError(f"{label} a dépassé le délai de {timeout} secondes. Vous pouvez réessayer.")
                if cancelled.is_set():
                    raise TranscriptionCancelled()
                if process.returncode:
                    output.seek(0, 2)
                    output.seek(max(0, output.tell() - 4000))
                    detail = output.read().decode("utf-8", errors="replace").strip()
                    if "matches no streams" in detail or "does not contain any stream" in detail:
                        raise ValueError("Cette vidéo ne contient pas de piste audio. Vous pouvez continuer avec les images seules.")
                    if any(word in detail.lower() for word in ("out of memory", "cuda failed", "cublas", "cudnn")):
                        raise ValueError("Faster Whisper n’a pas pu utiliser le GPU. Réessayez en mode CPU ; les autres services restent ouverts.")
                    raise ValueError(f"{label} a échoué (code {process.returncode}). {detail[-1200:]}")
            finally:
                # Only the process started here is stopped, never Unsloth or ComfyUI.
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=3)


def parse_transcript(value, request):
    if not isinstance(value, dict) or not isinstance(value.get("segments"), list) or len(value["segments"]) > 500:
        raise ValueError("Segments JSON absents ou invalides.")
    segments = []
    for raw in value["segments"]:
        if not isinstance(raw, dict) or not isinstance(raw.get("text"), str):
            raise ValueError("Réplique JSON invalide.")
        if not raw["text"].strip():
            continue
        start, end = raw["start"], raw["end"]
        # Whisper can round the last boundary slightly beyond the WAV duration.
        for time_value in (start, end):
            if isinstance(time_value, bool) or not isinstance(time_value, (int, float)) or not 0 <= time_value <= request.duration_seconds + .1:
                raise ValueError("Repère de parole hors de l’extrait.")
        segments.append(TranscriptSegment(min(start, request.duration_seconds), min(end, request.duration_seconds), raw["text"].strip()))
    text = "\n".join(f"[{s.start_seconds:.2f} → {s.end_seconds:.2f} s] {s.text}" for s in segments)
    return MediaTranscript(text=text, original_text=text, segments=tuple(segments),
        clip_start_seconds=request.clip_start_seconds, clip_end_seconds=request.clip_end_seconds,
        language=request.language, detected_language=value.get("language"), device=request.device)
