"""Version-pinned Combat revision prompts; no dependency on Classic creative rules."""
from dataclasses import dataclass
from panelforge.domain.video_preparation import VideoPreparationRef


def combat_audacity_policy(level: int, preparation: VideoPreparationRef) -> str:
    if preparation.is_combat and preparation.version in {"1.1.0", "1.1.1", "1.2.0", "1.3.0"}:
        if type(level) is not int or not 0 <= level <= 3:
            raise ValueError("unsupported Combat audacity level")
        return (f"COMBAT AUDACITY {preparation.version}: {level}/3. " + (
            "Invent the techniques needed for the requested encounter, within its established style.",
            "Allow restrained tactical invention within the established styles.",
            "Allow memorable tactical reversals and inventive use of established abilities and surroundings.",
            "Allow ambitious tactical ideas and unexpected coherent combinations within the requested genre.",
        )[level] + " Audacity controls invention, not quantity of action or number of shots. "
        "Preserve identities, requested outcome and permissions. It never requires new magic, gore, glow or camera moves.")
    if preparation != VideoPreparationRef("combat", "1.0.0") or type(level) is not int or not 0 <= level <= 3:
        raise ValueError("unsupported Combat audacity policy")
    return (
        f"COMBAT AUDACITY 1.0.0: {level}/3. "
        + (
            "Translate the requested encounter faithfully; infer only necessary defense, contact, recoil and recovery.",
            "You may add a restrained tactical variation that clarifies the requested exchange.",
            "You may develop a memorable attack/counterattack combination within the permitted axes.",
            "You may propose a strong reversal of initiative or an ambitious coherent combination within the permitted axes.",
        )[level]
        + " These are permissions, not quotas. Preserve the requested outcome, characters, weapons and genre. "
        "Necessary defensive reactions are part of the fight, not optional extra events. "
        "Audacity alone never requests glow, energy pulses, gore, slow motion or camera changes."
    )


def combat_freedom_policy(axes, preparation: VideoPreparationRef) -> str:
    if preparation.is_combat and preparation.version in {"1.1.0", "1.1.1", "1.2.0", "1.3.0"}:
        from .vocal_policy import vocal_policy
        return (f"COMBAT PERMISSIONS {preparation.version}: scene life {axes.scene_life}/3; camera {axes.camera}/3; "
            f"secondary activity {axes.extra_motion}/3. 0 no unsolicited additions, 1 restrained, 2 clear, 3 broad compatible initiative. "
            "The separate saved ACTION QUANTITY controls the principal fighters, including necessary defenses and recovery. "
            "Secondary activity never limits those combinations. SHOT COUNT controls cuts independently of camera motion; "
            "camera 0 can still use the chosen number of static shots. Explicit camera requests remain allowed. "
            + vocal_policy(axes.dialogue))
    if preparation != VideoPreparationRef("combat", "1.0.0"):
        raise ValueError("unsupported Combat freedom policy")
    from .vocal_policy import vocal_policy
    return (
        f"COMBAT PERMISSIONS 1.0.0. Scene life {axes.scene_life}/3; camera {axes.camera}/3; "
        f"additional choreography {axes.extra_motion}/3. Zero forbids unsolicited additions on that axis; "
        "1 allows restrained details, 2 allows clearly perceptible compatible choices, 3 allows broader coherent initiative. "
        "Permissions are not quotas and never override explicit instructions or reference ownership. "
        "A request for combat already permits the necessary attack, defense, contact, recoil and recovery: "
        "do not collapse the encounter into one gesture because additional motion is zero. "
        "Extra choreography expands tactics only when permitted; do not change the requested winner. "
        "Camera changes obey the camera axis and the selected shot structure independently of the number of exchanges. "
        + vocal_policy(axes.dialogue)
    )


@dataclass(frozen=True, slots=True)
class CombatRevisionPolicy:
    preparation: VideoPreparationRef
    system_prompt: str
    audacity_prompt: str

    def __post_init__(self) -> None:
        if not self.preparation.is_combat or not self.system_prompt.strip() or not self.audacity_prompt.strip():
            raise ValueError("invalid Combat revision policy")
