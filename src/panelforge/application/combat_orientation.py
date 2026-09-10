"""Compact, exact-version choreography guidance for Combat 1.2.0 only.

Injected at existing decision/writer/revision stages; no classification call,
render settings or infrastructure dependency. Earlier settings have no direction.
"""
from panelforge.domain.video_preparation import CombatSettings


_DIRECTIONS_1_2_0 = {
    "mixed": (
        "MIXED / FREE: Develop the contrasting styles, abilities and equipment established by the intention. "
        "Connect movement, range control and defense to the requested powers or weapons. A magical effect "
        "extends a concrete attack, changes a route or forces a physical response; it does not replace the "
        "whole exchange with an unrelated explosion. Do not introduce powers or weapons merely for this orientation."
    ),
    "hand_to_hand": (
        "HAND-TO-HAND: Prioritize foot placement, distance, anatomical contacts, checks, slips, grips and "
        "balance changes compatible with the requested style. A forearm check may open an angle; a displaced "
        "arm or torso changes the next available counter. Make the contact, recoil and recovery readable. "
        "Do not impose boxing gloves, bare hands, clothing, new injuries or the removal of explicitly requested equipment."
    ),
    "weapons": (
        "WEAPONS: Choose techniques from the actual weapon's reach, grip, shape and momentum. A spear can "
        "compress its sliding grip for a shaft strike, then re-extend; a heavy weapon carries the body through "
        "a rebound; a shield-led entry opens the sword's line. Pick only relevant mechanics. Every recovery "
        "starts at the weapon's previous position, with identifiable ownership and grip. For long weapons, "
        "favor readable side or three-quarter framing when compatible with camera permissions. A flourish "
        "flows into an attack or defense; effects follow the real weapon path. Contact has a coherent parry, "
        "miss, displacement or requested physical consequence. No automatic injury or execution."
    ),
}

_CROWD_1_2_0 = (
    "If the intention requests one against several opponents, plan the protagonist's route before attacker "
    "entries. Overlap approach, attack, retreat and re-entry to sustain pressure; others can flank, recover "
    "or block exits. Usually one or two opponents reach close contact at once; this is not a ceiling on "
    "explicitly requested wide-area fantasy attacks. Obstacles channel access and redirect bodies. Carry "
    "displacement, imbalance and fallen opponents forward. Brief recovery beats maintain continuity; avoid "
    "a neutral reset after every move. For a duel, do not add a crowd."
)


def orientation_policy(settings: CombatSettings | None) -> str:
    if settings is None or settings.orientation is None:
        return ""
    return (
        "\n\nCOMBAT ORIENTATION 1.2.0 — " + _DIRECTIONS_1_2_0[settings.orientation]
        + "\n" + _CROWD_1_2_0
        + "\nExplicit intention and reference roles take priority. At decision stages choose the mechanics; "
        "writers preserve the approved plan, and revisions alter only what the user asks to change. "
        "Keep the saved action quantity, shot count, camera permissions and requested ending independent. "
        "Show speed through footwork, recoil and consequences on materials already present, not repeated "
        "speed adjectives or compulsory particles. Preserve the application's output and camera contracts."
    )
