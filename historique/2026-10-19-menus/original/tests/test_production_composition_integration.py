import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from panelforge.application.production import ProductionService
from panelforge.domain import ProductionJob, ProductionStage, ProductionStatus
from tests.test_direct_fl2va_composition import configured_service
from tests.test_h3_base_motion_v3 import late_anchor_motion_plan
from tests.test_production import (
    FakeGateway,
    FakeH3,
    FakeKrea,
    MemoryAssets,
    MemoryJobs,
    SafeThermal,
    config,
)


FINAL_PROMPT = """integrated_multimodal_description:
[Shot 1] The target video is one continuous 8-second shot. At 00:00.000, the player begins exactly from the visible starting pose on the warm indoor court. Throughout the entire shot, the player moves continuously through one controlled kick while the ball accelerates toward the net; body balance, uniform fabric and the net keep responding naturally. At 00:08.000, at the cut instant, the player is still regaining balance while the net continues moving. The video ends during the same ongoing motion without a pause, freeze or held pose.
overall_soundscape:
Continuous indoor court ambience, measured footwork, one ball impact and the moving net.
non_diegetic_music:
N/A"""


class ProductionCompositionIntegrationTest(unittest.TestCase):
    def test_production_approves_the_real_h3_plan_before_the_final_writer(self):
        with tempfile.TemporaryDirectory() as directory:
            composition, gateway = configured_service(
                directory,
                ("first_frame",),
                source_text="Plan unique de 8 secondes.",
                profile_version="0.3.3",
                cookbook_version="0.3.3",
            )

            def content(request):
                if request.operation_id == "action_plan.generate":
                    return json.dumps(late_anchor_motion_plan())
                return FINAL_PROMPT

            gateway._content = content
            assets = MemoryAssets()
            jobs = MemoryJobs()
            h3 = FakeH3(assets)
            service = ProductionService(
                gateway=FakeGateway(),
                assets=assets,
                jobs=jobs,
                krea2=FakeKrea(assets),
                prompt_lab=SimpleNamespace(get_session=composition.sessions.get),
                composition=composition,
                h3_render=h3,
                thermal_monitor=SafeThermal(),
                monitor_interval=0.001,
            )
            job = ProductionJob(
                job_id="production-real-composition",
                name="Real composition",
                intention="The player kicks the ball and keeps moving.",
                source_asset_id="source",
                source_filename="source.png",
                config=config(),
                status=ProductionStatus.RUNNING,
                stage=ProductionStage.H3_PROMPT,
                krea_project_id="krea-project",
                krea_attempt_ids=("image-1",),
                selected_image_attempt_id="image-1",
                selected_image_asset_id="source",
                image_review_approved=True,
                prompt_session_id="h3-base-session",
            )
            jobs.create(job)

            result = service._build_h3_prompt(job)

            persisted = composition.get("h3-base-session")
            self.assertEqual(result.stage, ProductionStage.VIDEO_PREVIEW)
            self.assertEqual(
                persisted.beat_sheet.approved_revision_id,
                persisted.beat_sheet.active_revision_id,
            )
            self.assertEqual(
                persisted.final_prompt.approved_revision_id,
                persisted.final_prompt.active_revision_id,
            )
            self.assertEqual(
                [request.operation_id for request in gateway.requests],
                ["action_plan.generate", "final_prompt.generate"],
            )


if __name__ == "__main__":
    unittest.main()
