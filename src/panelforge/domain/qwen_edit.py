"""Image roles, render settings and immutable context identities for Qwen editing."""

from dataclasses import asdict, dataclass
import hashlib
import json
import math
import re


MAX_RENDER_IMAGES = 16
MAX_ASSISTANT_IMAGES = 32
ACTIVE_ATTEMPTS = {"queued", "running", "cancel_pending"}
RATIOS = ("1:1", "3:2", "2:3", "16:9", "9:16")


@dataclass(frozen=True, slots=True)
class QwenEditSettings:
    resolution: str = "source"
    aspect_ratio: str = "1:1"
    steps: int = 25
    cfg: float = 1.0
    seed: str = "1234"
    reuse_seed: bool = True
    negative_prompt: str = ""
    color_finish: str = "natural"

    def __post_init__(self):
        if self.resolution not in {"source", "1", "2", "4"} or self.aspect_ratio not in RATIOS:
            raise ValueError("Résolution ou format Qwen invalide.")
        if type(self.steps) is not int or not 1 <= self.steps <= 100:
            raise ValueError("Les steps doivent être compris entre 1 et 100.")
        if isinstance(self.cfg, bool) or not isinstance(self.cfg, (int, float)) or not math.isfinite(self.cfg) or not 1 <= self.cfg <= 10:
            raise ValueError("Le CFG doit être compris entre 1 et 10.")
        if not isinstance(self.seed, str) or not re.fullmatch(r"[0-9]{1,20}", self.seed) or int(self.seed) >= 2**64:
            raise ValueError("Seed invalide : entier positif inférieur à 2⁶⁴.")
        if (type(self.reuse_seed) is not bool or not isinstance(self.negative_prompt, str)
                or len(self.negative_prompt) > 12000 or self.color_finish not in {"natural", "raw"}):
            raise ValueError("Réglages Qwen invalides.")

    def dimensions(self, source_size=None):
        if source_size is not None:
            width, height = source_size
        else:
            width, height = map(int, self.aspect_ratio.split(":"))
        if source_size is None or self.resolution != "source":
            pixels = float(self.resolution if self.resolution != "source" else "1") * 1024**2
            scale = math.sqrt(pixels / (width * height))
            width, height = width * scale, height * scale
        return max(32, round(width / 32) * 32), max(32, round(height / 32) * 32)

    def record(self):
        return asdict(self)


def validate_references(references):
    if not isinstance(references, list) or len(references) > 256:
        raise ValueError("Trop d’images conservées dans cette étape (256 maximum).")
    ids, names = set(), set()
    for ref in references:
        if not isinstance(ref, dict) or set(ref) != {"id", "asset_id", "name", "role", "usage", "active"}:
            raise ValueError("Référence d’image invalide.")
        for field, limit in (("id", 80), ("asset_id", 100), ("name", 80)):
            if not isinstance(ref[field], str) or not ref[field].strip() or len(ref[field]) > limit:
                raise ValueError("Chaque image doit avoir un identifiant et un nom.")
        if ref["id"] in ids or (ref["active"] and ref["name"].strip().casefold() in names):
            raise ValueError("Les noms des images actives doivent être différents.")
        ids.add(ref["id"])
        if ref["active"]:
            names.add(ref["name"].strip().casefold())
        if ref["usage"] not in {"assistant", "render"} or type(ref["active"]) is not bool:
            raise ValueError("Usage d’image invalide.")
        if not isinstance(ref["role"], str) or len(ref["role"]) > 300:
            raise ValueError("Le rôle doit rester inférieur à 300 caractères.")


def render_inputs(stage):
    result = []
    if stage["source_asset_id"]:
        result.append({"id": "source", "asset_id": stage["source_asset_id"], "name": "Source", "role": "Image à modifier"})
        guide = stage.get("guide")
        if guide:
            result.append({"id": "guide", "asset_id": guide["mask_asset_id"], "name": "Zone peinte",
                           "role": "Masque visuel : blanc = zone où concentrer la modification"})
    result.extend({key: ref[key] for key in ("id", "asset_id", "name", "role")}
                  for ref in stage["references"] if ref["active"] and ref["usage"] == "render")
    if len(result) > MAX_RENDER_IMAGES:
        raise ValueError("Qwen accepte 16 images au total, source comprise.")
    return [{**ref, "tag": f"<image{index}>"} for index, ref in enumerate(result, 1)]


def context_snapshot(stage):
    return {"mode": stage["mode"], "source_asset_id": stage["source_asset_id"],
            "guide": dict(stage["guide"]) if stage.get("guide") else None,
            "references": [dict(ref) for ref in stage["references"] if ref["active"]],
            "render_inputs": render_inputs(stage),
            "aspect_ratio": stage["settings"]["aspect_ratio"] if stage["mode"] == "composition" else "source"}


def context_fingerprint(stage):
    return hashlib.sha256(json.dumps(context_snapshot(stage), ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def validate_prompt(prompt, inputs):
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 24000:
        raise ValueError("Écris ou prépare une instruction de rendu (24 000 caractères maximum).")
    indexes = {int(value) for value in re.findall(r"<image(\d+)>", prompt)}
    if any(index < 1 or index > len(inputs) for index in indexes):
        raise ValueError("Le prompt cite une image qui ne sera pas envoyée à Qwen. Actualise l’instruction.")
    if len(inputs) > 1 and indexes != set(range(1, len(inputs) + 1)):
        raise ValueError("Le prompt doit préciser l’usage de chaque référence Qwen. Actualise l’instruction.")


def prompt_is_ready(stage):
    return bool(stage["prompt"].strip()) and stage.get("prompt_fingerprint") == context_fingerprint(stage)
