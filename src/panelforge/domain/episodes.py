"""Episode fabrication snapshots, independent of image/video providers."""
from copy import deepcopy
import hashlib
import json

from .stories import validate_scenario
from .prompt_lab import CreativeFreedomAxes
from .krea2_sampling import Krea2AssistedSampling
from dataclasses import asdict

REF2V_COOKBOOK = ("minimax.h3.ref2v.classic.cinematic.planned", "1.0.0")
REF2V_PROFILE = ("minimax.h3.ref2v.classic.cinematic", "1.0.0")
DEFAULT_PLAN_MODEL = "local::unsloth/Qwen3.8-27B-GGUF"
DEFAULT_WRITER_MODEL = "local::unsloth/gemma-4-31B-it-qat-GGUF"
DEFAULT_CREATIVE_AXES = dict(scene_life=1, camera=2, extra_motion=1, dialogue=0)


def image_defaults(episode):
    return deepcopy(episode.get("image_defaults") or dict(
        model_id=None, loras=[], sampling=asdict(Krea2AssistedSampling())))


def inherits_images(ref):
    # Existing explicit choices stay personal when opening a v1 fabrication.
    return ref.get("inherit_image_settings", ref.get("render_settings") is None)


def effective_image_settings(episode, ref):
    settings = deepcopy(ref.get("render_settings") or {})
    common = image_defaults(episode)
    if inherits_images(ref):
        settings.update({key: val for key, val in common.items() if val is not None})
    return settings


def style_context(episode):
    return dict(style=episode["style"], image=deepcopy(episode.get("style_image")),
                preset=deepcopy(episode.get("style_preset")))
REFERENCE_ROLES = {
    "subject_reference": "subject", "environment_reference": "environment",
    "style_reference": "style", "composition_reference": "composition",
    "motion_reference": "motion", "keyframe_reference": "keyframe",
    "first_frame": "first_frame", "last_frame": "last_frame",
}


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def default_render_setup(duration):
    # Recipe IDs and user settings only. Graph bindings remain in manifests.
    return dict(recipe={"id": "minimax-h3-bunny", "version": "0.1.3"},
        settings=dict(aspect_ratio="9:16 (Portrait Widescreen)", megapixels=0.9,
                      duration_seconds=duration, steps=9, seed=0),
        initial_megapixels=0.9, checkpoint=None, music_enabled=False, spectrum_enabled=False,
        bunny=dict(turbo_enabled=True, base_steps=9, coarse_steps=4, refine_steps=5,
                   lora_second_strength=0.2, preview_enabled=True),
        video_loras=dict(version="0.2.0", enabled=True, clip_last_layer=None, entries=[
            dict(name="minmax_nsfw/Motion_Repair.safetensors", strength=0.6,
                 second_strength=0.2, enabled=True)]))


def scene_action(scene):
    return (f"Situation initiale : {scene['opening_state']}\n\n{scene['action']}\n\n"
            f"À la fin : {scene['ending_state']}")


def initial_episode(story, identity):
    scenario = validate_scenario(story["document"]["scenario"])
    refs, lookup = [], {}
    for kind, collection in (("character", "characters"), ("location", "locations")):
        for index, item in enumerate(scenario[collection]):
            ref_id = f"{kind}-{index + 1}"
            lookup[(kind, item["id"])] = ref_id
            refs.append(dict(id=ref_id, source_id=item["id"], kind=kind, name=item["name"],
                description=item["description"], revision=1, image_asset_id=None, images=[],
                krea_project_id=None, prompt="", model_id=DEFAULT_PLAN_MODEL,
                render_settings=None, inherit_image_settings=True, job=None))
    scenes = []
    for index, scene in enumerate(scenario["scenes"]):
        bindings = [dict(reference_id=lookup[("character", cid)], role="subject_reference")
                    for cid in scene["character_ids"]]
        bindings.append(dict(reference_id=lookup[("location", scene["location_id"])], role="environment_reference"))
        # Preserve all requested assets, even when the user must reduce a scene to nine.
        scenes.append(dict(id=f"scene-{index + 1}", index=index, title=scene["title"], revision=1,
            duration=story["clip_seconds"], intention=scene_action(scene), references=bindings,
            plan_model_id=DEFAULT_PLAN_MODEL, writer_model_id=DEFAULT_WRITER_MODEL,
            shot_count=None, audacity=2, creative_axes=deepcopy(DEFAULT_CREATIVE_AXES), preparations=[], render_revision=1,
            render_setup=default_render_setup(story["clip_seconds"])))
        scenes[-1]["render_setup"]["settings"]["seed"] = int(fingerprint([identity, index])[:12], 16)
    return dict(episode_id=identity, story_id=story["project_id"], title=scenario["title"],
        story_revision=story["revisions"][-1]["revision"], source_hash=fingerprint(scenario),
        scenario=deepcopy(scenario), references=refs, scenes=scenes, style="", visual_revision=1,
        style_image=None, style_preset=None, image_defaults=image_defaults({}),
        cookbook=dict(id=REF2V_COOKBOOK[0], version=REF2V_COOKBOOK[1]))


