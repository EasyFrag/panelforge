"""Resolve the visual ledger into fabrication references and readable scene inputs."""
from copy import deepcopy

from . import story_continuity as ledger


def active(episode):
    return episode.get("continuity_version") == ledger.VERSION


def sync_references(episode, model_id):
    if not active(episode):
        return
    specs = ledger.reference_specs(episode["scenario"])
    wanted = {s["id"] for s in specs}
    refs = {r["id"]: r for r in episode["references"]}
    for ref in refs.values():
        if "continuity_element_id" in ref:
            ref["continuity_archived"] = ref["id"] not in wanted
    for spec in specs:
        ref = refs.get(spec["id"])
        if ref is None:
            ref = dict(**spec, revision=1, image_asset_id=None, images=[], krea_project_id=None,
                prompt="", model_id=model_id, render_settings=None, inherit_image_settings=True, job=None,
                continuity_generated_description=spec["description"])
            episode["references"].append(ref)
        else:
            ref["continuity_archived"] = False
            if ref.get("continuity_generated_description") != spec["description"]:
                if ref.get("continuity_generated_description") == ref["description"]:
                    ref["description"] = spec["description"]
                ref["name"] = spec["name"]
                ref["revision"] += 1
                ref["continuity_image_stale"] = bool(ref.get("image_asset_id"))
            ref["continuity_generated_description"] = spec["description"]


def bindings(episode, scene):
    result = deepcopy(scene["references"])
    if not active(episode):
        return result
    refs = {r["id"]: r for r in episode["references"]}
    for binding in list(result):
        archived = refs.get(binding["reference_id"], {})
        if not archived.get("continuity_archived"):
            continue
        base = next((r for r in refs.values() if r["kind"] == "character" and r["source_id"] == archived.get("source_id")
                     and not r.get("continuity_state_id")), None)
        if base and not any(b["reference_id"] == base["id"] for b in result):
            binding["reference_id"] = base["id"]
        else:
            result.remove(binding)
    scenario, index = episode["scenario"], scene["index"]
    # The explicit ledger can declare a silent observer omitted from the original
    # character_ids. Do not guess presence from a mention in dialogue or prose.
    extra = set(ledger.present_ids(scenario, index)) - set(scenario["scenes"][index]["character_ids"])
    for ref in refs.values():
        if ref["kind"] == "character" and ref["source_id"] in extra and "continuity_element_id" not in ref:
            if not any(b["reference_id"] == ref["id"] for b in result):
                result.append(dict(reference_id=ref["id"], role="subject_reference"))
    for row in ledger.scene_rows(scenario, index):
        if row["tracking"] != "reference":
            continue
        state_id = row["before"]["reference_state_id"]
        desired = ledger.reference_id(row["element_id"], state_id)
        matching = [b for b in result if b["reference_id"] in refs
                    and refs[b["reference_id"]]["source_id"] == row["element_id"]]
        if any(refs[b["reference_id"]].get("continuity_state_id") for b in matching):
            # An explicit variant overrides the automatic identity binding; do
            # not send two conflicting bodies merely because the base remained.
            for binding in matching:
                if not refs[binding["reference_id"]].get("continuity_state_id"):
                    result.remove(binding)
            continue
        if row["kind"] == "object" and not matching and desired in refs:
            result.append(dict(reference_id=desired, role="subject_reference"))
        elif state_id and desired in refs:
            for binding in matching:
                # A manually selected variant is an explicit override. The base
                # identity binding follows the automatic state timeline.
                ref = refs[binding["reference_id"]]
                if not ref.get("continuity_state_id"):
                    if any(b["reference_id"] == desired for b in result):
                        result.remove(binding)
                    else:
                        binding["reference_id"] = desired
    return result


def scene_warnings(episode, scene):
    result = []
    scenario, index = episode["scenario"], scene["index"]
    for char in ledger.missing_mentions(scenario, index):
        result.append(f"{char['name']} est cité dans la mise en scène, mais absent du casting déclaré. "
                      "S'il est visible, ajoute-le aux scènes concernées dans Continuité ou à la scène.")
    if active(episode):
        for binding in bindings(episode, scene):
            ref = next((r for r in episode["references"] if r["id"] == binding["reference_id"]), None)
            if ref and ref.get("continuity_image_stale"):
                result.append(f"{ref['name']} : l'état a changé depuis le choix de l'image. Vérifie ou remplace cette référence.")
    return result


def snapshot(episode, scene):
    return ledger.scene_rows(episode["scenario"], scene["index"]) if active(episode) else []
