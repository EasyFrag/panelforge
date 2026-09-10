"""Attach shared post-processing results to existing workshops without replaying generation."""

from dataclasses import asdict, replace

from panelforge.domain.dlss import DlssResult
from panelforge.domain.krea2_edit import Krea2EditUpscale, Krea2EditAttemptStatus
from panelforge.domain.krea2_assisted import Krea2AssistedAttemptStatus
from panelforge.domain.h3_render import H3RenderAttemptStatus, H3RenderKeyframe


class DlssCandidates:
    def __init__(self, *, edit, assisted, h3):
        self.services = {"edit": edit, "assisted": assisted, "h3": h3, "ref2v": h3}

    def _service(self, owner):
        service = self.services.get(owner)
        if service is None:
            raise ValueError("Atelier DLSS indisponible.")
        return service

    def _get(self, service, owner, identifier):
        return (service.sources if owner == "edit" else service.projects).get(identifier)

    def prepare(self, owner, owner_id, attempt_id, settings):
        service = self._service(owner)
        with service._lock:
            project = self._get(service, owner, owner_id)
            if owner == "edit":
                service._require_editable(project)
            attempt = next((a for a in project.attempts if a.attempt_id == attempt_id), None)
            if attempt is None or attempt.status.value != "succeeded" or not attempt.output_asset_id:
                raise ValueError("Choisis un résultat réussi à améliorer.")
            if attempt.dlss:
                # Another setting is compared from the same root, never a succession of DLSS passes.
                attempt = next(a for a in project.attempts if a.attempt_id == attempt.dlss.root_attempt_id)
            if owner in {"h3", "ref2v"}:
                is_ref = project.input_mode.value == "ref2va"
                if (owner == "ref2v") != is_ref:
                    raise ValueError("La vidéo n’appartient pas à ce mode de rendu.")
            if settings.size == "source" and owner != "edit":
                raise ValueError("La taille source est réservée à l’atelier Edit.")
            if owner in {"edit", "assisted"} and (settings.interpolate or settings.hdr):
                raise ValueError("Ces options sont réservées à la vidéo.")
            snapshot = {"owner": owner, "owner_id": owner_id, "parent_attempt_id": attempt.attempt_id,
                        "root_attempt_id": attempt.attempt_id, "input_asset_id": attempt.output_asset_id,
                        "media_type": "video/mp4" if owner in {"h3", "ref2v"} else "image/png"}
            if owner == "edit":
                original = attempt
                while original.kind != "generation":
                    original_id = original.upscale.original_attempt_id if original.upscale else original.retouch.original_attempt_id
                    original = next(a for a in project.attempts if a.attempt_id == original_id)
                mask = (attempt.retouch or attempt.upscale) if settings.size == "source" else None
                snapshot.update(original_attempt_id=original.attempt_id, source_asset_id=project.source_asset_id,
                                restart_count=project.restart_count, mask_asset_id=mask.mask_asset_id if mask else None,
                                harmonize=mask.harmonize if mask else False, harmonize_strength=mask.harmonize_strength if mask else 100)
                if settings.size == "source":
                    snapshot["input_asset_id"] = original.output_asset_id
            if owner in {"h3", "ref2v"}:
                snapshot["keyframe_timestamps_ms"] = list(attempt.keyframe_timestamps_ms)
                snapshot["generation_recipe"] = asdict(attempt.recipe) if attempt.recipe else None
                snapshot["generation_bunny"] = asdict(attempt.bunny) if attempt.bunny else None
                snapshot["generation_video_loras"] = asdict(attempt.video_loras) if attempt.video_loras is not None else None
                snapshot["generation_checkpoint"] = attempt.checkpoint
                snapshot["generation_model_loading"] = asdict(attempt.model_loading) if attempt.model_loading else None
            return snapshot

    def validate_current(self, snapshot):
        service = self._service(snapshot["owner"])
        with service._lock:
            project = self._get(service, snapshot["owner"], snapshot["owner_id"])
            if snapshot["owner"] == "edit":
                service._require_editable(project)
                if project.restart_count != snapshot["restart_count"] or project.source_asset_id != snapshot["source_asset_id"]:
                    raise ValueError("L’étape a été recommencée pendant l’upscale. Le fichier DLSS reste téléchargeable.")
            if not any(a.attempt_id == snapshot["parent_attempt_id"] for a in project.attempts):
                raise ValueError("L’essai d’origine n’est plus dans cet atelier.")

    def compose(self, snapshot, enhanced, assets):
        if not snapshot.get("mask_asset_id"):
            return enhanced
        service = self._service("edit")
        return service.retouch_compositor.compose(
            assets.read_bytes(snapshot["source_asset_id"]), enhanced, assets.read_bytes(snapshot["mask_asset_id"]),
            harmonize=snapshot["harmonize"], harmonize_strength=snapshot["harmonize_strength"],
        ).output_png

    def attach(self, job, workflow):
        snapshot = job["snapshot"]
        owner = snapshot["owner"]
        service = self._service(owner)
        info = DlssResult(job_id=job["job_id"], parent_attempt_id=snapshot["parent_attempt_id"], root_attempt_id=snapshot["root_attempt_id"],
                          input_asset_id=snapshot["input_asset_id"], report_asset_id=job["report_asset_id"],
                          width=job["output_metadata"]["width"], height=job["output_metadata"]["height"], size=job["settings"]["size"],
                          fps=job["output_metadata"].get("fps"), duration_seconds=job["output_metadata"].get("duration_seconds"))
        with service._lock:
            project = self._get(service, owner, snapshot["owner_id"])
            existing = next((a for a in project.attempts if a.dlss and a.dlss.job_id == job["job_id"]), None)
            if existing:
                return existing.attempt_id
            self.validate_current(snapshot)
            parent = next(a for a in project.attempts if a.attempt_id == snapshot["parent_attempt_id"])
            fields = dict(attempt_id="dlss-result-" + job["job_id"][5:], dlss=info, execution_id=None, compiled_workflow_sha256=None,
                          output_asset_id=job["output_asset_id"], error=None)
            if owner == "edit":
                original = next(a for a in project.attempts if a.attempt_id == snapshot["original_attempt_id"])
                candidate = replace(original, **fields, status=Krea2EditAttemptStatus.SUCCEEDED, kind="upscale", retouch=None,
                                    output_dimensions=(info.width, info.height),
                                    upscale=Krea2EditUpscale(original_attempt_id=original.attempt_id, parent_attempt_id=parent.attempt_id,
                                        input_asset_id=info.input_asset_id, model_name="NVIDIA DLSS", request_id=job["job_id"],
                                        workflow=workflow.reference, width=info.width, height=info.height,
                                        mask_asset_id=snapshot.get("mask_asset_id"), harmonize=snapshot.get("harmonize", False),
                                        harmonize_strength=snapshot.get("harmonize_strength", 100), enhanced_asset_id=job["enhanced_asset_id"],
                                        preserve_source_size=info.size == "source"))
                service.sources.save(replace(project, attempts=(*project.attempts, candidate)))
            elif owner == "assisted":
                candidate = replace(parent, **fields, status=Krea2AssistedAttemptStatus.SUCCEEDED, kind="dlss", composition=None,
                                    accepted=False, queue_order=None)
                service.projects.save(replace(project, attempts=(*project.attempts, candidate)))
            else:
                frames = tuple(H3RenderKeyframe(**frame) for frame in job["keyframes"])
                candidate = replace(parent, **fields, status=H3RenderAttemptStatus.SUCCEEDED,
                                    keyframes=frames, keyframe_timestamps_ms=tuple(f.timestamp_ms for f in frames),
                                    warnings=tuple(job.get("warnings", [])))
                service.projects.save(replace(project, attempts=(*project.attempts, candidate)))
            return candidate.attempt_id