def scene_inputs(episode, scene, *, require_images=True):
    axes = CreativeFreedomAxes(**scene.get("creative_axes", DEFAULT_CREATIVE_AXES))
    refs = {r["id"]: r for r in episode["references"]}
    bindings = scene["references"]
    if not 1 <= len(bindings) <= 9:
        raise ValueError("Choisissez entre une et neuf images pour cette scène, personnages et décor compris.")
    if len({b["reference_id"] for b in bindings}) != len(bindings):
        raise ValueError("Une même fiche ne peut pas être ajoutée deux fois à la scène.")
    selected = []
    for binding in bindings:
        ref = refs.get(binding["reference_id"])
        if ref is None or binding["role"] not in REFERENCE_ROLES:
            raise ValueError("Référence ou rôle inconnu.")
        if require_images and not ref["image_asset_id"]:
            raise ValueError(f"Choisissez une image pour {ref['name']} avant de préparer le prompt.")
        selected.append(dict(reference_id=ref["id"], name=ref["name"], asset_id=ref["image_asset_id"],
                             role=binding["role"], kind=ref["kind"], source_id=ref["source_id"]))
    for role in ("first_frame", "last_frame"):
        if sum(b["role"] == role for b in bindings) > 1:
            raise ValueError("Une seule première et dernière frame sont possibles.")
    source_scene = episode["scenario"]["scenes"][scene["index"]]
    people = {p["id"]: p for p in episode["scenario"]["characters"]}
    lines = [f"Durée cible : {scene['duration']:g} secondes.", "Références de cette scène :\n" + "\n".join(
        f"<Picture {i}> : {ref['name']}." for i, ref in enumerate(selected, 1))]
    missing_people = [people[c] for c in source_scene["character_ids"] if not any(
        r["kind"] == "character" and r["source_id"] == c for r in selected)]
    if missing_people:
        lines.append("Personnages sans image de référence :\n" + "\n".join(
            f"{p['name']} : {p['description']}" for p in missing_people))
    location = next(l for l in episode["scenario"]["locations"] if l["id"] == source_scene["location_id"])
    if not any(r["kind"] == "location" and r["source_id"] == location["id"] for r in selected):
        lines.append(f"Décor : {location['name']}. {location['description']}")
    lines.append(scene["intention"])
    if source_scene["dialogue"]:
        lines.append("Répliques françaises exactes, dans cet ordre et avec ces locuteurs :\n" + "\n".join(
            f"{people[d['speaker_id']]['name']} : « {d['text']} »" for d in source_scene["dialogue"]))
    elif axes.dialogue < 2:
        lines.append("Aucun dialogue.")
    lines.append("Invente une mise en scène créative, vivante et expressive. Les gestes et réactions accompagnent les paroles. "
                 "Préserve les identités et les objets importants. "
                 + ("Sans dialogue supplémentaire, " if axes.dialogue < 2 else
                    "Ne remplace ni ne reformule les répliques du scénario. Les ajouts éventuels suivent le niveau Dialogues et réactions choisi. Sans ")
                 + "voix off, musique ni texte à l’écran.")
    result = dict(references=selected, source_text="\n\n".join(lines),
        plan_model_id=scene["plan_model_id"], writer_model_id=scene["writer_model_id"],
        shot_count=scene["shot_count"], audacity=scene["audacity"], cookbook=episode["cookbook"])
    # Old preparations keep their fingerprints until their inputs are edited.
    if "creative_axes" in scene:
        result["creative_axes"] = deepcopy(scene["creative_axes"])
    return result
