"""Read video outputs using the binding declared by a workflow manifest."""

from collections.abc import Mapping
from typing import Any


def extract_bound_video(
    history_run: Mapping[str, Any],
    *,
    node_id: str,
    history_field: str,
) -> dict[str, str]:
    """Read the exact SaveVideo result declared by the recipe manifest."""
    outputs = history_run.get("outputs")
    if not isinstance(outputs, Mapping):
        raise ValueError("ComfyUI history has no outputs object")
    node_output = outputs.get(node_id)
    if not isinstance(node_output, Mapping):
        raise ValueError(f"ComfyUI history has no output for node {node_id!r}")
    videos = node_output.get(history_field)
    if not isinstance(videos, list) or not videos:
        raise ValueError(
            f"ComfyUI node {node_id!r} has no {history_field!r} output"
        )
    video = videos[0]
    if not isinstance(video, Mapping):
        raise ValueError("ComfyUI video output must be an object")
    filename = video.get("filename")
    subfolder = video.get("subfolder", "")
    folder_type = video.get("type", "output")
    if not isinstance(filename, str) or not filename:
        raise ValueError("ComfyUI video output has no filename")
    if not isinstance(subfolder, str) or not isinstance(folder_type, str):
        raise ValueError("ComfyUI video output has invalid location fields")
    return {
        "filename": filename,
        "subfolder": subfolder,
        "type": folder_type,
    }
