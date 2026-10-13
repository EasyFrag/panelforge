"""Reuse existing KREA2, MiniMax and factory lifecycles, without new GPU queues."""
from panelforge.domain.krea2_batch import Krea2AspectRatio, Krea2PromptLanguage
from panelforge.domain.krea2_sampling import Krea2AssistedSettings, sampling_from_dict
from panelforge.domain.krea2_assisted_workflows import workflow_selection_from_dict
from .cooking_recipe_prompting import image_instruction


class CookingRecipeProduction:
    def __init__(self, krea, minimax, factory, sources=None):
        self.krea, self.minimax, self.factory, self.sources = krea, minimax, factory, sources

    def presets(self):
        return [dict(id=p.preset_id, name=p.name, image_asset_id=p.image_asset_id)
                for p in self.krea.list_style_presets()]

    def recent_images(self):
        result, seen = [], set()
        for p in self.krea.list(limit=50):
            for a in reversed(p.attempts):
                if str(a.status) == "succeeded" and a.output_asset_id and a.output_asset_id not in seen:
                    seen.add(a.output_asset_id)
                    result.append(dict(asset_id=a.output_asset_id, label=p.name,
                                       project_id=p.project_id, attempt_id=a.attempt_id))
        if self.sources:
            for item in self.sources.recent(limit=50)["images"]:
                if item["asset_id"] not in seen:
                    seen.add(item["asset_id"]); result.append(item)
        return result[:100]

    def prepare_master(self, snapshot, key, feedback):
        s = snapshot["settings"]
        if not s["style_preset_id"]:
            raise ValueError("Choisis un preset KREA2 pour créer le plat.")
        intention = ("Create the FINISHED plated dish for this culinary film. " + s["intention"]
            + "\nMaterials: " + s["world"] + "\nCook if visible: " + s["cook"]
            + "\nSingle beautiful food image, no text or storyboard. " + feedback)
        p = self.krea.create_project(name=("Recette · " + snapshot["name"])[:120], intention=intention,
            model_id=s["model_id"], style_preset_id=s["style_preset_id"], assistance_recipe_version="6.0.0",
            prompt_language=Krea2PromptLanguage.ENGLISH, local_inspiration_enabled=False, managed_key=key)
        return dict(engine="krea", project_id=p.project_id)

    def submit_master(self, link, snapshot, checkpoint):
        p = self.krea.get(link["project_id"])
        if not p.current_prompt:
            for event in self.krea.stream_chat(p.project_id, p.intention, expected_branch_id=p.active_branch_id,
                                               include_reasoning=False, refresh_prompt_examples=False):
                if getattr(event, "error", None):
                    raise ValueError(str(event.error))
            p = self.krea.get(p.project_id)
        if not p.current_prompt:
            raise ValueError("KREA2 n’a pas fourni de prompt exploitable.")
        if not link.get("attempt_id"):
            # This managed child belongs to one request only; recover a prepared attempt.
            if p.attempts:
                attempt = p.attempts[-1]
            else:
                preset = p.style_preset
                if preset is None:
                    raise ValueError("Le preset KREA2 de cet essai est absent.")
                settings = Krea2AssistedSettings(model_name=preset.settings.model_name,
                    loras=preset.settings.loras, aspect_ratio=Krea2AspectRatio(snapshot["settings"]["aspect_ratio"]),
                    megapixels=2.1, sampling=sampling_from_dict(None, default_preset_id="finish_4"),
                    workflow=workflow_selection_from_dict(dict(recipe_id="krea2-flux-klein", version="1.0.0")))
                p = self.krea.prepare_attempt(p.project_id, prompt=p.current_prompt, settings=settings,
                                             expected_branch_id=p.active_branch_id, enqueue=False)
                attempt = p.attempts[-1]
            link["attempt_id"] = attempt.attempt_id
            checkpoint(link)
        p = self.krea.get(p.project_id)
        attempt = next(a for a in p.attempts if a.attempt_id == link["attempt_id"])
        if str(attempt.status) == "created":
            self.krea.queue_attempt(p.project_id, attempt.attempt_id)
        return link

    def prepare_image(self, snapshot, shot, role, start, feedback, key):
        refs = [dict(asset_id=snapshot["master_asset_id"], name="Plat terminé",
                     role="Identité des ingrédients, palette et monde matériel. Ne pas copier l’état cuit ou dressé dans les étapes antérieures.")]
        p = self.minimax.ensure_managed_image(owner="cooking-recipes", key=key,
            name=("Recette · " + shot["title"] + (" · arrivée" if role == "end" else ""))[:120],
            source_asset_id=start if role == "end" else None, references=refs,
            draft=image_instruction(snapshot, shot, role, feedback), model_id=snapshot["settings"]["edit_model_id"],
            settings=dict(resolution="source" if role == "end" else "2", reuse_seed=False,
                          aspect_ratio=snapshot["settings"]["aspect_ratio"].split(" ")[0]))
        return dict(engine="minimax", project_id=p["id"], stage_id=p["stages"][0]["id"],
                    request_id="recipe-" + key)

    def submit_image(self, link, checkpoint):
        p = self.minimax.get(link["project_id"])
        stage = next(s for s in p["stages"] if s["id"] == link["stage_id"])
        message = next((m for m in stage["messages"] if m["request_id"] == link["request_id"]), None)
        if message is None:
            p, mid = self.minimax.begin_message(p["id"], stage["id"], revision=stage["revision"],
                                               request_id=link["request_id"], render_after_prompt=False)
            message = next(m for m in p["stages"][0]["messages"] if m["id"] == mid)
        link["message_id"] = message["id"]
        checkpoint(link)
        if message["status"] == "queued":
            self.minimax.execute_message(p["id"], stage["id"], message["id"])
        p = self.minimax.get(p["id"])
        stage = next(s for s in p["stages"] if s["id"] == link["stage_id"])
        message = next(m for m in stage["messages"] if m["id"] == link["message_id"])
        if message["status"] != "succeeded" or not message.get("applied"):
            raise ValueError(message.get("error") or "Le prompt de l’image n’a pas été appliqué.")
        self.minimax.queue_attempt(p["id"], stage["id"], revision=stage["revision"], request_id=link["request_id"])
        return link

    def image_result(self, link):
        if link["engine"] == "krea":
            p = self.krea.get(link["project_id"])
            a = next((a for a in p.attempts if a.attempt_id == link.get("attempt_id")), None)
            if a is None:
                return dict(status="failed", error="Préparation interrompue avant la mise en file.")
            return dict(status=str(a.status), asset_id=a.output_asset_id, error=a.error,
                        prompt=a.prompt, attempt_id=a.attempt_id)
        p = self.minimax.get(link["project_id"])
        stage = next(s for s in p["stages"] if s["id"] == link["stage_id"])
        a = next((a for a in stage["attempts"] if a.get("request_id") == link["request_id"]), None)
        if a is None:
            return dict(status="failed", error="Préparation interrompue avant la mise en file.")
        return dict(status=a["status"], asset_id=a.get("output_asset_id"), error=a.get("error"),
                    prompt=a.get("prompt", ""), attempt_id=a["id"])

    def video_items(self, ids):
        # Read only; the factory remains the sole owner of execution and recovery.
        wanted = set(ids)
        return {i["id"]:i for i in self.factory.snapshot()["items"] if i["id"] in wanted} if ids else {}

    def submit_clip(self, entry, checkpoint):
        received = self.factory.receive([entry])
        identity = received["ids"][0]
        checkpoint(dict(factory_id=identity))
        item = self.video_items([identity])[identity]
        if item["status"] == "preparation":
            self.factory.launch([identity], {identity:item["revision"]})
        return identity
