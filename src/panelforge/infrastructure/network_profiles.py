"""Explicit startup profiles; legacy settings remain opt-in and unchanged.

No DNS lookup, drive remount, credentials access or filesystem probing here.
"""
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import Mapping
from urllib.parse import urlsplit, urlunsplit


DEFAULT_COMFY_URL = "http://192.168.1.72:8188"
DEFAULT_LLM_URL = "http://bucket:8083/v1"
DEFAULT_MODELS_ROOT = r"\\sshfs.r\malmo@bucket\data\models\ComfyUi\diffusion_models\Krea2"
DEFAULT_LORAS_ROOT = r"\\sshfs.r\malmo@bucket\data\models\ComfyUi\loras\krea2"
DEFAULT_EXPORT_ROOT = r"X:\data\ComfyUI\output\video\Upscale"
NETWORK_LABELS = {"lan": "Local", "tailscale": "Tailscale"}


@dataclass(frozen=True)
class NetworkConfiguration:
    mode: str | None
    base_url: str
    llm_base_url: str
    models_root: Path
    loras_root: Path
    export_root: Path
    export_access_root: Path | None = None


def resolve_network_configuration(
    mode=None, *, base_url=None, llm_base_url=None, models_root=None,
    loras_root=None, export_root=None, environ: Mapping[str, str],
):
    """Explicit profiles override inherited network defaults, never explicit conflicts."""
    if mode is None:
        return NetworkConfiguration(
            None,
            base_url if base_url is not None else environ.get("PANELFORGE_COMFY_URL", DEFAULT_COMFY_URL),
            llm_base_url if llm_base_url is not None else environ.get("PANELFORGE_LLM_URL", DEFAULT_LLM_URL),
            Path(models_root if models_root is not None else environ.get("PANELFORGE_KREA2_MODELS_ROOT", DEFAULT_MODELS_ROOT)),
            Path(loras_root if loras_root is not None else environ.get("PANELFORGE_KREA2_LORAS_ROOT", DEFAULT_LORAS_ROOT)),
            Path(export_root if export_root is not None else DEFAULT_EXPORT_ROOT),
        )
    if mode not in NETWORK_LABELS:
        raise ValueError("Mode réseau inconnu : choisir lan ou tailscale.")
    host = "192.168.1.72" if mode == "lan" else "bucket"
    share = PureWindowsPath("\\\\sshfs.r\\malmo@" + host)
    expected = NetworkConfiguration(
        mode, f"http://{host}:8188", f"http://{host}:8083/v1",
        Path(str(share / r"data\models\ComfyUi\diffusion_models\Krea2")),
        Path(str(share / r"data\models\ComfyUi\loras\krea2")),
        Path(DEFAULT_EXPORT_ROOT),
        Path(str(share / r"data\ComfyUI\output\video\Upscale")),
    )
    for option, given, selected in (
        ("--base-url", base_url, expected.base_url),
        ("--llm-base-url", llm_base_url, expected.llm_base_url),
    ):
        if given is not None and _url_identity(given) != _url_identity(selected):
            raise ValueError(f"{option} contredit --network-mode {mode}. "
                             "Retire cette option pour utiliser le profil, ou retire --network-mode.")
    for option, given, selected in (
        ("--krea2-models-root", models_root, expected.models_root),
        ("--krea2-loras-root", loras_root, expected.loras_root),
        ("--dlss-video-export-root", export_root, expected.export_root),
    ):
        if given is not None and PureWindowsPath(given) != PureWindowsPath(selected):
            raise ValueError(f"{option} contredit --network-mode {mode}. "
                             "Le profil utilise les dossiers serveur prévus et conserve le chemin logique X:. "
                             "Retire cette option, ou utilise le lancement historique sans --network-mode.")
    return expected


def _url_identity(value):
    try:
        url = urlsplit(value)
        # A profile must not accept hidden alternate targets, credentials or queries.
        if url.username is not None or url.password is not None or url.query or url.fragment:
            return None
        return url.scheme.lower(), url.hostname, url.port, url.path.rstrip("/")
    except (TypeError, ValueError):
        return None


def safe_endpoint(value):
    """Console diagnostic without URL credentials, queries or fragments."""
    try:
        url = urlsplit(value)
        host = url.hostname or ""
        if ":" in host:
            host = f"[{host}]"
        return urlunsplit((url.scheme, host + (f":{url.port}" if url.port else ""), url.path, "", ""))
    except (TypeError, ValueError):
        return "(adresse personnalisée)"


def describe_network(args):
    mode = getattr(args, "network_mode", None)
    heading = NETWORK_LABELS.get(mode, "configuration historique ; montages conservés")
    lines = [
        f"Réseau : {heading}",
        f"  ComfyUI : {safe_endpoint(args.base_url)}",
        f"  LLM serveur : {safe_endpoint(args.llm_base_url)}",
        f"  Modèles : {args.krea2_models_root}",
        f"  LoRA : {args.krea2_loras_root}",
        f"  Export : {getattr(args, 'dlss_video_export_access_root', None) or args.dlss_video_export_root}",
    ]
    if mode is None:
        lines.append("  Aucun profil complet déclaré : les URL et les montages peuvent utiliser des accès différents.")
    return "\n".join(lines)
