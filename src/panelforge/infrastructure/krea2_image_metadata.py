"""Bounded, data-only metadata recovery for KREA2 PNG sources."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
import json
import struct
import zlib

from panelforge.domain.krea2_batch import Krea2LoraSelection
from panelforge.domain.krea2_edit import Krea2EditMetadata
from panelforge.domain.krea2_lab import Krea2AspectRatio
from panelforge.domain.firered_edit import FireRedEditSettings


_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_MAX_CHUNK = 8 * 1024 * 1024
_MAX_TEXT = 16 * 1024 * 1024


def recover_krea2_metadata(
    image: bytes,
    *,
    sidecar: bytes | None = None,
) -> Krea2EditMetadata:
    """Recover known KREA2 fields without evaluating embedded workflow data."""
    warnings: list[str] = []
    if sidecar is not None:
        try:
            payload = json.loads(sidecar.decode("utf-8-sig"))
            return _from_sidecar(payload)
        except (UnicodeError, json.JSONDecodeError, TypeError, ValueError) as error:
            warnings.append(f"Sidecar ignoré : {error}")

    try:
        texts = png_text_chunks(image)
    except ValueError as error:
        return Krea2EditMetadata(origin="none", warnings=(*warnings, str(error)))
    prompt_raw = texts.get("prompt")
    if not prompt_raw:
        return Krea2EditMetadata(
            origin="none",
            warnings=(*warnings, "Aucune métadonnée de prompt KREA2 trouvée."),
        )
    try:
        graph = json.loads(prompt_raw)
        metadata = _from_comfy_graph(graph)
    except (json.JSONDecodeError, TypeError, ValueError) as error:
        return Krea2EditMetadata(
            origin="none",
            warnings=(*warnings, f"Métadonnées ComfyUI illisibles : {error}"),
        )
    return replace(metadata, warnings=(*warnings, *metadata.warnings))


def png_text_chunks(content: bytes) -> dict[str, str]:
    if not isinstance(content, bytes) or not content.startswith(_PNG_SIGNATURE):
        raise ValueError("L’image source n’est pas un PNG valide.")
    offset = len(_PNG_SIGNATURE)
    total = 0
    result: dict[str, str] = {}
    while offset + 12 <= len(content):
        length = struct.unpack(">I", content[offset : offset + 4])[0]
        chunk_type = content[offset + 4 : offset + 8]
        offset += 8
        if length > _MAX_CHUNK or offset + length + 4 > len(content):
            raise ValueError("Les métadonnées PNG dépassent la limite autorisée.")
        data = content[offset : offset + length]
        offset += length + 4  # data + CRC; CRC is not trusted as metadata.
        if chunk_type == b"IEND":
            break
        parsed = _decode_text_chunk(chunk_type, data)
        if parsed is None:
            continue
        key, value = parsed
        total += len(value.encode("utf-8", errors="replace"))
        if total > _MAX_TEXT:
            raise ValueError("Les textes PNG dépassent la limite autorisée.")
        result.setdefault(key, value)
    return result


def _decode_text_chunk(kind: bytes, data: bytes) -> tuple[str, str] | None:
    try:
        if kind == b"tEXt":
            key, value = data.split(b"\0", 1)
            return key.decode("latin-1"), value.decode("latin-1")
        if kind == b"zTXt":
            key, remainder = data.split(b"\0", 1)
            if not remainder or remainder[0] != 0:
                return None
            value = _bounded_decompress(remainder[1:])
            return key.decode("latin-1"), value.decode("latin-1")
        if kind == b"iTXt":
            key, remainder = data.split(b"\0", 1)
            compressed, method = remainder[0], remainder[1]
            remainder = remainder[2:]
            _, remainder = remainder.split(b"\0", 1)  # language
            _, value = remainder.split(b"\0", 1)  # translated keyword
            if compressed:
                if method != 0:
                    return None
                value = _bounded_decompress(value)
            return key.decode("latin-1"), value.decode("utf-8")
    except (IndexError, ValueError, UnicodeError, zlib.error):
        return None
    return None


def _bounded_decompress(value: bytes) -> bytes:
    stream = zlib.decompressobj()
    result = stream.decompress(value, _MAX_CHUNK + 1)
    result += stream.flush(_MAX_CHUNK + 1 - len(result))
    if len(result) > _MAX_CHUNK or stream.unconsumed_tail:
        raise ValueError("compressed PNG text is too large")
    return result


def _from_sidecar(value: object) -> Krea2EditMetadata:
    payload = _mapping(value, "sidecar")
    render = _mapping(payload.get("render"), "sidecar.render")
    if render.get("engine") == "firered":
        settings = FireRedEditSettings(model_name=render.get("model_name"),
            megapixels=render.get("megapixels"), seed=_optional_seed(render.get("seed")),
            mode=render.get("mode"), steps=render.get("steps"), cfg=render.get("cfg"))
        return Krea2EditMetadata(prompt=_optional_text(payload.get("prompt")),
            model_name=settings.model_name, megapixels=settings.megapixels, seed=settings.seed,
            steps=settings.steps, firered_settings=settings, origin="sidecar")
    return Krea2EditMetadata(
        prompt=_optional_text(payload.get("prompt")),
        model_name=_optional_text(render.get("model_name")),
        aspect_ratio=_optional_ratio(render.get("aspect_ratio")),
        megapixels=_optional_number(render.get("megapixels")),
        seed=_optional_seed(render.get("seed")),
        loras=_loras_from_list(render.get("loras")),
        origin="sidecar",
    )


def _from_comfy_graph(value: object) -> Krea2EditMetadata:
    graph = _mapping(value, "ComfyUI prompt")
    fire = _firered_metadata(graph)
    if fire is not None:
        return fire
    prompts: list[str] = []
    model: str | None = None
    ratio: Krea2AspectRatio | None = None
    megapixels: float | None = None
    seed: int | None = None
    loras: list[Krea2LoraSelection] = []
    for raw in graph.values():
        if not isinstance(raw, Mapping):
            continue
        class_type = str(raw.get("class_type", ""))
        inputs = raw.get("inputs")
        if not isinstance(inputs, Mapping):
            continue
        if class_type in {"CLIPTextEncode", "Krea2EditGroundedEncode"}:
            prompt = inputs.get("text", inputs.get("prompt"))
            if isinstance(prompt, str) and prompt.strip():
                prompts.append(prompt.strip())
        elif class_type == "UNETLoader":
            model = _optional_text(inputs.get("unet_name")) or model
        elif class_type == "ResolutionSelector":
            ratio = _optional_ratio(inputs.get("aspect_ratio")) or ratio
            megapixels = _optional_number(inputs.get("megapixels")) or megapixels
        elif class_type == "KSampler":
            seed = _optional_seed(inputs.get("seed")) if seed is None else seed
        if "Seed" in class_type and seed is None:
            seed = _first_seed(inputs)
        if "Power Lora Loader" in class_type:
            loras.extend(_loras_from_power_loader(inputs))
        elif "Lora Loader Stack" in class_type:
            loras.extend(_loras_from_lora_stack(inputs))
    prompt = max(prompts, key=len) if prompts else None
    filtered: list[Krea2LoraSelection] = []
    seen: set[str] = set()
    for lora in loras:
        normalized = lora.name.replace("\\", "/").casefold()
        if "identity_edit" in normalized or normalized in seen:
            continue
        seen.add(normalized)
        filtered.append(lora)
        if len(filtered) == 4:
            break
    warnings: list[str] = []
    if prompt is None:
        warnings.append("Le workflow ne contient aucun prompt exploitable.")
    if model is None:
        warnings.append("Le modèle KREA2 n’est pas indiqué dans l’image.")
    return Krea2EditMetadata(
        prompt=prompt,
        model_name=model,
        aspect_ratio=ratio,
        megapixels=megapixels,
        seed=seed,
        loras=tuple(filtered),
        origin="png",
        warnings=tuple(warnings),
    )


def _firered_metadata(graph: Mapping) -> Krea2EditMetadata | None:
    """Read the known import's primitives/switches only; never evaluate nodes."""
    nodes = [n for n in graph.values() if isinstance(n, Mapping) and isinstance(n.get("inputs"), Mapping)]
    models = [n["inputs"].get("unet_name") for n in nodes if n.get("class_type") == "UNETLoader"]
    model = next((v for v in models if isinstance(v, str) and "firered-image-edit" in v.casefold()), None)
    if model is None:
        return None

    def linked(value):
        if not isinstance(value, list) or len(value) != 2 or value[1] != 0 or not isinstance(value[0], str):
            raise ValueError("unsupported FireRed metadata link")
        node = graph.get(value[0])
        if not isinstance(node, Mapping) or not isinstance(node.get("inputs"), Mapping):
            raise ValueError("missing FireRed metadata node")
        return node

    def scalar(value, depth=0):
        if depth > 12:
            raise ValueError("FireRed metadata links are too deep")
        if not isinstance(value, list):
            return value
        node = linked(value)
        inputs = node["inputs"]
        if node.get("class_type") in {"PrimitiveInt", "PrimitiveFloat", "PrimitiveBoolean"}:
            return scalar(inputs.get("value"), depth + 1)
        if node.get("class_type") == "ComfySwitchNode":
            enabled = scalar(inputs.get("switch"), depth + 1)
            if type(enabled) is not bool:
                raise ValueError("invalid FireRed metadata switch")
            return scalar(inputs.get("on_true" if enabled else "on_false"), depth + 1)
        raise ValueError("unsupported FireRed metadata scalar")

    try:
        sampler = next(n["inputs"] for n in nodes if n.get("class_type") == "KSampler")
        resize = next(n["inputs"] for n in nodes if n.get("class_type") == "ResizeImageMaskNode")
        switches = [n for n in nodes if n.get("class_type") == "ComfySwitchNode"
                    and linked(n["inputs"].get("on_true")).get("class_type") == "LoraLoaderModelOnly"]
        if len(switches) != 1:
            raise ValueError("ambiguous FireRed model branch")
        lightning = scalar(switches[0]["inputs"].get("switch"))
        if type(lightning) is not bool:
            raise ValueError("invalid FireRed model branch")
        positive = linked(sampler.get("positive"))
        if positive.get("class_type") != "TextEncodeQwenImageEditPlus":
            raise ValueError("unsupported FireRed positive conditioning")
        settings = FireRedEditSettings(model_name=model, megapixels=scalar(resize.get("resize_type.megapixels")),
            seed=_optional_seed(scalar(sampler.get("seed"))), mode="lightning" if lightning else "standard",
            steps=scalar(sampler.get("steps")), cfg=scalar(sampler.get("cfg")))
        return Krea2EditMetadata(prompt=_optional_text(positive["inputs"].get("prompt")), model_name=model,
            megapixels=settings.megapixels, seed=settings.seed, steps=settings.steps,
            firered_settings=settings, origin="png")
    except (KeyError, StopIteration, TypeError, ValueError):
        # Do not suggest a FireRed checkpoint in the KREA2 model selector.
        return Krea2EditMetadata(origin="png", warnings=("Réglages FireRed incomplets : sélectionnez le moteur et ses réglages dans l’atelier.",))


