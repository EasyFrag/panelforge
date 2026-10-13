"""Durable culinary projects with explicit image and video launch boundaries."""
from copy import deepcopy
from threading import Event, RLock, Thread
from panelforge.domain import cooking_recipes as policy


class RecipeConflict(ValueError):
    pass


class CookingRecipeService:
    def __init__(self, store, assets, images, planner, production, exporter=None):
        self.store, self.assets, self.images = store, assets, images
        self.planner, self.production = planner, production
        self.exporter = exporter
        self._lock, self._wake, self._stop = RLock(), Event(), Event()
        self._thread = None
        for p in store.list():
            if any(j["status"] in policy.ACTIVE for j in p["jobs"]):
                p["paused"] = True
                for job in p["jobs"]:
                    if job["status"] == "working":
                        # Inspect an external child before concluding it was interrupted.
                        if job.get("link") and job["kind"] in {"master", "image"}:
                            job["status"] = "waiting"
                        elif job["kind"] == "clip" and job.get("link", {}).get("factory_id"):
                            job["status"] = "queued"  # Explicit resume reuses the saved delivery.
                        else:
                            job.update(status="failed", error="Préparation interrompue. Relance explicitement cet élément.")
                self._save(p)

    def _save(self, p):
        p.update(version=p["version"] + 1, updated_at=policy.now())
        self.store.save(p)
        return p

    def _load(self, identity, version=None, editable=False):
        p = self.store.get(identity)
        if version is not None and p["version"] != version:
            raise RecipeConflict("La recette a changé. Actualise avant d’appliquer cette modification.")
        if editable and any(j["status"] in policy.ACTIVE for j in p["jobs"]):
            raise RecipeConflict("Attends la fin du lot ou abandonne ses étapes restantes avant de modifier la recette.")
        return p

    def _asset(self, asset_id):
        if not self.assets.get(asset_id).media_type.startswith("image/"):
            raise ValueError("Choisis une image.")
        self.images.dimensions(self.assets.read_bytes(asset_id))

    def list(self):
        with self._lock:
            return [dict(id=p["id"], name=p["name"], master_asset_id=p["master_asset_id"],
                         updated_at=p["updated_at"], shot_count=len(p["shots"])) for p in self.store.list()]

    def create(self, command, name, settings, master_asset_id=None):
        proposed = policy.new_project(command, name, settings, master_asset_id)
        with self._lock:
            try:
                existing = self.store.get(proposed["id"])
                if existing.get("creation_key") != proposed["creation_key"]:
                    raise RecipeConflict("Cette demande de création correspond à une autre recette.")
                return existing
            except FileNotFoundError:
                pass
            if master_asset_id:
                self._asset(master_asset_id)
                proposed["master_images"].append(dict(asset_id=master_asset_id, label="Image choisie"))
            return self._save(proposed)

    def update(self, identity, version, name, settings, shots=None):
        settings = policy.Settings.model_validate(settings).model_dump(mode="json")
        if not name.strip() or len(name) > 120:
            raise ValueError("Le nom doit contenir de 1 à 120 caractères.")
        if shots is not None:
            shots = policy.Breakdown.model_validate(dict(title=name, shots=shots)).model_dump()["shots"]
        with self._lock:
            p = self._load(identity, version, editable=True)
            if shots is not None and shots != p["shots"]:
                self._history(p)
                p["shots"] = shots
                p["approved"] = None
            if p["settings"] != settings:
                p["approved"] = None
            p.update(name=name.strip(), settings=settings)
            return self._save(p)

    def set_master(self, identity, version, asset_id=None, content=None):
        with self._lock:
            p = self._load(identity, version, editable=True)
            if content is not None:
                asset_id = self.assets.create(self.images.normalize_source(content), media_type="image/png").asset_id
            self._asset(asset_id)
            if p["master_asset_id"] != asset_id:
                p.update(master_asset_id=asset_id, approved=None)
            if not any(a["asset_id"] == asset_id for a in p["master_images"]):
                p["master_images"].append(dict(asset_id=asset_id, label="Image choisie"))
            return self._save(p)

    @staticmethod
    def _history(p):
        if p["shots"]:
            p["breakdown_history"].append(dict(name=p["name"], shots=deepcopy(p["shots"]), saved_at=policy.now()))

    def _selected_shots(self, p, ids):
        if not ids or len(ids) != len(set(ids)) or not set(ids) <= {s["id"] for s in p["shots"]}:
            raise ValueError("Choisis des plans distincts de ce découpage.")
        return [s for s in p["shots"] if s["id"] in ids]

    def _approval(self, p):
        return policy.digest(dict(master=p["master_asset_id"], settings=p["settings"], shots=p["shots"]))

    def approve(self, identity, version):
        with self._lock:
            p = self._load(identity, version, editable=True)
            if not p["master_asset_id"] or not p["shots"]:
                raise ValueError("Choisis le plat et prépare un découpage.")
            policy.Breakdown.model_validate(dict(title=p["name"], shots=p["shots"]))
            p["approved"] = self._approval(p)
            return self._save(p)

    def enqueue(self, identity, version, command, kind, ids=(), feedback=""):
        if kind not in {"plan", "master", "image", "clip"}:
            raise ValueError("Action inconnue.")
        signature = policy.digest(dict(kind=kind, ids=ids, feedback=feedback))
        with self._lock:
            p = self._load(identity)
            if command in p["commands"]:
                if p["commands"][command] != signature:
                    raise RecipeConflict("Cette commande correspond à une autre action.")
                return p
            p = self._load(identity, version, editable=True)
            if kind != "master" and not p["master_asset_id"]:
                raise ValueError("Choisis d’abord l’image du plat terminé.")
            if kind == "master" and (not p["settings"]["style_preset_id"] or not p["settings"]["intention"]):
                raise ValueError("Décris le plat et choisis son preset KREA2.")
            shots = self._selected_shots(p, ids) if kind in {"image", "clip"} else [None]
            if kind in {"image", "clip"} and p["approved"] != self._approval(p):
                raise ValueError("Accepte le découpage actuel avant la génération.")
            if kind == "clip":
                for shot in shots:
                    image = policy.selected_image(p, shot)
                    if not image or image["context_key"] != policy.image_key(p, shot):
                        raise ValueError(shot["title"] + " : choisis des images correspondant au plan actuel.")
                    if shot["mode"] == "endpoints" and not image.get("end_asset_id"):
                        raise ValueError(shot["title"] + " : image d’arrivée manquante.")
                    if any(c["status"] in {"queued", "preparation", "active"}
                           for c in p["media"].get(shot["id"], {}).get("clips", [])):
                        raise RecipeConflict(shot["title"] + " : un clip est déjà en préparation.")
            for shot in shots:
                job_id = policy.identity("job")
                snap = dict(id=p["id"], name=p["name"], settings=deepcopy(p["settings"]),
                            master_asset_id=p["master_asset_id"], shots=deepcopy(p["shots"]))
                job = dict(id=job_id, kind=kind, shot_id=shot["id"] if shot else None,
                           shot=deepcopy(shot), snapshot=snap, feedback=feedback, status="queued",
                           phase="start", outputs={}, link=None, error=None, created_at=policy.now())
                if shot:
                    holder = p["media"].setdefault(shot["id"], dict(images=[], clips=[], selected_image=None, selected_clip=None))
                    job["context_key"] = policy.image_key(p, shot)
                    if kind == "clip":
                        image = policy.selected_image(p, shot)
                        key = policy.clip_key(p, shot, image)
                        clip_id = policy.identity("clip")
                        entry = policy.factory_entry(p, shot, image, clip_id)
                        entry["config"]["intention"] += "\nCorrection pour cet essai : " + feedback if feedback else ""
                        job.update(clip_id=clip_id, entry=entry, context_key=key)
                        holder["clips"].append(dict(id=clip_id, context_key=key, image_id=image["id"],
                            factory_id=None, asset_id=None, status="queued", error=None, entry=deepcopy(entry)))
                p["jobs"].append(job)
            p["commands"][command] = signature
            p["paused"] = False
            self._save(p)
        self._wake.set()
        return p

    def choose(self, identity, version, shot_id, kind, attempt_id):
        with self._lock:
            p = self._load(identity, version, editable=True)
            shot = self._selected_shots(p, [shot_id])[0]
            if kind not in {"image", "clip"}:
                raise ValueError("Type d’essai inconnu.")
            holder = p["media"][shot_id]
            item = next((a for a in holder[kind + "s"] if a["id"] == attempt_id), None)
            if not item or (kind == "clip" and not item.get("asset_id")):
                raise ValueError("Choisis un essai terminé.")
            holder["selected_" + kind] = attempt_id
            return self._save(p)

    def pause(self, identity, paused=True, abandon=False):
        with self._lock:
            p = self._load(identity)
            p["paused"] = paused
            if abandon:
                for job in p["jobs"]:
                    if job["status"] in {"working", "waiting"}:
                        job["abandon_next"] = True
                    if job["status"] == "queued":
                        job.update(status="cancelled", error="Étape restante abandonnée.")
                        if job["kind"] == "clip":
                            clip = next(c for c in p["media"][job["shot_id"]]["clips"] if c["id"] == job["clip_id"])
                            clip.update(status="cancelled", error=job["error"])
                # Already submitted work remains tracked until it finishes.
            self._save(p)
        self._wake.set()
        return p

    def _checkpoint(self, identity, job_id, link):
        with self._lock:
            p = self._load(identity)
            job = next(j for j in p["jobs"] if j["id"] == job_id)
            job["link"] = deepcopy(link)
            if job["kind"] == "clip":
                clip = next(c for c in p["media"][job["shot_id"]]["clips"] if c["id"] == job["clip_id"])
                clip["factory_id"] = link["factory_id"]
            self._save(p)

    def _complete_image(self, p, job, result):
        role = job["phase"]
        job["outputs"][role] = dict(asset_id=result["asset_id"], prompt=result.get("prompt", ""),
                                      link=deepcopy(job["link"]), attempt_id=result.get("attempt_id"))
        if job["kind"] == "master":
            p["master_images"].append(dict(asset_id=result["asset_id"], label="Création KREA2", link=job["link"]))
            # A successful new candidate is selectable, never silently replaces the chosen dish.
            if not p["master_asset_id"]:
                p.update(master_asset_id=result["asset_id"], approved=None)
        elif role == "start" and job["shot"]["mode"] == "endpoints":
            if job.get("abandon_next"):
                job.update(status="cancelled", error="Image de départ conservée ; arrivée abandonnée.")
            else:
                job.update(phase="end", status="queued", link=None)
            return
        else:
            holder = p["media"][job["shot_id"]]
            attempt = dict(id=job["id"], context_key=job["context_key"], feedback=job["feedback"],
                           start_asset_id=job["outputs"]["start"]["asset_id"],
                           end_asset_id=job["outputs"].get("end", {}).get("asset_id"),
                           outputs=deepcopy(job["outputs"]))
            holder["images"].append(attempt)
            # An explicit regeneration retains history and selects its new complete image pair.
            holder["selected_image"] = attempt["id"]
        job.update(status="succeeded", finished_at=policy.now())

    def _refresh(self, p):
        before = deepcopy(p)
        for job in p["jobs"]:
            if job["status"] == "waiting" and job["kind"] in {"image", "master"}:
                try:
                    result = self.production.image_result(job["link"])
                    if result["status"] == "succeeded" and result.get("asset_id"):
                        self._complete_image(p, job, result)
                    elif result["status"] in {"failed", "cancelled", "interrupted", "created"}:
                        job.update(status="failed", error=result.get("error") or "Rendu interrompu.")
                except (ValueError, OSError, KeyError, StopIteration) as error:
                    job.update(status="failed", error=str(error))
        ids = [c["factory_id"] for h in p["media"].values() for c in h["clips"] if c.get("factory_id")]
        items = self.production.video_items(ids)
        for holder in p["media"].values():
            for clip in holder["clips"]:
                item = items.get(clip.get("factory_id"))
                if not item:
                    if clip.get("factory_id") and not clip.get("asset_id"):
                        clip.update(status="failed", error="Cette production n’est plus disponible dans l’usine. Tu peux lancer un nouvel essai.")
                    continue
                actual = item.get("launch_snapshot") or item.get("config", {})
                expected = clip["entry"]["config"]
                def source_signature(config):
                    return dict(intention=config.get("intention"), references=config.get("references"),
                        duration=config.get("render", {}).get("settings", {}).get("duration_seconds"),
                        ratio=config.get("render", {}).get("settings", {}).get("aspect_ratio"))
                clip["source_changed"] = source_signature(actual) != source_signature(expected)
                output = item["steps"]["video"].get("output", {})
                clip.update(status=item["status"], steps={k:v["status"] for k,v in item["steps"].items()},
                            error=next((v.get("error") for v in item["steps"].values() if v.get("error")), None))
                if item["steps"]["video"]["status"] == "succeeded" and output.get("asset_id"):
                    new = not clip.get("asset_id")
                    clip["asset_id"] = output["asset_id"]
                    if new and not holder.get("selected_clip"):
                        holder["selected_clip"] = clip["id"]
        if p != before:
            self._save(p)
        return p

    def get(self, identity):
        with self._lock:
            p = self._refresh(self._load(identity))
            return self.public(p)

    def public(self, p):
        value = deepcopy(p)
        value["active"] = any(j["status"] in policy.ACTIVE for j in p["jobs"])
        value["planned_duration"] = sum(s["duration"] for s in p["shots"])
        value["approved_current"] = bool(p["approved"] and p["approved"] == self._approval(p))
        for shot in value["shots"]:
            image = policy.selected_image(p, shot)
            shot["image_stale"] = bool(image and image["context_key"] != policy.image_key(p, shot))
            holder = p["media"].get(shot["id"], {})
            key = policy.clip_key(p, shot, image) if image else None
            for clip in value["media"].get(shot["id"], {}).get("clips", []):
                clip["stale"] = not image or shot["image_stale"] or clip["context_key"] != key or clip.get("source_changed", False)
            shot["image_ready"] = bool(image and not shot["image_stale"])
        value["jobs"] = [{k:deepcopy(v) for k,v in j.items() if k not in {"snapshot", "entry", "shot"}}
                         for j in p["jobs"]]
        return value

    def export_selection(self, identity, version, ids):
        with self._lock:
            p = self._refresh(self._load(identity))
            if p["version"] != version:
                raise RecipeConflict("Les résultats ont changé. Actualise avant l’export.")
            shots = self._selected_shots(p, ids)
            result = []
            for shot in shots:
                holder = p["media"].get(shot["id"], {})
                clip = next((c for c in holder.get("clips", []) if c["id"] == holder.get("selected_clip")), None)
                if not clip or not clip.get("asset_id"):
                    raise ValueError(shot["title"] + " : choisis un clip terminé.")
                image = policy.selected_image(p, shot)
                if not image or image["context_key"] != policy.image_key(p, shot) or clip["context_key"] != policy.clip_key(p, shot, image) or clip.get("source_changed"):
                    raise ValueError(shot["title"] + " : le clip correspond à une ancienne version du plan.")
                result.append(dict(index=p["shots"].index(shot)+1, title=shot["title"], asset_id=clip["asset_id"],
                                   duration=shot["duration"], shot_id=shot["id"], clip_id=clip["id"]))
            return dict(project_id=p["id"], name=p["name"], clips=result)

    def tick(self):
        task = None
        with self._lock:
            for p in self.store.list():
                p = self._refresh(p)
                if p["paused"] or any(j["status"] in {"working", "waiting"} for j in p["jobs"]):
                    continue
                job = next((j for j in p["jobs"] if j["status"] == "queued"), None)
                if job:
                    job["status"] = "working"
                    self._save(p)
                    task = (p["id"], deepcopy(job))
                    break
        if task is None:
            return False
        identity, job = task
        checkpoint = lambda link:self._checkpoint(identity, job["id"], link)
        try:
            if job["kind"] == "plan":
                result = self.planner.propose(job["snapshot"], job["feedback"])
                with self._lock:
                    p = self._load(identity)
                    self._history(p)
                    p.update(name=result["title"], shots=result["shots"], approved=None)
                    current = next(j for j in p["jobs"] if j["id"] == job["id"])
                    current["status"] = "succeeded"
                    self._save(p)
            elif job["kind"] == "clip":
                self.production.submit_clip(job["entry"], checkpoint)
                with self._lock:
                    p = self._load(identity)
                    next(j for j in p["jobs"] if j["id"] == job["id"])["status"] = "succeeded"
                    self._save(p)
            else:
                key = job["id"] + "-" + job["phase"]
                if job["kind"] == "master":
                    link = job.get("link") or self.production.prepare_master(job["snapshot"], key, job["feedback"])
                    checkpoint(link)
                    link = self.production.submit_master(link, job["snapshot"], checkpoint)
                else:
                    start = job["outputs"].get("start", {}).get("asset_id")
                    link = job.get("link") or self.production.prepare_image(job["snapshot"], job["shot"],
                        job["phase"], start, job["feedback"], key)
                    checkpoint(link)
                    link = self.production.submit_image(link, checkpoint)
                with self._lock:
                    p = self._load(identity)
                    current = next(j for j in p["jobs"] if j["id"] == job["id"])
                    current.update(status="waiting", link=deepcopy(link))
                    self._save(p)
        except Exception as error:
            with self._lock:
                p = self._load(identity)
                current = next(j for j in p["jobs"] if j["id"] == job["id"])
                current.update(status="failed", error=str(error)[:3000])
                if current.get("link") and current["kind"] in {"image", "master"}:
                    try:
                        result = self.production.image_result(current["link"])
                        if result["status"] not in {"failed", "cancelled", "interrupted", "created"}:
                            current.update(status="waiting", error=None)
                    except (ValueError, OSError, KeyError, StopIteration):
                        pass
                if current["kind"] == "clip":
                    clip = next(c for c in p["media"][current["shot_id"]]["clips"] if c["id"] == current["clip_id"])
                    clip.update(status="failed", error=current["error"])
                self._save(p)
        return True

    def start_worker(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = Thread(target=self._loop, daemon=True, name="cooking-recipes")
        self._thread.start()

    def stop_worker(self):
        self._stop.set(); self._wake.set()
        if self._thread:
            self._thread.join(timeout=2)

    def _loop(self):
        while not self._stop.is_set():
            try:
                self.tick()
            except Exception:
                # A missing external store must not kill the queue; no task is blindly retried.
                import logging
                logging.getLogger(__name__).exception("Recettes : suivi interrompu")
            self._wake.wait(2)
            self._wake.clear()
