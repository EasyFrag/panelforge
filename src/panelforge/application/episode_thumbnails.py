"""Reusable series artwork and independent episode PNGs, using the existing Qwen queue.

No writer/prompt/video document is mutated. Reads reconcile persisted Qwen attempts;
reopening the workshop after a restart finishes lettering without another GPU job.
"""
from copy import deepcopy
from datetime import UTC, datetime
from threading import RLock
from uuid import uuid4

from panelforge.domain.episode_thumbnails import (
    ACTIVE, GRID_LAYOUT, MAX_RENDER_IMAGES, ROLE_INSTRUCTIONS, cover_format, ThumbnailConflict, assign_reference_roles, composition_prompt, default_references,
    badge_geometry, displayed_template_id, editorial_context, reference_choices, template_usage, validate_options,
)
from panelforge.domain.qwen_edit import QwenEditSettings


def _now():
    return datetime.now(UTC).isoformat()


class EpisodeThumbnailService:
    def __init__(self, *, store, stories, episodes, assets, images, qwen=None):
        self.store, self.stories, self.episodes = store, stories, episodes
        self.assets, self.images, self.qwen = assets, images, qwen
        self._lock = RLock()

    def _context(self, identity):
        episode = self.episodes.get(identity)
        context = editorial_context(episode, self.stories.catalog()["items"], self.stories.library_metadata())
        return episode, context

    @staticmethod
    def _save_record(index, identity, record):
        record["revision"] = index["episodes"].get(identity, {}).get("revision", 0) + 1
        record["updated_at"] = _now()
        index["episodes"][identity] = record

    def _refresh(self, index, identity):
        record = index["episodes"].get(identity)
        if not record or record["status"] not in ACTIVE:
            return
        before = deepcopy(record)
        template = index["templates"][record["template_id"]]
        try:
            if template["status"] in ACTIVE:
                if not self.qwen:
                    raise ValueError("Qwen n’est pas disponible pour retrouver cette génération.")
                project = self.qwen.get(template["qwen_project_id"])
                stage = next(s for s in project["stages"] if s["id"] == template["qwen_stage_id"])
                attempt = next((a for a in stage["attempts"] if a["id"] == template.get("qwen_attempt_id")
                                or a["request_id"] == template.get("qwen_request_id")), None)
                if attempt is None:
                    template.update(status="failed", error="Préparation interrompue avant la mise en file. Relance la miniature.")
                    raise ValueError(template["error"])
                template["qwen_attempt_id"] = attempt["id"]
                if attempt["status"] == "succeeded":
                    if not attempt.get("output_asset_id"):
                        raise ValueError("Le rendu Qwen est terminé sans image.")
                    template.update(status="ready", asset_id=attempt["output_asset_id"], error=None)
                elif attempt["status"] in {"failed", "cancelled", "interrupted", "unconfirmed"}:
                    template.update(status="failed", error=attempt.get("error") or "Génération Qwen interrompue.")
                else:
                    template["status"] = "queued" if attempt["status"] == "queued" else "running"
            if template["status"] == "failed":
                record.update(status="failed", error=template.get("error") or "Le modèle de miniature a échoué.")
            elif template["status"] == "ready":
                png = self.images.render(self.assets.read_bytes(template["asset_id"]), title=template["title"],
                    number=record["number"], title_mode=template["title_mode"], layout=template["layout"],
                    title_style=template.get("title_style", "pop"), badge_position=record.get("badge_position"))
                asset = self.assets.create(png, media_type="image/png")
                record.update(status="ready", asset_id=asset.asset_id, error=None,
                              title=template["title"], asset_number=record["number"], asset_title=template["title"],
                              asset_format=cover_format(template["layout"]), asset_template_id=template["id"], completed_at=_now())
            else:
                record.update(status=template["status"], error=None)
        except Exception as error:
            # A cover failure is visible locally and never poisons scene production.
            record.update(status="failed", error=str(error) or type(error).__name__)
        if template["status"] == "failed":
            previous_id = template.get("previous_template_id")
            if previous_id and index["series"].get(template["group_id"]) == template["id"]:
                index["series"][template["group_id"]] = previous_id
        if record != before:
            self._save_record(index, identity, record)
            self.store.save(index)

    def _view(self, index, identity, episode, context):
        record = deepcopy(index["episodes"].get(identity) or dict(
            revision=0, status="missing", asset_id=None, error=None, number=context["number"], title=context["title"]))
        series_id = index["series"].get(context["group_id"])
        template = index["templates"].get(record.get("template_id") or series_id)
        if not record["revision"] and template:
            record["title"] = template["title"]
        choices = reference_choices(episode)
        return dict(**record, episode_id=identity, group_id=context["group_id"],
            series_template_id=series_id, template=deepcopy(template),
            badge=badge_geometry(template["layout"], record.get("badge_position")) if template and record["status"] == "ready" else None,
            output_format=cover_format(template["layout"] if template else GRID_LAYOUT),
            references=choices, default_reference_ids=default_references(choices), max_references=MAX_RENDER_IMAGES, qwen_available=self.qwen is not None,
            templates=[dict(id=t["id"], title=t["title"], title_mode=t["title_mode"], asset_id=t["asset_id"],
                            created_at=t["created_at"], title_style=t.get("title_style", "pop"), output_format=cover_format(t["layout"]),
                            group_id=t["group_id"], revision=t.get("revision", 0), archived_at=t.get("archived_at"),
                            **template_usage(index, t["id"])) for t in sorted(index["templates"].values(), key=lambda t: t["created_at"], reverse=True) if t["status"] == "ready"])

    def get(self, identity):
        episode, context = self._context(identity)
        with self._lock:
            index = self.store.load()
            self._refresh(index, identity)
            return self._view(index, identity, episode, context)

    def prepare(self, identity, *, request_id, expected_revision=None, source="series", template_id=None,
                title=None, number=None, title_mode="artwork", reference_ids=None, direction="", content=None,
                replace=False, reference_roles=None, title_style="pop"):
        episode, context = self._context(identity)
        with self._lock:
            index = self.store.load()
            self._refresh(index, identity)
            previous = index["episodes"].get(identity, {})
            if previous.get("request_id") == request_id or (not replace and previous.get("asset_id")):
                return self._view(index, identity, episode, context)
            if expected_revision is not None and previous.get("revision", 0) != expected_revision:
                raise ThumbnailConflict("La miniature a changé. Actualise-la avant de modifier le modèle.")
            if previous.get("status") in ACTIVE:
                if not replace:
                    return self._view(index, identity, episode, context)
                raise ThumbnailConflict("La miniature est déjà en cours. Attends la fin du rendu.")
            if source not in {"series", "template", "generate", "upload"}:
                raise ValueError("Source de modèle inconnue.")
            if source == "upload" and not content:
                raise ValueError("Choisis l’image du modèle à importer.")
            if source != "upload" and content is not None:
                raise ValueError("Une image importée exige le mode Importer.")
            candidate = (template_id if source == "template" else
                         index["series"].get(context["group_id"]) if source == "series" else None)
            template = index["templates"].get(candidate)
            if template and template.get("archived_at"):
                raise ThumbnailConflict("Ce modèle est dans la corbeille. Restaure-le avant de l’utiliser.")
            if source == "template" and (not template or template["status"] != "ready"):
                raise ValueError("Choisis un modèle terminé.")
            # Rebuilding the title on a ready artwork requires an explicit new Qwen composition.
            if template and template["status"] != "failed":
                if title is not None and title.strip() != template["title"]:
                    raise ValueError("Ce titre appartient au modèle. Choisis Nouveau modèle Qwen pour le changer.")
                title, title_mode = template["title"], template["title_mode"]
                title_style = template.get("title_style", "pop")
            else:
                template = None
                title = title if title is not None else previous.get("title", context["title"])
            number = number if number is not None else previous.get("number", context["number"])
            validate_options(title, number, title_mode, direction, title_style)
            choices = reference_choices(episode)
            ids = reference_ids if reference_ids is not None else default_references(choices)
            if not isinstance(ids, list) or len(ids) > MAX_RENDER_IMAGES or len(ids) != len(set(ids)):
                raise ValueError(f"Choisis au maximum {MAX_RENDER_IMAGES} références distinctes.")
            by_id = {r["id"]: r for r in choices}
            if any(r not in by_id for r in ids):
                raise ThumbnailConflict("Une référence a changé. Rouvre les réglages de miniature.")
            references = assign_reference_roles([by_id[key] for key in ids], reference_roles)
            if template is None and source != "upload" and (not self.qwen or not references):
                raise ValueError("Prépare les images de référence puis utilise Qwen, ou importe un modèle.")
            preference = index.get("badge_positions", {}).get(context["group_id"], {})
            position = (previous.get("badge_position") if candidate and previous.get("template_id") == candidate
                        else preference.get("position") if preference.get("template_id") == candidate else None)
            record = dict(revision=previous.get("revision", 0), status="queued", title=title.strip(), number=number,
                request_id=request_id, template_id=None, asset_id=previous.get("asset_id"), error=None,
                asset_number=previous.get("asset_number", previous.get("number")),
                asset_title=previous.get("asset_title", previous.get("title")),
                asset_format=deepcopy(previous.get("asset_format")), asset_template_id=displayed_template_id(previous),
                badge_position=deepcopy(position),
                history=deepcopy(previous.get("history", [])))
            if previous.get("asset_id"):
                record["history"].append(self._history_entry(previous))
            if template is None:
                template = dict(id=f"cover-{uuid4().hex}", group_id=context["group_id"], title=title.strip(),
                    title_mode=title_mode, title_style=title_style, layout=GRID_LAYOUT,
                    font="BarlowCondensed-Black.ttf" if title_style == "cinema" else "Outfit.ttf", font_weight=900,
                    created_at=_now(), status="queued", asset_id=None, error=None,
                    reference_ids=ids, reference_roles={r["id"]: r["placement"] for r in references}, references=references, direction=direction.strip(), source=source,
                    previous_template_id=index["series"].get(context["group_id"]))
                index["templates"][template["id"]] = template
                # Persist the project and attempt identities before enqueue: a restart cannot duplicate a job.
                try:
                    if source == "upload":
                        asset = self.assets.create(self.images.normalize(content), media_type="image/png")
                        template.update(status="ready", asset_id=asset.asset_id)
                    else:
                        self._queue_template(index, identity, record, template, references)
                except Exception as error:
                    template.update(status="failed", error=str(error) or type(error).__name__)
            record["template_id"] = template["id"]
            index["series"][context["group_id"]] = template["id"]
            self._save_record(index, identity, record)
            self.store.save(index)
            self._refresh(index, identity)
            return self._view(index, identity, episode, context)

    @staticmethod
    def _history_entry(record):
        return dict(asset_id=record.get("asset_id"), template_id=displayed_template_id(record),
                    number=record.get("asset_number", record.get("number")),
                    title=record.get("asset_title", record.get("title")),
                    asset_format=deepcopy(record.get("asset_format")),
                    badge_position=deepcopy(record.get("badge_position")), completed_at=record.get("completed_at"))

    @staticmethod
    def _badge_record(index, identity, expected_revision):
        record = index["episodes"].get(identity)
        if not record or record["status"] != "ready" or not record.get("asset_id"):
            raise ThumbnailConflict("Attends une miniature terminée pour déplacer son bandeau.")
        if record["revision"] != expected_revision:
            raise ThumbnailConflict("La miniature a changé. Rouvre le réglage du bandeau.")
        template = index["templates"][record["template_id"]]
        return record, template

    def badge_preview(self, identity, *, part, expected_revision):
        self._context(identity)
        with self._lock:
            index = self.store.load()
            record, template = self._badge_record(index, identity, expected_revision)
            options = dict(number=record["number"], layout=template["layout"], title_style=template.get("title_style", "pop"))
            if part == "badge":
                return self.images.badge(**options)
            if part != "background":
                raise ValueError("Aperçu de bandeau inconnu.")
            # Always use the original artwork, never a PNG with an old badge baked in.
            return self.images.render(self.assets.read_bytes(template["asset_id"]), title=template["title"],
                                      title_mode=template["title_mode"], include_badge=False, **options)

    def reposition_badge(self, identity, *, request_id, expected_revision, position, remember_series=False):
        episode, context = self._context(identity)
        if type(remember_series) is not bool:
            raise ValueError("Le choix de mémorisation doit être un booléen.")
        with self._lock:
            index = self.store.load()
            if index["episodes"].get(identity, {}).get("badge_request_id") == request_id:
                return self._view(index, identity, episode, context)
            record, template = self._badge_record(index, identity, expected_revision)
            badge_geometry(template["layout"], position)
            png = self.images.render(self.assets.read_bytes(template["asset_id"]), title=template["title"],
                number=record["number"], title_mode=template["title_mode"], layout=template["layout"],
                title_style=template.get("title_style", "pop"), badge_position=position)
            asset = self.assets.create(png, media_type="image/png")
            record.setdefault("history", []).append(self._history_entry(record))
            record.update(asset_id=asset.asset_id, badge_position=deepcopy(position), badge_request_id=request_id,
                          asset_template_id=template["id"], asset_format=cover_format(template["layout"]), completed_at=_now())
            if remember_series:
                index.setdefault("badge_positions", {})[context["group_id"]] = dict(template_id=template["id"], position=deepcopy(position))
            self._save_record(index, identity, record)
            self.store.save(index)
            return self._view(index, identity, episode, context)

    def archive_template(self, identity, template_id, *, archived, expected_revision):
        episode, context = self._context(identity)
        if type(archived) is not bool:
            raise ValueError("Le choix de corbeille doit être un booléen.")
        with self._lock:
            index = self.store.load()
            template = index["templates"][template_id]
            if template.get("revision", 0) != expected_revision:
                raise ThumbnailConflict("Ce modèle a changé. Actualise la galerie.")
            if archived and (template["status"] != "ready" or not template_usage(index, template_id)["can_archive"]):
                raise ThumbnailConflict("Ce modèle est utilisé par une série, un épisode ou un traitement en cours.")
            template.update(archived_at=_now() if archived else None, revision=template.get("revision", 0) + 1)
            # Soft deletion preserves assets and historical covers, including Qwen source references.
            self.store.save(index)
            return self._view(index, identity, episode, context)

    def _queue_template(self, index, identity, record, template, references):
        project = self.qwen.create(name=("Miniature · " + template["title"])[:120], composition=True)
        stage = project["stages"][0]
        for ref in references:
            project = self.qwen.add_reference(project["id"], stage["id"], revision=stage["revision"],
                name=ref["name"], usage="render", role=ROLE_INSTRUCTIONS[ref["placement"]],
                content=self.assets.read_bytes(ref["asset_id"]))
            stage = project["stages"][0]
        prompt = composition_prompt(template["title"], template["title_mode"], references, template["direction"], template.get("title_style", "pop"))
        project = self.qwen.update(project["id"], stage["id"], revision=stage["revision"], changes=dict(
            settings=QwenEditSettings(resolution="2", aspect_ratio=cover_format(template["layout"])["aspect_ratio"], reuse_seed=False).record(), prompt=prompt))
        stage = project["stages"][0]
        template.update(qwen_project_id=project["id"], qwen_stage_id=stage["id"], qwen_request_id=template["id"])
        # If enqueue is interrupted, _refresh can locate the attempt by request ID.
        template["qwen_attempt_id"] = None
        record["template_id"] = template["id"]
        index["series"][template["group_id"]] = template["id"]
        self._save_record(index, identity, record)
        self.store.save(index)
        project = self.qwen.queue_attempt(project["id"], stage["id"], revision=stage["revision"], request_id=template["id"])
        template["qwen_attempt_id"] = next(a["id"] for a in project["stages"][0]["attempts"] if a["request_id"] == template["id"])
