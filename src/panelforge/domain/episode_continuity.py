"""Resolve the visual ledger into fabrication references and readable scene inputs."""
from copy import deepcopy

from . import story_continuity as ledger


def active(episode):
    return episode.get("continuity_version") == ledger.VERSION


def sync_references(episode, model_id):
    if not active(episode):
        return
    if episode.get("visual_state_policy") == 2:
        from .story_reference_plan import build, appearance_key
        plan = build(episode["scenario"])
        specs = plan["references"]
        for ref in episode["references"]:
            initial = plan["identities"].get(ref["source_id"])
            if not initial or ref.get("continuity_state_id") or ref["kind"] != "character":
                continue
            old_description = ref.get("continuity_identity_description")
            if (appearance_key(ref.get("continuity_appearance", {})) != appearance_key(initial["state"])
                    or old_description != initial["description"]):
                if old_description is None or ref["description"] == old_description:
                    ref["description"] = initial["description"]
                ref["continuity_image_stale"] = bool(ref.get("image_asset_id"))
                ref["revision"] += 1
            ref["continuity_identity_description"] = initial["description"]
            ref["continuity_appearance"] = deepcopy(initial["state"])
    else:
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
            if "continuity_appearance" in spec:
                ref["continuity_appearance"] = deepcopy(spec["continuity_appearance"])
                ref["continuity_state_id"] = spec["continuity_state_id"]


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
    for row in ledger.scene_rows(scenario, index, explicit_presence=required_states(episode)):
        if row["tracking"] != "reference":
            continue
        state_id = row["before"]["reference_state_id"]
        desired = desired_reference(episode, row["element_id"], scene["index"])
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
    if required_states(episode):
        for desired in required_bindings(episode, scene):
            ref = refs.get(desired)
            if ref:
                resolved, replaced = [], False
                for binding in result:
                    if refs.get(binding["reference_id"], {}).get("source_id") != ref["source_id"]:
                        resolved.append(binding)
                    elif not replaced:
                        resolved.append(dict(reference_id=desired, role=binding["role"]))
                        replaced = True
                if not replaced:
                    resolved.append(dict(reference_id=desired, role="subject_reference"))
                result = resolved
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
    return ledger.scene_rows(episode["scenario"], scene["index"], explicit_presence=required_states(episode)) if active(episode) else []


def required_states(episode):
    return episode.get("visual_state_policy") in {1, 2} and active(episode)


def desired_reference(episode, element_id, index):
    if episode.get("visual_state_policy") == 2:
        from .story_reference_plan import build
        identity = build(episode["scenario"])["bindings"].get((element_id, index))
        if identity is not None:
            return identity
        return next((r["id"] for r in episode["references"] if r["source_id"] == element_id
                     and not r.get("continuity_state_id") and not r.get("continuity_archived")), None)
    element = next(e for e in ledger.elements(episode["scenario"]) if e["id"] == element_id)
    return ledger.reference_id(element_id, ledger.state_at(element, index)["reference_state_id"])


def reference_appearance(episode, ref):
    """What an existing reference represents, including legacy state IDs."""
    if "continuity_appearance" in ref:
        return ref["continuity_appearance"]
    from .story_reference_plan import appearance
    element = next((e for e in ledger.elements(episode["scenario"]) if e["id"] == ref["source_id"]), None)
    if element is None:
        return None
    state_id = ref.get("continuity_state_id")
    if state_id:
        change = next((s for s in element["states"] if s["id"] == state_id), None)
        return appearance(ledger.state_at(element, change["scene_index"], end=change["at"] == "end")) if change else None
    first = min(element["scene_indices"], default=0)
    return appearance(ledger.state_at(element, first))


def variant_base(episode, ref):
    if ref.get("continuity_source_image"):
        return ref["continuity_source_image"]
    return next((r for r in episode["references"] if r["source_id"] == ref["source_id"]
                 and not r.get("continuity_state_id") and not r.get("continuity_archived")), None)


def variant_signature(episode, ref):
    from .episodes import fingerprint
    base = variant_base(episode, ref)
    return fingerprint([base.get("image_asset_id") if base else None, ref["description"]])


def variant_source_ready(episode, ref):
    base = variant_base(episode, ref)
    return bool(base and base.get("image_asset_id")
        and (episode.get("visual_state_policy") != 2 or not base.get("continuity_image_stale")))


def variant_stale(episode, ref):
    if episode.get("visual_state_policy") == 2 and (ref.get("continuity_state_id") or ref.get("continuity_source_image")):
        base = variant_base(episode, ref)
        if base and base.get("continuity_image_stale"):
            return True
    return bool(ref.get("continuity_image_stale") or (required_states(episode)
        and ref.get("continuity_source_signature")
        and ref["continuity_source_signature"] != variant_signature(episode, ref)))


def required_bindings(episode, scene):
    """A required state is authoritative even when a manual scene binding omits its identity."""
    result = []
    if not required_states(episode) or episode.get("localization"):
        return result
    for row in ledger.scene_rows(episode["scenario"], scene["index"], explicit_presence=required_states(episode)):
        if row["tracking"] == "reference":
            state_id = row["before"]["reference_state_id"]
            if state_id or row["kind"] == "object" or episode.get("visual_state_policy") == 2:
                desired = desired_reference(episode, row["element_id"], scene["index"])
                if desired:
                    result.append(desired)
    return result


class RequiredReferenceMissing(ValueError):
    pass


def missing_requirements(episode, scene):
    refs = {r["id"]: r for r in episode["references"]}
    result = []
    for identity in required_bindings(episode, scene):
        ref = refs.get(identity)
        if not ref or not ref.get("image_asset_id") or variant_stale(episode, ref):
            result.append(dict(reference_id=identity, name=ref["name"] if ref else "État visuel",
                message=("Référence à actualiser : " if ref and ref.get("image_asset_id") else "Référence à préparer : ")
                        + (ref["name"] if ref else "État visuel") + ". Ouvre Références pour préparer ou choisir son image."))
    return result
