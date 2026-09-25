"""Read-only production summaries and reversible library organization."""
from datetime import UTC, datetime
from threading import RLock

from panelforge.domain import long_stories as narrative
from panelforge.domain.episodes import effective_video_setup, fingerprint, scene_inputs, style_context
from panelforge.domain.story_library import LibraryConflict, episode_count, memberships, metadata_change

ACTIVE = {"running", "queued", "starting", "submitting", "receiving", "importing", "rendering", "pausing", "cancelling", "cancel_pending"}
FAILED = {"failed", "interrupted", "unconfirmed", "completed_with_errors"}


def state_of(value):
    state = getattr(value, "status", None)
    return getattr(state, "value", state) if state is not None else (value or {}).get("status")


def writing_progress(project):
    doc, flow, job = project.get("document", {}), project.get("workflow") or {}, project.get("job") or {}
    stages = dict(intention="done", story="pending", scenario="pending")
    if narrative.is_v2(project):
        status = narrative.status(project)
        approved = lambda key: flow.get("mode") != "manual" or flow.get("status") == "ready" or (
            bool(doc.get("reviews", {}).get(key, {}).get("source_hash")) and
            flow.get("approvals", {}).get(key) == doc["reviews"][key]["source_hash"])
        stages["story"] = "done" if status["outline_reviewed"] and approved("outline") else "planned" if doc.get("series_outline") else "pending"
        units = status["units"]
        stages["scenario"] = "done" if units and all(u["ready"] and approved(key) for key, u in units.items()) else (
            "planned" if any(u["written"] for u in units.values()) else "pending")
    else:
        stages["story"] = "done" if doc.get("series_outline") or doc.get("scenario") else "approval" if doc.get("concepts") else "pending"
        units = (doc.get("series_outline") or {}).get("episodes", [])
        complete = all(doc.get("episode_scenarios", {}).get(u["id"]) for u in units) if units else bool(doc.get("scenario"))
        stages["scenario"] = "done" if complete else "pending"
    target = "story" if flow.get("wait_target") == "outline" or stages["story"] != "done" else "scenario"
    if flow.get("status") == "awaiting_author":
        stages[target] = "approval"
    elif flow.get("status") == "blocked":
        stages[target] = "attention"
    if job.get("operation") != "discuss":
        if state_of(job) in ACTIVE or flow.get("status") == "running":
            stages[target] = "running" if state_of(job) == "running" else "planned"
        elif state_of(job) in FAILED:
            stages[target] = "error"
    return stages


