from pathlib import Path
import sys
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from panelforge.domain import (
    ProductionLoraChoice,
    ProductionLoraChoiceSource,
    ProductionLoraPlan,
)
from panelforge.infrastructure.storage import LocalProductionLoraMemory


class LocalProductionLoraMemoryTest(unittest.TestCase):
    def test_declared_knowledge_hypotheses_and_observations_remain_distinct(self):
        with tempfile.TemporaryDirectory() as root:
            memory = LocalProductionLoraMemory(root)
            memory.set_declared_profile(
                "krea2/cinematic.safetensors",
                effects=("cinematic contrast",),
                trigger_terms=("cinematic lighting",),
                recommended_strength=1.0,
                compatible_checkpoints=("Krea2/model.safetensors",),
                warnings=("May crush shadows above 1.5",),
            )
            plan = ProductionLoraPlan(
                choices=(ProductionLoraChoice(
                    name="krea2/cinematic.safetensors",
                    strength=1.25,
                    source=ProductionLoraChoiceSource.MODEL,
                    expected_effect="Increase contrast while keeping the face readable.",
                ),),
                rationale="The scene needs a stronger light hierarchy.",
            )
            memory.record_plan(
                job_id="job-1",
                checkpoint="Krea2/model.safetensors",
                plan=plan,
                timestamp="2026-08-30T12:00:00Z",
            )
            memory.record_observation(
                job_id="job-1",
                attempt_id="attempt-2",
                checkpoint="Krea2/model.safetensors",
                prompt="A cinematic spectral portrait with controlled highlights.",
                seed=42,
                plan=plan,
                score=91,
                selection="model_recommended",
                timestamp="2026-08-30T12:01:00Z",
            )

            context = LocalProductionLoraMemory(root).context(("krea2/cinematic.safetensors",))[0]

            self.assertEqual(context["declared_effects"], ["cinematic contrast"])
            self.assertEqual(context["recommended_strength"], 1.0)
            self.assertEqual(context["model_hypotheses"][0]["confidence"], "hypothesis")
            self.assertEqual(context["recent_observations"][0]["confidence"], "low_observational")
            self.assertEqual(context["recent_observations"][0]["score"], 91)

    def test_observational_memory_can_be_isolated_by_profile(self):
        with tempfile.TemporaryDirectory() as root:
            memory = LocalProductionLoraMemory(root)
            plan = ProductionLoraPlan(
                choices=(ProductionLoraChoice(
                    name="wetness.safetensors", strength=0.5,
                    source=ProductionLoraChoiceSource.MODEL,
                    expected_effect="Wet surface detail.",
                ),),
                rationale="Controlled comparison.",
            )
            for profile_id, selection in (("sfw", "like"), ("nsfw", "dislike")):
                memory.record_plan(
                    job_id=f"job-{profile_id}", checkpoint="Krea2/model.safetensors",
                    plan=plan, profile_id=profile_id,
                )
                memory.record_observation(
                    job_id=f"job-{profile_id}", attempt_id=f"attempt-{profile_id}",
                    checkpoint="Krea2/model.safetensors", prompt="A wet portrait.", seed=42,
                    plan=plan, score=None, selection=selection, profile_id=profile_id,
                )

            sfw = memory.context(("wetness.safetensors",), profile_id="sfw")[0]
            nsfw = memory.context(("wetness.safetensors",), profile_id="nsfw")[0]
            self.assertEqual([item["selection"] for item in sfw["recent_observations"]], ["like"])
            self.assertEqual([item["selection"] for item in nsfw["recent_observations"]], ["dislike"])
            self.assertEqual({item["profile_id"] for item in sfw["model_hypotheses"]}, {"sfw"})


if __name__ == "__main__":
    unittest.main()
