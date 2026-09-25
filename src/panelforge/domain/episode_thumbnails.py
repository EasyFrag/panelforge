"""Independent episode covers: editorial numbering and reusable visual contracts."""
import math

from .story_library import memberships
from .qwen_edit import MAX_RENDER_IMAGES


class ThumbnailConflict(ValueError):
    pass


ACTIVE = {"queued", "running"}
GRID_LAYOUT = "grid-cover-v3"


def cover_format(layout=GRID_LAYOUT):
    if layout == GRID_LAYOUT:
        return {"width": 1080, "height": 1440, "aspect_ratio": "3:4"}
    if layout in {"outfit-cover-v1", "poster-cover-v2"}:
        return {"width": 1080, "height": 1920, "aspect_ratio": "9:16"}
    raise ValueError("Ce gabarit de miniature n’est pas disponible.")

TITLE_STYLES = {"pop", "cinema"}
REFERENCE_ROLES = {"foreground", "background", "environment", "object", "style"}
ROLE_INSTRUCTIONS = {
    "foreground": "MAIN SUBJECT: large in the foreground, prominent expressive face, strongest visual focus",
    "background": "SUPPORTING SUBJECT: recognizable in a smaller secondary layer behind the leads, visible face, never competing in scale with the leads",
    "environment": "ENVIRONMENT ONLY: use its location, atmosphere and lighting, do not copy incidental people",
    "object": "SIGNATURE OBJECT: a recognizable secondary narrative detail, not a new protagonist",
    "style": "STYLE ONLY: borrow palette, materials and visual treatment, do not add its depicted people or copy its text",
}


def default_role(reference):
    return {"location": "environment", "object": "object"}.get(reference["kind"], "foreground")


def assign_reference_roles(references, roles=None):
    if roles is not None and (not isinstance(roles, dict) or set(roles) - {r["id"] for r in references}
                              or any(role not in REFERENCE_ROLES for role in roles.values())):
        raise ValueError("Chaque rôle doit correspondre à une image sélectionnée.")
    return [{**ref, "placement": (roles or {}).get(ref["id"], default_role(ref))} for ref in references]



def editorial_context(episode, projects, metadata):
    by_id = {p["project_id"]: p for p in projects}
    story = by_id[episode["story_id"]]
    group, number = memberships(projects, metadata)[story["project_id"]]
    if story.get("narrative_format") == "long" and (story.get("long_options") or {}).get("delivery", "serial") != "continuous":
        units = (story.get("document", {}).get("series_outline") or {}).get("episodes", [])
        number += next((i for i, unit in enumerate(units) if unit["id"] == episode.get("series_episode_id")), 0)
    title = metadata.get("groups", {}).get(group, {}).get("title") or by_id.get(group, story)["title"]
    return dict(group_id=group, title=title[:80], number=number)


def reference_choices(episode):
    return [dict(id=r["id"], name=r["name"], kind=r["kind"], source_id=r.get("source_id", r["id"]), asset_id=r["image_asset_id"])
            for r in episode.get("references", []) if r.get("image_asset_id") and not r.get("continuity_archived") and not r.get("continuity_image_stale")]


def default_references(choices):
    # One state per character, a small cast, and one location. No incidental props.
    characters = {}
    for ref in choices:
        if ref["kind"] == "character":
            characters.setdefault(ref.get("source_id", ref["id"]), ref["id"])
    return list(characters.values())[:2] + [r["id"] for r in choices if r["kind"] == "location"][:1]


def validate_options(title, number, title_mode, direction, title_style="pop"):
    if not isinstance(title, str) or not 1 <= len(title.strip()) <= 80:
        raise ValueError("Le titre public doit contenir de 1 à 80 caractères.")
    if type(number) is not int or not 1 <= number <= 9999:
        raise ValueError("Le numéro d’épisode doit être compris entre 1 et 9999.")
    if title_mode not in {"artwork", "overlay"}:
        raise ValueError("Choisis un titre Qwen ou un titre Outfit.")
    if title_style not in TITLE_STYLES:
        raise ValueError("Choisis un habillage de titre Pop ou Cinéma.")
    if not isinstance(direction, str) or len(direction) > 1500:
        raise ValueError("La direction visuelle est limitée à 1 500 caractères.")