class StoryLibraryService:
    def __init__(self, stories, episodes=None):
        self.stories, self.episodes = stories, episodes
        self._lock = RLock()

    def _snapshot(self):
        stories = self.stories.store.catalog()
        episodes = self.episodes.store.catalog() if self.episodes else dict(items=[], unreadable=0)
        dlss = getattr(self.episodes, "dlss", None)
        # Use repositories only: service.get/list can reconcile or wake workers.
        jobs = dlss.jobs.list() if dlss else []
        return dict(projects=stories["items"], episodes=episodes["items"], dlss=jobs,
                    unreadable=stories["unreadable"] + episodes["unreadable"], renders={}, images={})

    def _render(self, key, snapshot):
        if key not in snapshot["renders"]:
            snapshot["renders"][key] = self.episodes.render.projects.get(key)
        return snapshot["renders"][key]

    def _busy(self, project, records, snapshot):
        if project["project_id"] in getattr(self.stories, "_active", {}) or state_of(project.get("job")) in ACTIVE or state_of(project.get("workflow")) in ACTIVE:
            return True
        for identity in getattr(getattr(self.stories, "followups", None), "_active", {}):
            try:
                if self.stories.store.get_followup(identity)["source_story_id"] == project["project_id"]:
                    return True
            except (OSError, ValueError):
                return True
        render_ids, image_ids, qwen_ids = set(), set(), set()
        for value in records:
            for name in ("reference_batch", "video_chain"):
                if state_of(value.get(name)) in ACTIVE:
                    return True
            if state_of((value.get("localization") or {}).get("job")) in ACTIVE:
                return True
            for item in [*value.get("references", []), *value.get("scenes", [])]:
                if state_of(item.get("job")) in ACTIVE:
                    return True
                if item.get("krea_project_id"):
                    image_ids.add(item["krea_project_id"])
                if item.get("qwen_variant"):
                    qwen_ids.add(item["qwen_variant"]["project_id"])
                for prep in item.get("preparations", []):
                    if prep.get("render_project_id"):
                        render_ids.add(prep["render_project_id"])
        for key in render_ids:
            try:
                if any(state_of(a) in ACTIVE for a in self._render(key, snapshot).attempts):
                    return True
            except FileNotFoundError:
                continue
        for key in image_ids:
            try:
                if key not in snapshot["images"]:
                    snapshot["images"][key] = self.episodes.krea.projects.get(key)
                if any(state_of(a) in ACTIVE for a in snapshot["images"][key].attempts):
                    return True
            except FileNotFoundError:
                continue
        if getattr(self.episodes, "qwen_edit", None):
            for key in qwen_ids:
                try:
                    value = self.episodes.qwen_edit.projects.get(key)
                    if any(state_of(a) in ACTIVE for stage in value["stages"] for a in stage["attempts"]):
                        return True
                except FileNotFoundError:
                    continue
        return any(state_of(job) in ACTIVE and job.get("snapshot", {}).get("owner_id") in render_ids | image_ids | qwen_ids for job in snapshot["dlss"])

    @staticmethod
    def _source_hash(project, unit_id):
        doc = project.get("document", {})
        scenario = narrative.fabrication_scenario(project, episode_id=unit_id, require_review=False) if narrative.is_v2(project) else (
            doc.get("episode_scenarios", {}).get(unit_id) if unit_id else doc.get("scenario"))
        return fingerprint([unit_id, scenario] if unit_id else scenario) if scenario else None

    def _fabrication(self, project, value, snapshot, expected_hash):
        result = dict(references=0, reference_total=0, prompts=0, videos=0, dlss=0,
                      scenes=len(value.get("scenes", [])), stale=0, errors=0, active=False, queued=False)
        localized = value.get("localization")
        changed = bool(expected_hash and value.get("source_hash") != expected_hash) if not localized else False
        if not localized:
            changed |= bool(project.get("long_status", {}).get("units", {}).get(value.get("series_episode_id"), {}).get("stale"))
        for ref in value.get("references", []):
            if ref.get("continuity_archived"):
                continue
            result["reference_total"] += 1
            stale = ref.get("continuity_image_stale") or (ref.get("image_style") is not None and fingerprint(ref["image_style"]) != fingerprint(style_context(value)))
            result["references"] += bool(ref.get("image_asset_id") and not stale)
        for scene in value.get("scenes", []):
            prep = (scene.get("preparations") or [None])[-1]
            if not prep:
                continue
            prompt_states = set((prep.get("prompt_stages") or {}).values())
            result["active"] |= bool(prompt_states & (ACTIVE - {"queued"})) or (not prompt_states and state_of(scene.get("job")) == "running")
            result["queued"] |= "queued" in prompt_states
            stale = changed
            if localized:
                stale |= (scene.get("localization") or {}).get("status") != "ready"
            else:
                try:
                    stale |= prep.get("input_hash") != fingerprint(scene_inputs(value, scene))
                except (ValueError, KeyError):
                    stale = True
            ready = prep.get("status") == "ready" and not stale
            result["prompts"] += ready
            result["errors"] += state_of(scene.get("job")) in FAILED or prep.get("status") in FAILED
            if not prep.get("render_project_id"):
                result["stale"] += bool(stale)
                continue
            render = self._render(prep["render_project_id"], snapshot)
            attempts = [a for a in render.attempts if not a.dlss]
            attempt = attempts[-1] if attempts else None
            if attempt:
                result["active"] |= state_of(attempt) in ACTIVE - {"queued"}
                result["queued"] |= state_of(attempt) == "queued"
                result["errors"] += state_of(attempt) in FAILED
                setup = effective_video_setup(value, scene)
                settings_changed = any(getattr(attempt.settings, key, object()) != setting for key, setting in setup.get("settings", {}).items() if key in {"aspect_ratio", "megapixels", "duration_seconds", "steps"})
                video = ready and not settings_changed and state_of(attempt) == "succeeded" and bool(attempt.output_asset_id) and attempt.prompt == render.current_prompt
                result["videos"] += bool(video)
                result["dlss"] += bool(video and any(a.dlss and a.dlss.root_attempt_id == attempt.attempt_id and state_of(a) == "succeeded" and a.output_asset_id for a in render.attempts))
                stale |= state_of(attempt) == "succeeded" and (settings_changed or attempt.prompt != render.current_prompt)
            result["stale"] += bool(stale)
        return result

    @staticmethod
    def _character_previews(values):
        previews, names, assets = [], set(), set()
        for value in sorted(values, key=lambda v: v.get("updated_at", ""), reverse=True):
            people = {c["id"]: c["name"] for c in value.get("scenario", {}).get("characters", [])}
            # Prefer the identity reference over another state of the same person.
            for ref in sorted(value.get("references", []), key=lambda r: bool(r.get("continuity_state_id"))):
                asset = ref.get("image_asset_id")
                if ref.get("kind") != "character" or ref.get("continuity_archived") or not asset:
                    continue
                name = people.get(ref.get("source_id")) or ref.get("name", "Personnage")
                identity = " ".join(name.casefold().split())
                if identity in names or asset in assets:
                    continue
                previews.append(dict(name=name, asset_id=asset))
                names.add(identity)
                assets.add(asset)
                if len(previews) == 3:
                    return previews
        return previews

    def _production(self, project, records, snapshot):
        doc = project.get("document", {})
        units = (doc.get("series_outline") or {}).get("episodes", [])
        expected = [u["id"] for u in units] or [None]
        known_scenes = sum(len(s.get("scenes", [])) for s in doc.get("episode_scenarios", {}).values()) if units else len((doc.get("scenario") or {}).get("scenes", []))
        hashes = {key: self._source_hash(project, key) for key in expected}
        base = []
        for key in expected:
            candidates = [r for r in records if not r.get("localization") and r.get("series_episode_id") == key]
            if candidates:
                base.append(max(candidates, key=lambda r: (r.get("source_hash") == hashes[key], r.get("created_at", r.get("updated_at", "")), r["episode_id"])))
        language = project.get("dialogue_language", "French")
        chosen = {language: base}
        for original in base:
            versions = {}
            for record in records:
                info = record.get("localization") or {}
                if info.get("source_episode_id") != original["episode_id"]:
                    continue
                key = info["language"]
                if key == language:
                    continue
                if key not in versions or record.get("created_at", "") > versions[key].get("created_at", ""):
                    versions[key] = record
            for key, record in versions.items():
                chosen.setdefault(key, []).append(record)
        variants = []
        for lang, values in chosen.items():
            totals = dict(references=0, reference_total=0, prompts=0, videos=0, dlss=0, scenes=0, stale=0, errors=0, active=False, queued=False)
            for value in values:
                one = self._fabrication(project, value, snapshot, hashes.get(value.get("series_episode_id")))
                for key in totals:
                    totals[key] = totals[key] or one[key] if key in {"active", "queued"} else totals[key] + one[key]
            totals["scenes"] = max(known_scenes, totals["scenes"])
            totals["complete_units"] = len(values) == len(expected)
            variants.append(dict(language=lang, counts=totals, fabrication_ids=[v["episode_id"] for v in values],
                                 characters=self._character_previews(values)))
        return variants

    def view(self, snapshot=None):
        snapshot = snapshot or self._snapshot()
        metadata = self.stories.store.library_metadata()
        projects = {p["project_id"]: p for p in snapshot["projects"]}
        links = memberships(snapshot["projects"], metadata)
        groups = {}
        for key, raw in projects.items():
            group_id, number = links[key]
            prefs = metadata["groups"].get(group_id, {})
            group = groups.setdefault(group_id, dict(id=group_id, title=prefs.get("title") or projects.get(group_id, raw)["title"],
                favorite=prefs.get("favorite", False), items=[]))
            item = dict(project_id=key, title=raw["title"], episode_number=number, episode_count=episode_count(raw),
                updated_at=raw.get("updated_at", ""), trashed=metadata["projects"].get(key, {}).get("trashed", False),
                active=False, progress_error=None, variants=[])
            records = [r for r in snapshot["episodes"] if r.get("story_id") == key]
            item["last_activity_at"] = max([raw.get("updated_at", ""), *(r.get("updated_at", "") for r in records)])
            activity_known = False
            try:
                project = self.stories._normalize(raw)
                item["stages"] = writing_progress(project)
                item["active"] = self._busy(project, records, snapshot)
                activity_known = True
                item["variants"] = self._production(project, records, snapshot)
                counts = item["variants"][0]["counts"]
                ready_refs = bool(counts["complete_units"] and counts["reference_total"] and counts["references"] == counts["reference_total"])
                item["stages"]["references"] = "done" if ready_refs else "running" if any(state_of(r.get("reference_batch")) in ACTIVE for r in records) else "pending"
                done = bool(counts["complete_units"] and counts["scenes"] and counts["videos"] == counts["scenes"])
                item["stages"]["videos"] = "done" if done else "error" if counts["errors"] else "attention" if counts["stale"] else "running" if counts["active"] else "planned" if counts["queued"] or any(state_of(r.get("video_chain")) in ACTIVE for r in records) else "pending"
                item["completed"] = all(value == "done" for value in item["stages"].values())
            except (OSError, ValueError, KeyError, TypeError) as error:
                item.update(stages=dict(intention="done", story="attention", scenario="attention", references="attention", videos="attention"),
                            completed=False, active=item["active"] if activity_known else True, progress_error=f"Avancement indisponible : {error}")
            group["items"].append(item)
        for group in groups.values():
            group["items"].sort(key=lambda item: (item["episode_number"], item["updated_at"], item["project_id"]))
        result = sorted(groups.values(), key=lambda group: (not group["favorite"], group["title"].casefold()))
        return dict(revision=metadata["revision"], groups=result, unreadable=snapshot["unreadable"], generated_at=datetime.now(UTC).isoformat())

    def update(self, kind, target, *, expected_revision, **values):
        with self._lock:
            snapshot = self._snapshot()
            current = self.stories.store.library_metadata()
            if current["revision"] != expected_revision:
                raise LibraryConflict("La bibliothèque a changé. Actualise-la avant de réessayer.")
            if kind == "project" and values.get("trashed"):
                item = next((p for p in snapshot["projects"] if p["project_id"] == target), None)
                if item is None:
                    raise FileNotFoundError(target)
                records = [r for r in snapshot["episodes"] if r.get("story_id") == target]
                try:
                    busy = self._busy(item, records, snapshot)
                except (OSError, ValueError, KeyError):
                    raise LibraryConflict("L’activité de cette histoire est indisponible ; son retrait est suspendu.")
                if busy:
                    raise LibraryConflict("Un traitement est en cours pour cette histoire. Mets-le en pause avant de la retirer.")
            value = metadata_change(current, snapshot["projects"], kind=kind, target=target, values=values)
            self.stories.store.save_library_metadata(value, expected_revision)
            return self.view(snapshot)
