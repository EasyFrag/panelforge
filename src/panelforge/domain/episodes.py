"""Episode fabrication snapshots, independent of image/video providers."""
from copy import deepcopy
import hashlib
import json

from .stories import (
    DEFAULT_DIALOGUE_LANGUAGE, SILENT_CATS_RECIPE_ID, dialogue_instruction,
    dialogue_language_label, dialogue_language_selection, story_recipe_selection,
    validate_scenario, visual_transition_instruction,
)
from .prompt_lab import CreativeFreedomAxes
from .long_stories import fabrication_scenario
from .krea2_sampling import Krea2AssistedSampling
from .krea2_assisted_workflows import DEFAULT_KREA2_ASSISTED_WORKFLOW
from dataclasses import asdict

REF2V_COOKBOOK = ("minimax.h3.ref2v.classic.cinematic.planned", "1.0.0")
REF2V_PROFILE = ("minimax.h3.ref2v.classic.cinematic", "1.0.0")
DEFAULT_PLAN_MODEL = "local::unsloth/Qwen3.8-27B-GGUF"
DEFAULT_WRITER_MODEL = "local::unsloth/gemma-4-31B-it-qat-GGUF"
DEFAULT_CREATIVE_AXES = dict(scene_life=3, camera=3, extra_motion=3, dialogue=1)


def image_defaults(episode):
    result = deepcopy(episode.get("image_defaults") or {})
    result.setdefault("model_id", None)
    result.setdefault("loras", [])
    result.setdefault("sampling", asdict(Krea2AssistedSampling()))
    result.setdefault("workflow", asdict(DEFAULT_KREA2_ASSISTED_WORKFLOW))
    return result


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
        seed_locked=True, initial_megapixels=0.9, checkpoint=None, music_enabled=False, spectrum_enabled=False,
        force_upscale=False,
        bunny=dict(turbo_enabled=True, base_steps=9, coarse_steps=4, refine_steps=5,
                   lora_second_strength=0.2, preview_enabled=True),
        video_loras=dict(version="0.2.0", enabled=True, clip_last_layer=None, entries=[
            dict(name="minmax_nsfw/Motion_Repair.safetensors", strength=0.6,
                 second_strength=0.2, enabled=True)]))


def video_defaults(episode):
    value = episode.get("video_defaults")
    if value:
        return deepcopy(value)
    scenes = episode.get("scenes") or []
    duration = scenes[0].get("duration", 10) if scenes else 10
    return deepcopy(scenes[0].get("render_setup") if scenes else None) or default_render_setup(duration)


def inherits_video_settings(scene):
    return scene.get("inherit_video_settings", True)


def effective_video_setup(episode, scene):
    setup = deepcopy(scene.get("render_setup") or default_render_setup(scene["duration"]))
    if not inherits_video_settings(scene):
        return setup
    seed = setup.get("settings", {}).get("seed", 0)
    setup = video_defaults(episode)
    setup.setdefault("settings", {})
    setup["settings"]["duration_seconds"] = scene["duration"]
    setup["settings"]["seed"] = seed
    return setup


def scene_action(scene):
    lines = [f"Situation initiale : {scene['opening_state']}"]
    if scene.get("relationship_state"):
        lines.append(f"Dynamique relationnelle : {scene['relationship_state']}")
    if scene.get("appearance_state"):
        lines.append(f"Continuité des tenues : {scene['appearance_state']}")
    if scene.get("sexual_state"):
        lines.append(f"Position et contacts sexuels au début : {scene['sexual_state']}")
    lines.extend((scene["action"], f"À la fin : {scene['ending_state']}"))
    return "\n\n".join(lines)


def initial_episode(story, identity):
    recipe = story_recipe_selection(story.get("recipe"))
    scenario = validate_scenario(fabrication_scenario(story), recipe["id"], recipe["version"])
    selected_series_episode = story["document"].get("selected_episode_id")
    episode_format = (story["document"].get("episode_formats") or {}).get(selected_series_episode, {})
    clip_seconds = episode_format.get("clip_seconds", story["clip_seconds"])
    series_episode_index = None
    outline = story["document"].get("series_outline") or {}
    for index, item in enumerate(outline.get("episodes", []), 1):
        if item["id"] == selected_series_episode:
            series_episode_index = index
            break
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
            duration=clip_seconds, intention=scene_action(scene), references=bindings,
            plan_model_id=DEFAULT_PLAN_MODEL, writer_model_id=DEFAULT_WRITER_MODEL,
            shot_count=None, audacity=3, creative_axes=deepcopy(DEFAULT_CREATIVE_AXES), preparations=[], render_revision=1,
            render_setup=default_render_setup(clip_seconds), inherit_video_settings=True))
        scenes[-1]["render_setup"]["settings"]["seed"] = int(fingerprint([identity, index])[:12], 16)
    source_value = [selected_series_episode, scenario] if selected_series_episode else scenario
    result = dict(episode_id=identity, story_id=story["project_id"], title=scenario["title"],
        story_revision=story["revisions"][-1]["revision"], source_hash=fingerprint(source_value),
        story_recipe=deepcopy(recipe), dialogue_language=dialogue_language_selection(
            story.get("dialogue_language", DEFAULT_DIALOGUE_LANGUAGE)),
        scenario=deepcopy(scenario), references=refs, scenes=scenes,
        series_episode_id=selected_series_episode, series_episode_index=series_episode_index,
        style="", visual_revision=1,
        style_image=None, style_preset=None, image_defaults=image_defaults({}),
        reference_profiles={}, reference_batch=None,
        video_defaults=default_render_setup(clip_seconds), video_revision=1, video_chain=None,
        cookbook=dict(id=REF2V_COOKBOOK[0], version=REF2V_COOKBOOK[1]))
    if story.get("visual_state_policy") == 1:
        result["visual_state_policy"] = 1
    if "visual_continuity" in scenario:
        from .episode_continuity import sync_references
        result.update(continuity_version=1, continuity_revision=1)
        sync_references(result, DEFAULT_PLAN_MODEL)
    return result


