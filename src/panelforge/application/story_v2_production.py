"""Translate an approved screenplay to the shared episode and factory contracts."""
from copy import deepcopy
from uuid import uuid5, NAMESPACE_URL
from panelforge.domain.episodes import initial_episode
from panelforge.domain.story_v2_settings import image_settings
from .story_v2_images import StoryV2Images, attach_variants
from panelforge.domain.story_v2 import digest, validate_script

def dialogue_addressing(sequence, names):
    """A compact story brief, not a video Plan or an additional model call."""
    lines = []
    for index, line in enumerate(sequence["dialogue"], 1):
        recipients = line.get("addressee_ids") or []
        if not recipients:
            continue
        target = ", ".join(names[identity] for identity in recipients)
        cue = line.get("address_cue", "")
        lines.append(f"Réplique {index} — {names[line['speaker_id']]} s'adresse à {target}."
                     + (" " + cue if cue else ""))
    if lines:
        lines.append("Rythme de l'échange : laisser le temps de dire chaque réplique naturellement ; "
                     "enchaîner les réponses, hors pauses nécessaires à l'intention.")
    return lines


class StoryV2Production:
    def __init__(self, episodes, factory, *, minimax=None, qwen=None):
        self.episodes, self.factory = episodes, factory
        self.images = StoryV2Images(episodes, minimax, qwen)

    def export(self, project):
        settings = project["settings"]
        script = validate_script(project["script"], settings)
        image_options, video = settings["images"], settings["video"]
        key = digest(dict(script=script, production={k:v for k,v in settings.items() if k not in {"mode", "reader_model", "idea", "duration", "scene_duration", "final_review_enabled", "polish_enabled", "polish_model"}}))
        identity = "episode-" + uuid5(NAMESPACE_URL, project["id"] + key).hex
        try:
            return self.episodes.store.get(identity)["episode_id"]
        except FileNotFoundError:
            pass
        scenario = dict(title=script["title"], logline=" ".join(script["summary"]), presence_policy=1,
            characters=[{k:p[k] for k in ("id", "name", "description")} for p in script["characters"]],
            locations=deepcopy(script["locations"]), scenes=[])
        for s in script["sequences"]:
            scenario["scenes"].append(dict(title=s["title"], location_id=s["location_id"],
                character_ids=s["character_ids"],
                dialogue=[{k:d[k] for k in ("speaker_id", "text", "delivery")} for d in s["dialogue"]],
                action=s["action"],
                opening_state=s["setting"], ending_state="La scène se termine après les actions et répliques décrites."))
        story = dict(project_id=project["id"], document=dict(scenario=scenario), clip_seconds=10,
                     revisions=[dict(revision=project["version"])], dialogue_language=settings["language"])
        episode = initial_episode(story, identity)
        episode.update(source_story_v2=dict(id=project["id"], script_hash=key),
                       style=settings["universe"] + ". " + settings["style"])
        episode["reference_assistance"] = {k:deepcopy(image_options[k]) for k in (
            "assistance_recipe_version", "local_inspiration_enabled", "prompt_language", "style_preset_id", "art_style_id")}
        episode["image_defaults"] = dict(model_id=settings["image_model"],
            workflow=deepcopy(image_options["workflow"]), sampling=deepcopy(image_options["sampling"]),
            loras=deepcopy(image_options["loras"]), aspect_ratio=image_options["aspect_ratio"],
            megapixels=image_options["megapixels"])
        episode["video_defaults"] = deepcopy(video["render"])
        # A deterministic translation, not another writing pass.
        for ref in episode["references"]:
            ref["model_id"] = settings["prompt_model"]
        for obj in script["objects"]:
            episode["references"].append(dict(id="object-" + obj["id"], source_id=obj["id"], kind="object",
                name=obj["name"], description=obj["description"], revision=1, image_asset_id=None, images=[],
                krea_project_id=None, prompt="", model_id=settings["prompt_model"], render_settings=None,
                inherit_image_settings=True, job=None))
        names = {p["id"]:p["name"] for p in script["characters"]}
        for source, scene in zip(script["sequences"], episode["scenes"], strict=True):
            scene.update(duration=source["duration"], audacity=video["audacity"],
                creative_axes=deepcopy(video["creative_axes"]), shot_count=video["shot_count"],
                plan_model_id=video["plan_model"], writer_model_id=video["prompt_model"])
            seed = scene["render_setup"]["settings"]["seed"]
            scene["render_setup"] = deepcopy(video["render"])
            chosen_seed = int(video["render"]["settings"].get("seed") or 0)
            scene["render_setup"]["settings"]["seed"] = chosen_seed or seed
            scene["render_setup"]["settings"]["duration_seconds"] = source["duration"]
            scene["intention"] = "\n".join([source["setting"], source["action"],
                "Intention de jeu : " + source["intention"],
                *dialogue_addressing(source, names),
                "Univers et style : " + episode["style"],
                *[f"Apparence dans cette séquence uniquement — {names[a['character_id']]} : {a['state']}"
                  for a in source["appearances"]]])
            scene["references"].extend(dict(reference_id="object-"+o, role="subject_reference")
                                       for o in source["object_ids"])
        attach_variants(episode, script)
        # Reuse only a reference whose identity AND description AND visual direction are unchanged.
        previous = project.get("episode_id")
        if previous:
            old = self.episodes.store.get(previous)
            if (old.get("style") == episode["style"] and old.get("reference_assistance") == episode["reference_assistance"]
                    and old.get("image_defaults") == episode["image_defaults"]):
                if old.get("story_v2_thumbnail"):
                    episode["story_v2_thumbnail"] = deepcopy(old["story_v2_thumbnail"])
                for ref in episode["references"]:
                    match = next((r for r in old["references"] if all(r.get(k)==ref.get(k)
                                 for k in ("source_id", "kind", "description", "story_v2_state"))), None)
                    if match:
                        for k in ("images", "image_asset_id", "image_style", "inherited_image", "story_v2_edit"):
                            if k in match: ref[k] = deepcopy(match[k])
        self.episodes.store.save(episode)
        return identity

    def start_references(self, project, ids=None, request_id=None, *, retry_thumbnail=False, resume=False):
        episode = self.episodes.get(project["episode_id"])
        selected = list(ids) if ids is not None else [r["id"] for r in episode["references"] if not r["image_asset_id"]]
        known = {r["id"]:r for r in episode["references"]}
        if len(selected) != len(set(selected)) or not set(selected) <= set(known):
            raise ValueError("Sélection de références inconnue ou répétée.")
        # Selecting a state also prepares its identity when missing.
        for ref_id in list(selected):
            state = known[ref_id].get("story_v2_state")
            if state and not known[state["base_id"]]["image_asset_id"] and state["base_id"] not in selected:
                selected.append(state["base_id"])
        for ref in known.values():
            if ((ref.get("story_v2_state") or {}).get("base_id") in selected and ref["id"] not in selected
                    and (ref.get("image_asset_id") or ref.get("story_v2_edit"))):
                selected.append(ref["id"])
        request_id = request_id or (project["id"]+"-"+project["approved"][:16])
        active = episode.get("reference_batch") or {}
        if active.get("status") in {"running", "rendering", "cancelling"} and active.get("request_id") != request_id:
            raise ValueError("Un lot de références est déjà en cours.")
        # Refresh durable outputs before replacing a batch link, without submitting work.
        failed = set(self.images.reconcile(project))
        with self.episodes._lock:
            value = self.episodes.store.get(episode["episode_id"])
            reuse = {}
            for holder in [*value["references"], value.get("story_v2_thumbnail") or {}]:
                ref_id = holder.get("id", "thumbnail")
                link = holder.get("story_v2_edit") or {}
                if (link.get("project_id") and ref_id not in failed
                        and (resume or link.get("status") in {"queued", "running", "submitting", "cancel_pending"})):
                    reuse[ref_id] = deepcopy(link)
            value["story_v2_selection"] = dict(ids=selected, request_id=request_id,
                thumbnail_retry=(retry_thumbnail or (ids == [] and not resume)), reuse_edits=reuse)
            self.episodes.store.save(value)
        bases = [i for i in selected if not known[i].get("story_v2_state")]
        if not bases:
            return
        settings = image_settings(project["settings"]["images"], project["settings"]["image_model"])
        profiles = {kind:dict(model_id=project["settings"]["prompt_model"],
            settings=settings, seed=None, inherit_technical=False) for kind in ("character", "location")}
        self.episodes.start_reference_batch(episode["episode_id"],
            expected_visual_revision=episode["visual_revision"], request_id=request_id,
            reference_ids=bases, profiles=profiles, thermal={})

    def failed_images(self, project):
        self._retain_generated(self.episodes.get(project["episode_id"]))
        return self.images.reconcile(project)

    def _retain_generated(self, value):
        batch = value.get("reference_batch") or {}
        selection = value.get("story_v2_selection") or {}
        if selection and batch.get("request_id") != selection.get("request_id"):
            return value
        for item in batch.get("items", []):
            if item.get("status") == "ready_for_review" and item.get("output_asset_id"):
                ref = next(r for r in value["references"] if r["id"] == item["reference_id"])
                value = self.episodes.select_image(value["episode_id"], ref["id"], ref["revision"], item["output_asset_id"])
        return value

    def advance_images(self, project, automatic=False):
        return self.images.advance(project, automatic)

    def references(self, project, automatic=False):
        # Manual/automatic controls the hand-off to the factory, not image selection.
        value = self._retain_generated(self.episodes.get(project["episode_id"]))
        batch = value.get("reference_batch") or {}
        selection = value.get("story_v2_selection") or {}
        if selection and batch.get("request_id") != selection.get("request_id"):
            batch = {}
        if any(i.get("status") == "failed" for i in batch.get("items", [])):
            raise ValueError("Une référence a échoué ; ouvrez sa fiche pour la reprendre.")
        if batch.get("status") in {"cancelled", "interrupted"}:
            raise ValueError("La préparation des références a été interrompue ; reprenez-la explicitement.")
        current_batch = value.get("reference_batch") or {}
        if batch and any(i.get("status") != "validated" for i in current_batch.get("items", [])):
            return False
        refs = {r["id"]:r for r in value["references"]}
        for ref in refs.values():
            state, link = ref.get("story_v2_state"), ref.get("story_v2_edit") or {}
            if state and ref.get("image_asset_id") == link.get("output_asset_id") and link.get("reference_asset_ids"):
                if link["reference_asset_ids"][0] != refs[state["base_id"]].get("image_asset_id"):
                    return False
        return all(r.get("image_asset_id") for r in value["references"])

    def send(self, project):
        entries = self.factory.adapter.capture_episode(project["episode_id"], auto_dlss=project["settings"]["dlss"])
        if any(e.get("issues") for e in entries):
            raise ValueError("Références incomplètes : " + " · ".join(i for e in entries for i in e.get("issues", [])))
        # Entries themselves are persisted by the caller before receive to survive restart.
        for entry in entries:
            # The factory owns planning and prompt writing, including for a re-export.
            entry["config"]["final_prompt"] = ""
            entry["outputs"] = {}
            entry["runtime"] = {k:v for k,v in entry.get("runtime", {}).items() if k == "episode_inputs"}
            entry["runtime"]["episode_preparation_id"] = None
            entry["source"].update(view="story-v2", story_v2_id=project["id"],
                thumbnail_asset_id=(self.episodes.store.get(project["episode_id"]).get("story_v2_thumbnail") or {}).get("image_asset_id"))
        return entries

    def results(self, project):
        ids = set(project.get("factory_ids", []))
        if not ids: return []
        return [i for i in self.factory.snapshot()["items"] if i["id"] in ids]
