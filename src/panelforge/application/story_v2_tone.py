"""Small opt-in editorial tone, shared by both screenplay versions only."""
VERSION = "1.0.0"
COMMON = """Selected tone — Sketch provocateur: an excessive, provocative TikTok sketch with frankly crude language.
In French, use lively contemporary young neighbourhood speech; keep the requested language and universe.
Give characters distinct voices: mockery, bad faith and sharp replies arise from their aims, never a slang
or insult quota. Explicit author constraints take priority; keep the version's timing and staging rules.
"""
WRITE = """Hook the audience in the opening seconds through a striking action or line that also establishes the
essential context. Invent details and amplify situations, embarrassment and reactions around the idea,
while respecting explicitly requested events and ending. Keep motives and causal consequences readable.
End on an earned punchline, a consequential revenge decision or a strong prepared cliffhanger; do not force
closure or a generic sequel slogan. Revision scope still applies: preserve unaffected content.
"""
POLISH = """Preserve each voice's bite, irreverence and comic intent when making speech more natural. Clarify a
confusing jab without making it polite or generic. Keep the hook and the force of the existing ending;
this retouch does not invent a different ending or new provocations.
"""
REVIEW = """Judge comprehension within this selected tone. Do not require polite language, a moral lesson or a
resolved ending. Deliberate excess and a prepared cliffhanger are not inconsistencies; report concrete
comprehension or fidelity problems, not a preference for a milder register.
"""


def apply_tone(recipe, tone_profile):
    if tone_profile == "from_idea":
        return recipe
    if tone_profile != "provocative_sketch":
        raise ValueError("Ton d'histoire inconnu.")
    result = dict(recipe)
    result["version"] = f"{recipe['version']}+sketch-{VERSION}"
    for role in ("write", "repair"):
        # A complete scene list can end on an intentional cliffhanger.
        base = recipe[role].replace("Write ONE complete, playable short story", "Write ONE playable short story")
        base = base.replace("Write ONE short, complete, playable story", "Write ONE short, playable story")
        result[role] = base + "\n" + COMMON + WRITE
    # Allow the chosen slang while retaining the protection against repetitive verbal tics.
    result["polish"] = recipe["polish"].replace("forced slang", "repetitive slang tics") + "\n" + COMMON + POLISH
    result["review"] = recipe["review"] + "\n" + COMMON + REVIEW
    return result
