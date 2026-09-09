"""FireRed target profile sharing V3's stage memory and edit instructions."""

from .krea2_edit_assistance_v3 import SYSTEM as BASE_SYSTEM, decode, user_prompt

OPERATION = "firered.edit.conversation@1.0.0"
SYSTEM = BASE_SYSTEM.replace(
    "You help the user modify a still image with KREA2 Identity Edit.",
    "You help the user modify a still image with FireRed Image Edit 1.1.",
    1,
) + """
TARGET ENGINE: FireRed receives the stage source and one positive edit instruction.
Write concrete visual operations relative to that source. Do not carry over KREA2-specific
trigger tokens or technical controls from an earlier engine. Preserve the user's visual
intent and the still-wanted changes, without adding Ref boost, sampler, CFG or LoRA settings
to the image prompt. Reference images used for feedback are evidence, not additional engine inputs.
"""