def only_reference_images_changed(previous, current):
    """Allow image replacement only when the complete prompt contract is unchanged."""
    if not previous or not previous.get("references") or previous == current:
        return False
    def without_images(inputs):
        return {**inputs, "references": [
            {key: value for key, value in ref.items() if key != "asset_id"}
            for ref in inputs.get("references", [])]}
    return (all(ref.get("asset_id") for ref in current.get("references", []))
            and without_images(previous) == without_images(current))


def scene_inputs(episode, scene, *, require_images=True):
    from . import episode_continuity, story_continuity
    if episode.get("localization"):
        from .episode_localization import frozen_inputs
        return frozen_inputs(scene)
    if require_images:
        missing = episode_continuity.missing_requirements(episode, scene)
        if missing:
            raise episode_continuity.RequiredReferenceMissing(" ".join(item["message"] for item in missing))
    axes = CreativeFreedomAxes(**scene.get("creative_axes", DEFAULT_CREATIVE_AXES))
    refs = {r["id"]: r for r in episode["references"]}
    bindings = episode_continuity.bindings(episode, scene)
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
        if require_images and episode_continuity.active(episode) and ref.get("continuity_image_stale"):
            raise ValueError(f"L'état de {ref['name']} a changé. Confirmez ou remplacez son image dans la fiche avant de préparer le prompt.")
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
    if episode_continuity.active(episode):
        continuity_text = story_continuity.instructions(episode["scenario"], scene["index"],
            explicit_presence=episode_continuity.required_states(episode))
        if continuity_text:
            lines.append(continuity_text)
        lines.append("Les images ancrent les identités. Les états acquis ci-dessus déterminent le corps, la tenue et les objets à cet instant. "
                     "Une variante est le même personnage, pas un personnage supplémentaire. "
                     "Les émotions ne créent pas d'action physique non demandée : abattu signifie découragé, pas allongé ; humilié ne signifie pas rétréci.")
    transition = visual_transition_instruction(source_scene,
        silent=(episode.get("story_recipe") or {}).get("id") == SILENT_CATS_RECIPE_ID)
    if transition:
        lines.append(transition)
    if source_scene["dialogue"]:
        language = dialogue_language_selection(episode.get("dialogue_language", DEFAULT_DIALOGUE_LANGUAGE))
        lines.append(
            f"Langue parlée obligatoire : {dialogue_language_label(language)}. Dans le Plan REF2V, chaque entrée "
            f"spoken_languages correspondant à ces répliques contient exactement {language} ; conserve leurs mots sans traduction."
        )
        lines.append("Répliques exactes, dans cet ordre et avec ces locuteurs :\n" + "\n".join(
            dialogue_instruction(d, people[d["speaker_id"]]["name"]) for d in source_scene["dialogue"]))
    elif axes.dialogue < 2:
        lines.append("Aucun dialogue.")
    requested_delivery = any(line.get("delivery", "spoken") != "spoken" for line in source_scene["dialogue"])
    delivery_rule = ("Respecte exactement les modes de restitution indiqués et n’ajoute aucune autre voix off, "
                     if requested_delivery else "Sans voix off, ")
    lines.append("Invente une mise en scène créative, vivante et expressive. Les gestes et réactions accompagnent les paroles. "
                 "Préserve les identités et les objets importants. "
                 + ("Sans dialogue supplémentaire, " if axes.dialogue < 2 else
                    "Ne remplace ni ne reformule les répliques du scénario. Les ajouts éventuels suivent le niveau Dialogues et réactions choisi. ")
                 + delivery_rule + "musique ni texte à l’écran.")
    result = dict(references=selected, source_text="\n\n".join(lines),
        plan_model_id=scene["plan_model_id"], writer_model_id=scene["writer_model_id"],
        shot_count=scene["shot_count"], audacity=scene["audacity"], cookbook=episode["cookbook"])
    # Old preparations keep their fingerprints until their inputs are edited.
    if "creative_axes" in scene:
        result["creative_axes"] = deepcopy(scene["creative_axes"])
    if episode_continuity.active(episode):
        result["visual_continuity"] = episode_continuity.snapshot(episode, scene)
    return result
