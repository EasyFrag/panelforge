"""Visual worker routing and scoped LLM rules, shared by transitions and Classic."""
import json
import re

from panelforge.domain.worker_visual_policy import VERSION

# Reject the known old instruction if it is pasted back or echoed by a model.
_TENTH = r"(?:one[ -]tenth|un dixi[eè]me|1\s*/\s*10)"
_LEGACY_SCALE = re.compile(rf"(?is)(?:{_TENTH}.{{0,100}}(?:trunk|tronc)|(?:trunk|tronc).{{0,100}}{_TENTH})")


def reject_legacy_scale(text):
    if _LEGACY_SCALE.search(text):
        raise ValueError("Retirez l’ancienne taille textuelle de l’ouvrier ; son échelle vient du montage de référence.")


def resolve(policy, session, mapping):
    if policy is None:
        return None
    def number(asset_id, role):
        candidates = [n for ref_id, n in mapping
                      if session.reference(ref_id).asset_id == asset_id and session.reference(ref_id).role == role]
        if len(candidates) != 1:
            raise ValueError("La référence d’ouvrier ne correspond plus aux images du Plan.")
        return candidates[0]
    return dict(version=policy.version,
                identity_picture=number(policy.identity_asset_id, "subject_reference"),
                scale_picture=number(policy.scale_asset_id, "composition_reference") if policy.scale_asset_id else None,
                depict_worker=policy.depict_worker)


def rules(binding):
    if not binding:
        return {}
    result = {binding["identity_picture"]:
        f'Use <Picture {binding["identity_picture"]}> as the sole visual definition of the worker’s identity, appearance, body and clothing. '
        'Its background, pose and framing are not scene instructions.'}
    if binding.get("scale_picture"):
        result[binding["scale_picture"]] = (
            f'Use <Picture {binding["scale_picture"]}> as the sole visual definition of the worker’s scale and ground placement in the scene. '
            'Maintain that physical scale with perspective during movement. '
            'This is a scale mock-up, not an intermediate scene state; ignore collage edges and any portrait background.')
    return result


def guidance(binding):
    if not binding:
        return ""
    refs = " ".join(rules(binding).values())
    return ("\nWORKER VISUAL-ONLY CONTRACT\n" + refs +
        " Never describe or reinterpret the worker’s identity, appearance, body or clothing in words. "
        "Never translate the scale image into a ratio, measurement or verbal size description. "
        "This applies to ALL output fields, including observations, invariants, scene setup, actions and final prose. "
        "Identify the actor only by its assigned Picture reference or 'the worker' / 'the crew'; never redescribe even correctly observed features. "
        "When the worker first acts, keep the explicit identity Picture link" +
        (" and the scale/placement Picture link together in the action paragraph." if binding.get("scale_picture") else " in the action paragraph.") +
        " Preserve these links from intention to Plan to Writer. Describe actions, tools, material handling, cooperation, movement and sound. "
        "Choose suitable equipment from the images without verbalizing the worker’s size. "
        "Do not add workers to a camera-only move. Do not copy old appearance or scale prose from user notes or history.")


def validate(text, binding, *, require_links=False):
    if not binding:
        return
    if binding.get("version") != VERSION:
        raise ValueError("Version du contrat visuel d’ouvrier inconnue.")
    reject_legacy_scale(text)
    if require_links and binding.get("depict_worker", True):
        for number in (binding["identity_picture"], binding.get("scale_picture")):
            if number and not re.search(rf"(?i)<?Picture\s+{number}\b>?", text):
                raise ValueError(f"Conservez le lien vers <Picture {number}> dans l’action de l’ouvrier.")


def scoped_schema(encoded, binding):
    """Replace the three text-scale schema hints only for visual-only preparations."""
    if not binding:
        return encoded
    schema = json.loads(encoded)
    descriptions = {
        "actions": "English visible actions in causal order. Keep actual identity and scale Picture links at the worker’s appearance. Describe actions and tools only for this actor, never appearance, clothing, body, ratios or size. No camera, cut or timestamp. Spoken lines retain exact tagged words and language.",
        "continuity_invariants": "English reference associations, setting, object ownership and progression. For the worker, use only identity and scale Picture links; no appearance, clothing, morphology or textual size.",
        "phases": "One English action paragraph per approved phase, same order. Preserve causal actions and actual worker identity and scale Picture links. No worker appearance, clothing, body or textual size. Keep exact tagged speech and language. No repetition of camera, framing, cue, pacing, end-state or transition.",
    }
    def visit(value):
        if isinstance(value, dict):
            for key, child in value.get("properties", {}).items():
                is_prose = key != "phases" or (isinstance(child, dict) and child.get("items", {}).get("type") == "string")
                if key in descriptions and is_prose and isinstance(child, dict) and "description" in child:
                    child["description"] = descriptions[key]
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
    visit(schema)
    return json.dumps(schema, ensure_ascii=False)
