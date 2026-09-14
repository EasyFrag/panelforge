"""Version-pinned Combat revision prompts; no dependency on Classic creative rules."""

from .prompt_recipe_text import prompt_text
from dataclasses import dataclass
from panelforge.domain.video_preparation import VideoPreparationRef


def combat_audacity_policy(level: int, preparation: VideoPreparationRef) -> str:
    if preparation.is_combat and preparation.version in {"1.1.0", "1.1.1", "1.2.0", "1.3.0"}:
        if type(level) is not int or not 0 <= level <= 3:
            raise ValueError("unsupported Combat audacity level")
        return (f"COMBAT AUDACITY {preparation.version}: {level}/3. " + (
            prompt_text('combat_preparation.combat_audacity_policy.01', 'Invent the techniques needed for the requested encounter, within its established style.'),
            prompt_text('combat_preparation.combat_audacity_policy.02', 'Allow restrained tactical invention within the established styles.'),
            prompt_text('combat_preparation.combat_audacity_policy.03', 'Allow memorable tactical reversals and inventive use of established abilities and surroundings.'),
            prompt_text('combat_preparation.combat_audacity_policy.04', 'Allow ambitious tactical ideas and unexpected coherent combinations within the requested genre.'),
        )[level] + prompt_text('combat_preparation.combat_audacity_policy.05', ' Audacity controls invention, not quantity of action or number of shots. Preserve identities, requested outcome and permissions. It never requires new magic, gore, glow or camera moves.'))
    if preparation != VideoPreparationRef("combat", "1.0.0") or type(level) is not int or not 0 <= level <= 3:
        raise ValueError("unsupported Combat audacity policy")
    return (
        prompt_text('combat_preparation.combat_audacity_policy.06', 'COMBAT AUDACITY 1.0.0: {value1}/3. ', value1=level)
        + (
            prompt_text('combat_preparation.combat_audacity_policy.07', 'Translate the requested encounter faithfully; infer only necessary defense, contact, recoil and recovery.'),
            prompt_text('combat_preparation.combat_audacity_policy.08', 'You may add a restrained tactical variation that clarifies the requested exchange.'),
            prompt_text('combat_preparation.combat_audacity_policy.09', 'You may develop a memorable attack/counterattack combination within the permitted axes.'),
            prompt_text('combat_preparation.combat_audacity_policy.10', 'You may propose a strong reversal of initiative or an ambitious coherent combination within the permitted axes.'),
        )[level]
        + prompt_text('combat_preparation.combat_audacity_policy.11', ' These are permissions, not quotas. Preserve the requested outcome, characters, weapons and genre. Necessary defensive reactions are part of the fight, not optional extra events. Audacity alone never requests glow, energy pulses, gore, slow motion or camera changes.')
    )


def combat_freedom_policy(axes, preparation: VideoPreparationRef) -> str:
    if preparation.is_combat and preparation.version in {"1.1.0", "1.1.1", "1.2.0", "1.3.0"}:
        from .vocal_policy import vocal_policy
        return (prompt_text('combat_preparation.combat_freedom_policy.01', 'COMBAT PERMISSIONS {value1}: scene life {value2}/3; camera {value3}/3; secondary activity {value4}/3. 0 no unsolicited additions, 1 restrained, 2 clear, 3 broad compatible initiative. The separate saved ACTION QUANTITY controls the principal fighters, including necessary defenses and recovery. Secondary activity never limits those combinations. SHOT COUNT controls cuts independently of camera motion; camera 0 can still use the chosen number of static shots. Explicit camera requests remain allowed. ', value1=preparation.version, value2=axes.scene_life, value3=axes.camera, value4=axes.extra_motion)
            + vocal_policy(axes.dialogue))
    if preparation != VideoPreparationRef("combat", "1.0.0"):
        raise ValueError("unsupported Combat freedom policy")
    from .vocal_policy import vocal_policy
    return (
        prompt_text('combat_preparation.combat_freedom_policy.02', 'COMBAT PERMISSIONS 1.0.0. Scene life {value1}/3; camera {value2}/3; additional choreography {value3}/3. Zero forbids unsolicited additions on that axis; 1 allows restrained details, 2 allows clearly perceptible compatible choices, 3 allows broader coherent initiative. Permissions are not quotas and never override explicit instructions or reference ownership. A request for combat already permits the necessary attack, defense, contact, recoil and recovery: do not collapse the encounter into one gesture because additional motion is zero. Extra choreography expands tactics only when permitted; do not change the requested winner. Camera changes obey the camera axis and the selected shot structure independently of the number of exchanges. ', value1=axes.scene_life, value2=axes.camera, value3=axes.extra_motion)
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