def composition_prompt(title, title_mode, references, direction, title_style="pop"):
    import json
    roles = []
    for i, ref in enumerate(references, 1):
        placement = ref.get("placement", default_role(ref))
        kind = {"location": "location", "object": "object"}.get(ref["kind"], "character identity")
        roles.append(f"<image{i}> supplies {kind} {json.dumps(ref['name'], ensure_ascii=False)}. "
                     + ROLE_INSTRUCTIONS[placement] + ".")
    treatment = {
        "pop": "oversized ultra-heavy geometric display lettering, tight bold shapes, crisp dark outline, "
               "a vivid lime offset extrusion and bright cream-white faces, a contemporary premium animated-series poster title",
        "cinema": "tall heavy condensed display lettering, compact spacing, a strong warm ivory face, "
                  "subtle amber dimensional shadow, sharp high-contrast modern cinematic poster typography",
    }[title_style]
    lettering = ("Use the quoted title supplied at the end as the only visible lettering. "
                 f"Style the title using {treatment}. "
                 "Arrange it on two or three balanced lines, legible at small thumbnail size. "
                 "Keep the complete title within 10% to 29% of image height, with 9% side margins. "
                 "Leave a clear margin above the title. Do not add lettering at the top edge, "
                 "on clothing or in the bottom badge area. Do not render prompt instructions as visible text."
                 if title_mode == "artwork" else
                 "Draw no text or letters. Keep the title area (10% to 29% of image height, 9% side margins) "
                 "as a simple low-detail background for typography added later.")
    subjects = ("Build a layered ensemble composition. Foreground subjects dominate the lower central area; "
                "supporting subjects remain recognizable behind them, smaller but not miniature silhouettes. "
                "Keep all faces unobstructed, preserve each identity separately, do not merge features or repeat a character. "
                if any(ref.get("placement", default_role(ref)) in {"foreground", "background"} for ref in references)
                else "Feature the supplied environment or objects without inventing characters. ")
    return ("Create one polished portrait 3:4 series cover, one cohesive scene with natural expressive poses. "
            "Preserve the supplied subjects, identities and visual style. Use rich cinematic lighting. " + subjects +
            "Arrange faces and important props between 33% and 72% of image height, outside both reserved text areas. "
            "Leave the area between 80% and 91% of image height quiet and without text for the episode badge added later. "
            "Keep all important content away from the top and bottom edges. No episode number, no logos, no watermark, no collage panels. " + lettering + "\n" + "\n".join(roles)
            + ("\nArt direction for poses, atmosphere and environment (keep the reference roles and text areas above): "
               + direction.strip() if direction.strip() else "")
            + ("\n\n" + json.dumps(title, ensure_ascii=False) if title_mode == "artwork" else ""))


def badge_geometry(layout, position=None):
    """Coordinates are percentages of available travel, keeping the whole badge inside."""
    canvas = cover_format(layout)
    width, height, x, y = ((851, 226, 115, 1480) if layout == "outfit-cover-v1" else
                           (501, 161, 290, 1590 if layout == "poster-cover-v2" else 1150))
    travel_x, travel_y = canvas["width"] - width, canvas["height"] - height
    default = {"x": x * 100 / travel_x, "y": y * 100 / travel_y}
    if position is not None:
        if (not isinstance(position, dict) or set(position) != {"x", "y"}
                or any(type(v) not in {int, float} or not math.isfinite(v) or not 0 <= v <= 100 for v in position.values())):
            raise ValueError("La position du bandeau doit contenir x et y entre 0 et 100.")
        x, y = int(travel_x * position["x"] / 100 + .5), int(travel_y * position["y"] / 100 + .5)
    return dict(x=x, y=y, width=width, height=height, canvas=canvas,
                position=dict(position) if position is not None else default, default_position=default)


def displayed_template_id(record):
    if not record.get("asset_id"):
        return None
    if record.get("asset_template_id"):
        return record["asset_template_id"]
    if record.get("status") != "ready" and record.get("history"):
        return record["history"][-1].get("template_id")
    return record.get("template_id")


def template_usage(index, template_id):
    episodes = {key for key, record in index["episodes"].items()
                if record.get("template_id") == template_id or displayed_template_id(record) == template_id}
    series = sum(value == template_id for value in index["series"].values())
    pending = any(t.get("previous_template_id") == template_id and t["status"] in ACTIVE
                  for t in index["templates"].values())
    return dict(episode_count=len(episodes), series_count=series,
                can_archive=not episodes and not series and not pending)