def _loras_from_power_loader(inputs: Mapping[str, object]) -> tuple[Krea2LoraSelection, ...]:
    result: list[Krea2LoraSelection] = []
    for key, raw in inputs.items():
        if not str(key).startswith("lora_") or not isinstance(raw, Mapping):
            continue
        if raw.get("on") is not True:
            continue
        name = _optional_text(raw.get("lora"))
        strength = raw.get("strength")
        if name and isinstance(strength, (int, float)) and not isinstance(strength, bool):
            try:
                result.append(Krea2LoraSelection(name=name, strength=float(strength)))
            except ValueError:
                continue
    return tuple(result)


def _loras_from_lora_stack(inputs: Mapping[str, object]) -> tuple[Krea2LoraSelection, ...]:
    """Read the flat lora_01/strength_01 fields emitted by rgthree's stack node."""
    result: list[Krea2LoraSelection] = []
    for key, raw_name in inputs.items():
        key_text = str(key)
        if not key_text.startswith("lora_") or not isinstance(raw_name, str):
            continue
        name = _optional_text(raw_name)
        if not name or name.casefold() in {"none", "off"}:
            continue
        suffix = key_text.removeprefix("lora_")
        strength = inputs.get(f"strength_{suffix}")
        if isinstance(strength, (int, float)) and not isinstance(strength, bool):
            try:
                result.append(Krea2LoraSelection(name=name, strength=float(strength)))
            except ValueError:
                continue
    return tuple(result)


def _loras_from_list(value: object) -> tuple[Krea2LoraSelection, ...]:
    if not isinstance(value, list):
        return ()
    result: list[Krea2LoraSelection] = []
    for raw in value[:10]:
        if not isinstance(raw, Mapping):
            continue
        name = _optional_text(raw.get("name"))
        strength = raw.get("strength")
        if name and isinstance(strength, (int, float)) and not isinstance(strength, bool):
            result.append(Krea2LoraSelection(name=name, strength=float(strength)))
    return tuple(result)


def _first_seed(inputs: Mapping[str, object]) -> int | None:
    for key in ("seed", "value"):
        value = _optional_seed(inputs.get(key))
        if value is not None:
            return value
    return None


def _optional_ratio(value: object) -> Krea2AspectRatio | None:
    if not isinstance(value, str):
        return None
    try:
        return Krea2AspectRatio(value.strip())
    except ValueError:
        return None


def _optional_number(value: object) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _optional_seed(value: object) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool) and 0 <= value < 2**64:
        return value
    return None


def _optional_text(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return value
