"""Worker identity, normalized placement and explicit shared scale references."""
from copy import deepcopy
import math

CREWS = {
    "solo": dict(label="Ouvrier solo", description="Un seul ouvrier réalise les travaux, avec des moyens adaptés."),
    "team": dict(label="Petite équipe", description="Quelques ouvriers coopèrent ; proposer un effectif utile et des tâches complémentaires."),
    "site": dict(label="Petit chantier", description="Un chantier coordonné avec plusieurs tâches et des engins légers si utiles."),
    "industrial": dict(label="Gros chantier industriel", description="Des équipes organisées, transport et levage mécanisés selon les travaux."),
}


def crew_catalog():
    return [dict(id=key, **value) for key, value in CREWS.items()]


def crew_contract(settings):
    key = settings.get("crew_size", "solo")
    return dict(id=key, **CREWS[key])


def placement(value, scene_dimensions, worker_dimensions):
    if not isinstance(value, dict) or set(value) != {"x", "y", "height"}:
        raise ValueError("Position d’échelle invalide.")
    for number in value.values():
        if type(number) not in (int, float) or not math.isfinite(number):
            raise ValueError("La position doit contenir des nombres finis.")
    x, y, height = (float(value[key]) for key in ("x", "y", "height"))
    if not .005 <= height <= .85:
        raise ValueError("La hauteur doit être comprise entre 0,5 % et 85 % de l’image.")
    sw, sh = scene_dimensions
    ww, wh = worker_dimensions
    width = height * sh * ww / wh / sw
    if not width / 2 <= x <= 1 - width / 2 or not height <= y <= 1:
        raise ValueError("Place le personnage entièrement dans l’image.")
    return dict(x=x, y=y, height=height)


def reference_state(project, transition):
    worker = deepcopy(project.get("worker_reference"))
    scale_id = transition.get("scale_setup_id")
    scale = deepcopy(project.get("scale_setups", {}).get(scale_id))
    error = None
    if scale_id:
        frames = {f["id"]: f for f in project["frames"]}
        basis = frames.get(scale.get("basis_frame_id")) if scale else None
        if not scale or not basis or basis["asset_id"] != scale["basis_asset_id"]:
            error = "Le décor de référence a changé. Repositionne l’ouvrier ou retire cette échelle."
        elif not worker or worker["asset_id"] != scale["worker_asset_id"]:
            error = "L’ouvrier a changé. Repositionne-le pour actualiser l’image d’échelle."
        else:
            order = [frame["id"] for frame in project["frames"]]
            start, end = order.index(basis["id"]), order.index(transition["left"])
            path = set(zip(order[start:end], order[start + 1:end + 1]))
            if start > end or any(t["kind"] == "camera" and (t["left"], t["right"]) in path
                                  for t in project["transitions"]):
                error = "Le cadrage a changé depuis ce montage. Repositionne l’ouvrier sur ce nouveau plan."
    return dict(worker=worker, scale=scale, scale_id=scale_id, error=error,
                mode="ref2v" if worker else "h3")


def require_references(project, transition):
    result = reference_state(project, transition)
    if result["error"]:
        raise ValueError(result["error"])
    return result


def scope_targets(transitions, identity, scope):
    if scope not in {"pair", "following"}:
        raise ValueError("Portée d’échelle inconnue.")
    start = next(i for i, t in enumerate(transitions) if t["id"] == identity)
    first = transitions[start]
    result = [first]
    if scope == "pair" or first["kind"] == "camera":
        return result
    old_group = first.get("scale_setup_id")
    for transition in transitions[start + 1:]:
        # An explicit different composition or a known camera move starts another shot.
        if transition["kind"] == "camera":
            break
        if transition.get("scale_setup_id") not in {None, old_group}:
            break
        result.append(transition)
    return result
