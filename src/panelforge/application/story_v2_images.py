"""Story references derived through the existing MiniMax/Qwen image queues."""
from copy import deepcopy
from threading import RLock, Thread
from panelforge.domain.story_v2 import digest


def attach_variants(episode, script):
    """Bind an explicit appearance only to its own sequence; derive from the stable identity."""
    bases = {r["source_id"]: r for r in episode["references"] if r["kind"] == "character"}
    variants = {}
    for source, scene in zip(script["sequences"], episode["scenes"], strict=True):
        for appearance in source["appearances"]:
            base = bases[appearance["character_id"]]
            state = appearance["state"].strip()
            key = digest([base["id"], state.casefold()])[:20]
            if key not in variants:
                ref = deepcopy(base)
                ref.update(id="state-" + key, name=base["name"] + " · " + state,
                    description=state, image_asset_id=None, images=[], krea_project_id=None, prompt="",
                    story_v2_state=dict(base_id=base["id"], state=state), story_v2_edit=None)
                variants[key] = ref
                episode["references"].append(ref)
            for binding in scene["references"]:
                if binding["reference_id"] == base["id"]:
                    binding["reference_id"] = variants[key]["id"]


class StoryV2Images:
    def __init__(self, episodes, minimax=None, qwen=None):
        self.episodes = episodes
        self.engines = dict(minimax=minimax, qwen=qwen)
        self._lock, self._prompts = RLock(), set()

    def _prompt(self, engine, identity, stage_id, message_id):
        key = (engine.engine, identity, message_id)
        with self._lock:
            if self._prompts:
                return
            self._prompts.add(key)
        def work():
            try:
                engine.execute_message(identity, stage_id, message_id)
            finally:
                with self._lock:
                    self._prompts.discard(key)
        try:
            Thread(target=work, daemon=True, name="story-v2-image-prompt").start()
        except BaseException:
            with self._lock:
                self._prompts.discard(key)
            raise

    @staticmethod
    def _message_attempt(stage, message):
        # The attempt is persisted before auto_render acknowledges its ID.
        # Recover that exact request after a restart; never pick an unrelated render.
        auto = message.get("auto_render") or {}
        return next((a for a in stage["attempts"] if a["id"] == auto.get("attempt_id")), None) or next(
            (a for a in stage["attempts"] if a.get("request_id") == "prompt-" + message["id"]), None)

    @staticmethod
    def _result_error(message, attempt):
        if attempt is not None:
            if attempt["status"] in {"failed", "cancelled", "interrupted"}:
                return attempt.get("error") or "rendu interrompu"
            return None  # A persisted render takes precedence over a lost acknowledgement.
        if message["status"] in {"failed", "interrupted"}:
            return message.get("error") or "préparation interrompue"
        auto = message.get("auto_render") or {}
        if auto.get("status") in {"failed", "skipped"}:
            return auto.get("error") or "mise en file interrompue"
        return None

    def _record_result(self, holder, stage, message):
        link = holder["story_v2_edit"]
        attempt = self._message_attempt(stage, message)
        error = self._result_error(message, attempt)
        status = attempt["status"] if attempt else message["status"]
        link["status"] = "failed" if error else "running" if status == "succeeded" and attempt is None else status
        if attempt is not None:
            link.update(attempt_id=attempt["id"], output_asset_id=attempt.get("output_asset_id"))
            if attempt["status"] == "succeeded" and attempt.get("output_asset_id"):
                asset_id = attempt["output_asset_id"]
                images = holder.setdefault("images", [])
                new_result = not any(i["asset_id"] == asset_id for i in images)
                if new_result:
                    images.append(dict(asset_id=asset_id, label=holder["name"], source_signature=link["signature"]))
                    holder["revision"] = holder.get("revision", 0) + 1
                # Use the first result without a validation stop, in either mode.
                # Polling a known result must preserve a later manual selection.
                selected = holder.get("image_asset_id")
                if (new_result or not selected) and (not selected or selected == link.get("initial_asset_id")):
                    holder["image_asset_id"] = asset_id
                    holder["revision"] = holder.get("revision", 0) + 1
                return False, None
        return True, error

    def reconcile(self, project):
        """Recover linked outputs without starting prompts, renders or new child projects."""
        failed = []
        with self.episodes._lock:
            episode = self.episodes.store.get(project["episode_id"])
            before = deepcopy(episode)
            for holder in [*episode["references"], episode.get("story_v2_thumbnail") or {}]:
                link = holder.get("story_v2_edit") or {}
                engine = self.engines.get(link.get("engine"))
                if not link.get("project_id") or engine is None:
                    continue
                try:
                    child = engine.get(link["project_id"])
                    stage = next(s for s in child["stages"] if s["id"] == link["stage_id"])
                    message = next(m for m in stage["messages"] if m["id"] == link["message_id"])
                    _, error = self._record_result(holder, stage, message)
                except (FileNotFoundError, StopIteration):
                    error = "préparation interrompue"
                if error:
                    link["status"] = "failed"
                    failed.append(holder.get("id", "thumbnail"))
            if episode != before:
                self.episodes.store.save(episode)
        return failed

    def _advance_image(self, episode, holder, *, key, name, source, references, draft, options, automatic, force=False, reuse=None):
        engine = self.engines[options["edit_engine"]]
        if engine is None:
            raise ValueError("Le moteur d’édition choisi est indisponible.")
        signature = digest(dict(source=source, references=references, draft=draft,
                                engine=options["edit_engine"], model=options["edit_model"], ratio=options["aspect_ratio"]))
        old = holder.get("story_v2_edit") or {}
        if (not force and old.get("signature") == signature and holder.get("image_asset_id")
                and holder["image_asset_id"] == old.get("output_asset_id")):
            return False
        identity_key = episode["episode_id"] + ":" + key + ":" + signature
        if reuse and reuse.get("signature") == signature and reuse.get("engine") == engine.engine:
            project = engine.get(reuse["project_id"])
            stage = next(s for s in project["stages"] if s["id"] == reuse["stage_id"])
            message = next(m for m in stage["messages"] if m["id"] == reuse["message_id"])
        else:
            project = engine.ensure_story_image(key=identity_key, name=name, source_asset_id=source,
                references=references, draft=draft, model_id=options["edit_model"], thumbnail=not bool(source),
                settings=dict(resolution="source" if source else "2", aspect_ratio="9:16" if source else options["aspect_ratio"].split(" ")[0]))
            stage = project["stages"][0]
            # Stable request IDs recover a child created before its episode link was saved.
            request_id = "story-image-" + digest(identity_key)[:32]
            message = next((m for m in stage["messages"] if m["request_id"] == request_id), None)
            if message is None:
                project, message_id = engine.begin_message(project["id"], stage["id"],
                    revision=stage["revision"], request_id=request_id, render_after_prompt=True)
                stage = project["stages"][0]
                message = next(m for m in stage["messages"] if m["id"] == message_id)
        link = dict(engine=engine.engine, project_id=project["id"], stage_id=stage["id"],
            message_id=message["id"], signature=signature, status=message["status"],
            initial_asset_id=(old.get("initial_asset_id") if old.get("project_id") == project["id"]
                and old.get("message_id") == message["id"] else holder.get("image_asset_id")),
            reference_asset_ids=[r["asset_id"] for r in engine.policy.render_inputs(stage)])
        if old.get("signature") and old["signature"] != signature and holder.get("image_asset_id") == old.get("output_asset_id"):
            holder["image_asset_id"] = None
        holder["story_v2_edit"] = link
        if message["status"] == "queued" and self._message_attempt(stage, message) is None:
            if old.get("project_id") != project["id"]:
                self.episodes.store.save(episode)  # Persist the child link BEFORE submitting any model work.
            self._prompt(engine, project["id"], stage["id"], message["id"])
        busy, error = self._record_result(holder, stage, message)
        if error:
            raise ValueError(name + " : " + error)
        return busy

    def advance(self, project, automatic):
        options = project["settings"]["images"]
        with self.episodes._lock:
            episode = self.episodes.store.get(project["episode_id"])
            selection = episode.get("story_v2_selection")
            if not selection:
                return False
            before = deepcopy(episode)
            batch = episode.get("reference_batch") or {}
            items = {i["reference_id"]:i for i in batch.get("items", [])} if batch.get("request_id") == selection["request_id"] else {}
            def source_ready(ref):
                item = items.get(ref["id"])
                return bool(ref.get("image_asset_id")) and (not item or item["status"] == "validated")
            busy = False
            try:
                for ref in episode["references"]:
                    state = ref.get("story_v2_state")
                    if not state or ref["id"] not in selection["ids"]:
                        continue
                    base = next(r for r in episode["references"] if r["id"] == state["base_id"])
                    if not source_ready(base):
                        continue
                    draft = ("Create one reference image of this same character. Change only this visual state: "
                        + ref["description"] + ". Preserve identity, species, rendering style and unchanged attributes. "
                        "The requested state replaces any conflicting earlier state. Single character, no text or comparison panel.")
                    busy |= self._advance_image(episode, ref, key=selection["request_id"]+ref["id"],
                        name=ref["name"], source=base["image_asset_id"], references=[], draft=draft,
                        options=options, automatic=automatic, force=True,
                        reuse=selection.get("reuse_edits", {}).get(ref["id"]))
                bases = [r for r in episode["references"] if not r.get("story_v2_state")]
                if options["thumbnail"] and bases and all(source_ready(r) for r in bases):
                    engine = self.engines[options["edit_engine"]]
                    if engine is None:
                        raise ValueError("Le moteur de miniature choisi est indisponible.")
                    # Main cast first, then a location and necessary props; pass actual images separately.
                    cast = [r for r in bases if r["kind"] == "character"]
                    others = [r for r in bases if r["kind"] != "character"]
                    limit = engine.policy.MAX_RENDER_IMAGES
                    chosen = (cast[:max(1, limit-1)] + others[:1] + cast[max(1, limit-1):] + others[1:])[:limit]
                    refs = [dict(asset_id=r["image_asset_id"], name=r["name"],
                        role="Character identity" if r["kind"] == "character" else "Setting" if r["kind"] == "location" else "Prop") for r in chosen]
                    thumb = episode.setdefault("story_v2_thumbnail", dict(name="Miniature", images=[], image_asset_id=None, revision=1))
                    draft = ("Compose an engaging story thumbnail, one readable scene, using the supplied character identities "
                        "and visual style. Choose the main dramatic situation; no collage, no duplicate characters. "
                        "Title to display exactly: " + project["script"]["title"] + ". Story: "
                        + " ".join(project["script"]["summary"]) + ". Use only characters whose reference is supplied.")
                    busy |= self._advance_image(episode, thumb, key=(selection["request_id"] if selection.get("thumbnail_retry") else "thumbnail"),
                        name="Miniature · " + project["script"]["title"], source=None, references=refs,
                        draft=draft, options=options, automatic=True, force=bool(selection.get("thumbnail_retry")),
                        reuse=selection.get("reuse_edits", {}).get("thumbnail"))
            finally:
                if episode != before:
                    self.episodes.store.save(episode)
            return busy
