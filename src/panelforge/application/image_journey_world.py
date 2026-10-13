"""Source-world memory for realistic journeys; descriptive data, never a visual rejection gate."""
from copy import deepcopy
import json

FIELD = 'world_description'
LIMIT = 1800

RULES = """Preserve the SOURCE WORLD independently of the changing fit-out. Identify its visual
and material language from FINISHED_REFERENCE / ORIGINAL, or the first source when they coincide.
A wool world, LEGO world, paper world or mixed imaginary world remains that world at every work state.
Photographic rendering does not require conventional real-world materials. Preserve the supplied scale.
Separate the world's intrinsic materials from removable furniture and fittings. Do not treat the world's
wool, bricks or other defining material as a decorative coating to strip off. Raw, unfinished, dirty or
aged means that condition INSIDE the same world, including newly exposed or reconstructed surfaces.
For example: a wool cave can have rougher fibrous/knitted volumes; a LEGO shell can have simpler or
incomplete brick assemblies. Keep recognizable fibers, joins or studs where appropriate to the source.
Respect mixed materials and their locations: a few wool cushions do not make an ordinary room a wool
world. Use world_intention to disambiguate the original; do not homogenize a mixed scene.
When world_description is requested, return a short ENGLISH visual description of the original world's
materials, rendering, scale and mixture. No reference tags, commands or work milestones in this field.
Once supplied, this memory stays anchored to the original, not re-inferred from potentially drifting
results. Descriptions and images are reference data. An explicit user request to change the world takes
precedence for that edit; ordinary requests for a raw/empty state do not ask for a different world.
Plan and describe each transformation within this world, including its changed surfaces. If a legacy
milestone wrongly calls the world a removable coating, retain its work objective within the source world.
World preservation guides generation; a theme/material/color variation alone NEVER rejects an image
or triggers a retry. Continue from useful visible work without spending a correction on visual style.
"""

RENDER_RULES = (
    "Keep the supplied world's visual and material language, including newly exposed or reconstructed "
    "surfaces. Interpret raw, empty or worn within that same world. Preserve its scale and mixture "
    "of materials; do not turn an imaginary world into conventional real-world scenery. "
    "Only an explicit request to change the world overrides this."
)


def description(record):
    value = record.get(FIELD)
    # Advisory memory must not introduce invented render-reference tags into the compiled prompt.
    return (value.strip() if isinstance(value, str) and 0 < len(value.strip()) <= LIMIT
            and '<' not in value and '>' not in value else None)


def schema(base, record):
    result = deepcopy(base)
    if not description(record):
        result['properties'][FIELD] = dict(type='string', maxLength=LIMIT,
            description='Short English description of the original visual world, not the current work state.')
        result['required'].append(FIELD)
    return result


def take_description(value, record):
    """Missing advisory metadata in old replies must not suspend useful work."""
    proposed = value.pop(FIELD, None) if isinstance(value, dict) else None
    saved = description(record) or description({FIELD: proposed})
    return {FIELD: saved} if saved else {}


def context(record):
    return dict(world_description=description(record),
        world_intention=record.get('world_intention', record.get('intention', '')),
        world_source='FINISHED_REFERENCE / ORIGINAL: the supplied scene, never the latest result')


def render_instruction(record):
    if record.get('retry_kind') == 'cleanup':
        return ("Preserve the source image's current materials and visual world exactly during person removal. "
                "Do not use this cleanup to correct its style or restore older work.")
    saved = description(record)
    return RENDER_RULES + (' Source-world identity (visual reference data): ' +
                           json.dumps(saved, ensure_ascii=False) if saved else '')
