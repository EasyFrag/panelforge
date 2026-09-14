"""Admit a comparison into the existing DLSS worker, without changing video admission."""

from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import hashlib
import re

from panelforge.domain.dlss import DlssSettings
from panelforge.domain.dlss_image_presets import PRESET_VERSION, selected_image_presets


def queue_image_comparison(service, *, owner, owner_id, attempt_id, settings, preset_ids, request_id):
    if owner not in {"assisted", "edit"}:
        raise ValueError("La comparaison DLSS est réservée aux images Assisted et Edit.")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", request_id):
        raise ValueError("Identifiant de demande DLSS invalide.")
    presets = selected_image_presets(settings, preset_ids)
    group_id = "dlss-compare-" + hashlib.sha256(
        f"image-comparison:{owner}:{owner_id}:{request_id}".encode()).hexdigest()[:32]
    request = {"owner": owner, "owner_id": owner_id, "attempt_id": attempt_id,
               "settings": asdict(settings), "preset_ids": [p["preset_id"] for p in presets],
               "preset_version": PRESET_VERSION}
    identifiers = ["dlss-" + hashlib.sha256(f"{group_id}:{p['preset_id']}".encode()).hexdigest()[:32] for p in presets]

    def existing_jobs():
        # Also reject request-ID reuse with a different subset of presets.
        values = {j["job_id"]: j for j in service.jobs.list() if j.get("comparison", {}).get("group_id") == group_id}
        if any(j["request"] != request for j in values.values()):
            raise ValueError("Cette comparaison correspond déjà à d’autres réglages.")
        return values

    existing = existing_jobs()
    if all(identifier in existing for identifier in identifiers):
        service.wake()
        return [existing[identifier] for identifier in identifiers]

    # Only one source read/probe, regardless of the number of variants.
    preview = service.preview(owner, owner_id, attempt_id, settings)
    if not preview["snapshot"]["media_type"].startswith("image/"):
        raise ValueError("La comparaison DLSS nécessite une image.")
    prepared = []
    now = datetime.now(timezone.utc)
    for index, (identifier, preset) in enumerate(zip(identifiers, presets)):
        job = dict(deepcopy(preview), schema_version=1, job_id=identifier, request=request,
                   settings=asdict(DlssSettings(**preset["settings"])),
                   created_at=(now + timedelta(microseconds=index)).isoformat(), status="queued", error=None,
                   endpoint=service.comfy.base_url, execution_id=None, output_asset_id=None, candidate_id=None,
                   comparison={"group_id": group_id, "preset_id": preset["preset_id"], "label": preset["label"],
                               "version": PRESET_VERSION, "index": index, "total": len(presets)})
        job["workflow"] = asdict(service.workflow(job).reference)
        prepared.append(job)

    with service._lock, service.jobs.lease("requests", wait_timeout=5):
        existing = existing_jobs()
        service.candidates.validate_current(preview["snapshot"])
        if any(j["snapshot"] != preview["snapshot"] for j in existing.values()):
            raise ValueError("La source de cette comparaison a changé. Lance une nouvelle comparaison.")
        # Persist before waking the worker. An interrupted write can be retried
        # with the same request ID: existing jobs are never reset or duplicated.
        result = [existing.get(j["job_id"], j) for j in prepared]
        for job in result:
            if job["job_id"] not in existing:
                service.jobs.save(job)
    service.wake()
    return result
