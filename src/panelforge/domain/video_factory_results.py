"""Path-free delivery selection and publication text for factory results."""
from .video_factory import STAGES, fingerprint


def variant_text(variant):
    parts = [str(variant.get(key) or "").strip() for key in ("hook", "caption")]
    body = "\n\n".join(part for part in parts if part)
    emojis = []
    for emoji in variant.get("emojis", []):
        if emoji and emoji not in body and emoji not in emojis:
            emojis.append(emoji)
    return "\n\n".join(part for part in (
        body, " ".join(emojis), " ".join(variant.get("hashtags", []))) if part)


def instagram_text(item):
    variants = item["steps"]["social"].get("output", {}).get("variants", [])
    if not variants:
        return ""
    language = item["config"]["social"]["language"].upper()
    parts = [item["name"], "Instagram · " + language]
    parts.extend(f"Variante {index + 1}\n\n{variant_text(variant)}"
                 for index, variant in enumerate(variants))
    return "\n\n--------------------\n\n".join(parts) + "\n"


def delivery_material(item):
    if item["status"] == "preparation" or item["steps"]["video"]["status"] != "succeeded":
        return None
    dlss = item["steps"]["dlss"]
    if dlss["status"] in {"pending", "running"}:
        return None
    stage = "dlss" if dlss["status"] == "succeeded" else "video"
    step = item["steps"][stage]
    asset_id = step.get("output", {}).get("asset_id")
    if not asset_id:
        return None
    config = item.get("launch_snapshot") or item["config"]
    preset = config.get("preset_origin") or config["preset"]
    family = ("Histoire" if item["source"].get("kind") == "episode" else
              {"little_men": "Petits hommes", "little_men_experimental": "Petits hommes", "lips": "Levres"}.get(preset, "Autres"))
    name = item["name"]
    if family == "Histoire":
        name = f"{item['source'].get('group', 'Histoire')}_scene_{item['source'].get('index', 0) + 1:02d}_{name}"
    material = dict(asset_id=asset_id, stage=stage, family=family, name=name,
                    completed_at=step.get("finished_at") or item.get("launched_at") or item["created_at"],
                    text=instagram_text(item))
    material["key"] = fingerprint(material)
    return material


def can_archive(item):
    """Only reviewed, fully finished deliveries can leave the results inbox."""
    if (item.get("archived_at") or item["status"] != "succeeded" or item.get("remove_requested")
            or item.get("cancel_requested") or item.get("recover_stage")):
        return False
    if any(item["steps"][stage]["status"] not in {"succeeded", "skipped"} for stage in STAGES):
        return False
    delivery = item.get("delivery", {})
    if delivery.get("status") != "succeeded":
        return False
    material = delivery_material(item)
    # A last IG response may have completed after the previous video-only export.
    return bool(material and delivery.get("key") == material["key"])
