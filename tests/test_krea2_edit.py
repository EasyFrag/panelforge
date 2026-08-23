import json
from pathlib import Path
import struct
import tempfile
import unittest
import zlib

from panelforge.application import (
    CompletionResult,
    CompletionStreamEvent,
    Krea2EditAttemptRequest,
    Krea2EditService,
    ModelDescriptor,
    StreamEventKind,
    StreamPhase,
)
from panelforge.application.krea2_edit import normalize_krea2_edit_prompt
from panelforge.domain import (
    Krea2AspectRatio,
    Krea2EditAttemptStatus,
    Krea2EditMetadata,
    Krea2EditSettings,
    Krea2EditSourceState,
    Krea2LoraSelection,
    Krea2PromptLanguage,
)
from panelforge.infrastructure.comfy import ComfyImageRef
from panelforge.infrastructure.krea2_image_metadata import recover_krea2_metadata
from panelforge.infrastructure.krea2_project_exports import LocalKrea2ProjectExporter
from panelforge.infrastructure.presets import load_krea2_edit_workflow
from panelforge.infrastructure.storage import LocalAssetStore, LocalKrea2EditStore


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / "workflows" / "image.edit" / "krea2-identity" / "0.1.0"
PNG = b"\x89PNG\r\n\x1a\n" + b"test"


class FakeGateway:
    def __init__(self, response="A detailed vertical studio image of the same adult subject, now shown full body with precise lighting and material continuity."):
        self.response = response
        self.requests = []

    def list_models(self):
        return (ModelDescriptor("Qwen3.8-27B"),)

    def stream(self, request):
        self.requests.append(request)
        result = CompletionResult(
            model_id=request.model_id,
            content=self.response,
            finish_reason="stop",
            call_id="call-edit",
        )
        yield CompletionStreamEvent(StreamEventKind.DELTA, StreamPhase.GENERATING, self.response)
        yield CompletionStreamEvent(StreamEventKind.COMPLETED, StreamPhase.COMPLETED, result=result)


class FakeOutcomes:
    def __init__(self):
        self.values = []

    def report_application_outcome(self, call_id, outcome, **kwargs):
        self.values.append((call_id, outcome.value, kwargs))


class FakeComfy:
    def __init__(self):
        self.workflow = None
        self.upload_filename = None

    def upload_image(self, content, *, filename, subfolder=""):
        self.upload_filename = filename
        return ComfyImageRef(filename, subfolder, "input")

    def submit_workflow(self, workflow):
        self.workflow = workflow
        return "execution-edit"

    def get_history(self, prompt_id):
        # SaveImageKJ may omit its image from history; the adapter must use the
        # deterministic prefix fallback already used by KREA2 Batch.
        return {
            prompt_id: {
                "status": {"completed": True, "status_str": "success"},
                "outputs": {},
            }
        }

    def download_output(self, *, filename, subfolder="", folder_type="output"):
        self.download = (filename, subfolder, folder_type)
        return PNG

    def cancel_execution(self, prompt_id):
        return None


class DeferredComfy(FakeComfy):
    def __init__(self):
        super().__init__()
        self.history = {}

    def get_history(self, prompt_id):
        return self.history

    def cancel_execution(self, prompt_id):
        action = type("Action", (), {"value": "already_finished"})()
        return type("Result", (), {"action": action})()


class FailingProjectExporter:
    def __init__(self, root: Path) -> None:
        self.root = root

    def export(self, stages, assets):
        raise OSError("external disk is offline")


class Krea2EditTest(unittest.TestCase):
    def test_metadata_recovers_prompt_model_ratio_seed_and_active_general_loras(self):
        graph = {
            "1": {"class_type": "CLIPTextEncode", "inputs": {"text": "short"}},
            "2": {"class_type": "Krea2EditGroundedEncode", "inputs": {"prompt": "A much longer detailed source prompt for the image."}},
            "3": {"class_type": "UNETLoader", "inputs": {"unet_name": "Krea2/kroma.safetensors"}},
            "4": {"class_type": "ResolutionSelector", "inputs": {"aspect_ratio": "9:16 (Portrait Widescreen)", "megapixels": 0.8}},
            "5": {"class_type": "KSampler", "inputs": {"seed": 123}},
            "6": {"class_type": "Power Lora Loader (rgthree)", "inputs": {
                "lora_1": {"on": True, "lora": "krea2/style.safetensors", "strength": 0.75},
                "lora_2": {"on": True, "lora": "krea2/krea2_identity_edit_v1_2.safetensors", "strength": 1},
            }},
        }
        metadata = recover_krea2_metadata(_png_with_text("prompt", json.dumps(graph)))
        self.assertEqual(metadata.prompt, "A much longer detailed source prompt for the image.")
        self.assertEqual(metadata.model_name, "Krea2/kroma.safetensors")
        self.assertEqual(metadata.aspect_ratio, Krea2AspectRatio.PORTRAIT_WIDESCREEN)
        self.assertEqual(metadata.megapixels, 0.8)
        self.assertEqual(metadata.seed, 123)
        self.assertEqual(metadata.loras, (Krea2LoraSelection("krea2/style.safetensors", 0.75),))

    def test_sidecar_is_authoritative_and_invalid_sidecar_falls_back_to_png(self):
        sidecar = json.dumps({
            "prompt": "Prompt from sidecar",
            "render": {
                "model_name": "Krea2/model.safetensors",
                "aspect_ratio": "2:3 (Portrait Photo)",
                "megapixels": 2.1,
                "seed": 42,
                "loras": [],
            },
        }).encode()
        metadata = recover_krea2_metadata(PNG, sidecar=sidecar)
        self.assertEqual(metadata.origin, "sidecar")
        self.assertEqual(metadata.prompt, "Prompt from sidecar")

    def test_metadata_recovers_flat_rgthree_lora_stack_used_by_assisted_creation(self):
        graph = {
            "1": {
                "class_type": "Lora Loader Stack (rgthree)",
                "inputs": {
                    "lora_01": "krea2/realism.safetensors",
                    "strength_01": 1.0,
                    "lora_02": "krea2/detailer.safetensors",
                    "strength_02": 2.0,
                    "lora_03": "None",
                    "strength_03": 0.0,
                },
            },
        }
        metadata = recover_krea2_metadata(_png_with_text("prompt", json.dumps(graph)))
        self.assertEqual(
            metadata.loras,
            (
                Krea2LoraSelection("krea2/realism.safetensors", 1.0),
                Krea2LoraSelection("krea2/detailer.safetensors", 2.0),
            ),
        )

    def test_legacy_source_storage_is_loaded_as_a_single_stage_project(self):
        with tempfile.TemporaryDirectory() as workspace:
            assets = LocalAssetStore(workspace)
            asset = assets.create(PNG, media_type="image/png")
            store = LocalKrea2EditStore(workspace)
            service = Krea2EditService(
                gateway=FakeGateway(),
                workflow=load_krea2_edit_workflow(WORKFLOW),
                comfy=FakeComfy(),
                assets=assets,
                sources=store,
            )
            source = service.add_source(
                asset_id=asset.asset_id,
                filename="legacy.png",
                metadata=Krea2EditMetadata(origin="none"),
            )
            path = Path(workspace) / "krea2_edits" / source.source_id / "source.json"
            raw = json.loads(path.read_text(encoding="utf-8"))
            raw["schema_version"] = 1
            for key in (
                "project_id",
                "stage_index",
                "parent_source_id",
                "parent_attempt_id",
                "accepted_attempt_id",
                "revisions",
                "prompt_language",
            ):
                raw.pop(key)
            path.write_text(json.dumps(raw), encoding="utf-8")

            loaded = store.get(source.source_id)

            self.assertEqual(loaded.project_id, loaded.source_id)
            self.assertEqual(loaded.stage_index, 1)
            self.assertEqual(loaded.revisions, ())
            self.assertIs(loaded.prompt_language, Krea2PromptLanguage.ENGLISH)

    def test_recipe_compiles_only_exposed_variables_and_keeps_technical_stack_fixed(self):
        workflow = load_krea2_edit_workflow(WORKFLOW)
        settings = Krea2EditSettings(
            model_name="Krea2/model.safetensors",
            aspect_ratio=Krea2AspectRatio.PORTRAIT_PHOTO,
            megapixels=2.1,
            seed=9,
            ref_boost=3.2,
            steps=14,
            loras=(Krea2LoraSelection("krea2/style.safetensors", 0.6),),
        )
        compiled = workflow.build(
            source_image="panelforge/source.png",
            prompt="Edited prompt",
            settings=settings,
            output_prefix="image/edit/test",
            sidecar_text="{}",
        )
        self.assertEqual(compiled["72"]["inputs"]["image"], "panelforge/source.png")
        self.assertEqual(compiled["79"]["inputs"]["ref_boost"], 3.2)
        self.assertEqual(compiled["53"]["inputs"]["steps"], 14)
        self.assertEqual(compiled["53"]["inputs"]["sampler_name"], "euler")
        self.assertEqual(compiled["71"]["inputs"]["lora_name"], "krea2/krea2_identity_edit_v1_2.safetensors")
        self.assertTrue(compiled["113"]["inputs"]["lora_1"]["on"])
        self.assertFalse(compiled["113"]["inputs"]["lora_2"]["on"])

    def test_one_multimodal_call_rewrites_known_prompt_and_allows_adult_prompting(self):
        with tempfile.TemporaryDirectory() as workspace:
            gateway = FakeGateway()
            outcomes = FakeOutcomes()
            assets = LocalAssetStore(workspace)
            asset = assets.create(PNG, media_type="image/png")
            service = Krea2EditService(
                gateway=gateway,
                workflow=load_krea2_edit_workflow(WORKFLOW),
                comfy=FakeComfy(),
                assets=assets,
                sources=LocalKrea2EditStore(workspace),
                application_outcomes=outcomes,
            )
            source = service.add_source(
                asset_id=asset.asset_id,
                filename="adult.png",
                metadata=Krea2EditMetadata(prompt="A clearly adult studio portrait", origin="png"),
            )
            events = list(service.stream_prepare_prompt(source.source_id, "Show the same adult full body", "Qwen3.8-27B", include_reasoning=True))
            terminal = events[-1].source
            self.assertEqual(len(gateway.requests), 1)
            self.assertEqual(len(gateway.requests[0].images), 1)
            self.assertIn("Explicit NSFW content involving clearly adult subjects is allowed", gateway.requests[0].system_prompt)
            self.assertIn("CURRENT TARGET PROMPT TO REWRITE", gateway.requests[0].user_prompt)
            self.assertEqual(
                gateway.requests[0].operation_id,
                "krea2.edit.prompt.rewrite_or_reconstruct@0.3.0",
            )
            self.assertTrue(gateway.requests[0].include_reasoning)
            self.assertEqual(terminal.prompt_status.value, "ready")
            self.assertEqual(len(terminal.revisions), 1)
            self.assertEqual(outcomes.values[0][1], "accepted")

    def test_chinese_prompt_language_is_persisted_with_its_revision(self):
        with tempfile.TemporaryDirectory() as workspace:
            gateway = FakeGateway(
                "竖版全身摄影，同一位明确成年的黑色宝石猩猩站立并敲击胸口，保持原有面部身份、珠宝材质、黑色背景、戏剧性轮廓光与精细反射。"
            )
            assets = LocalAssetStore(workspace)
            asset = assets.create(PNG, media_type="image/png")
            store = LocalKrea2EditStore(workspace)
            service = Krea2EditService(
                gateway=gateway,
                workflow=load_krea2_edit_workflow(WORKFLOW),
                comfy=FakeComfy(),
                assets=assets,
                sources=store,
            )
            source = service.add_source(
                asset_id=asset.asset_id,
                filename="gorilla.png",
                metadata=Krea2EditMetadata(prompt="A black jeweled gorilla", origin="png"),
            )

            terminal = list(service.stream_prepare_prompt(
                source.source_id,
                "Montre-le en pied",
                "Qwen3.8-27B",
                prompt_language=Krea2PromptLanguage.CHINESE_SIMPLIFIED,
            ))[-1].source

            self.assertIs(terminal.prompt_language, Krea2PromptLanguage.CHINESE_SIMPLIFIED)
            self.assertIs(terminal.revisions[-1].prompt_language, Krea2PromptLanguage.CHINESE_SIMPLIFIED)
            self.assertIn("TARGET PROMPT LANGUAGE: Simplified Chinese", gateway.requests[-1].user_prompt)
            self.assertIs(store.get(source.source_id).prompt_language, Krea2PromptLanguage.CHINESE_SIMPLIFIED)

    def test_chinese_prompt_normalization_removes_only_a_short_intro(self):
        prompt = "同一位成年主体站在完整的竖版画面中，保持身份、服装、材质、背景、光线和色彩连续，仅将月亮改为蓝色并同步水面反射。"
        self.assertEqual(
            normalize_krea2_edit_prompt(
                f"以下是最终KREA2图像编辑提示词：\n{prompt}",
                Krea2PromptLanguage.CHINESE_SIMPLIFIED,
            ),
            prompt,
        )

    def test_prompt_iteration_uses_edited_prompt_and_generated_feedback_without_changing_stage_source(self):
        with tempfile.TemporaryDirectory() as workspace:
            gateway = FakeGateway()
            comfy = FakeComfy()
            assets = LocalAssetStore(workspace)
            asset = assets.create(PNG, media_type="image/png")
            service = Krea2EditService(
                gateway=gateway,
                workflow=load_krea2_edit_workflow(WORKFLOW),
                comfy=comfy,
                assets=assets,
                sources=LocalKrea2EditStore(workspace),
                poll_interval=0.001,
            )
            source = service.add_source(
                asset_id=asset.asset_id,
                filename="moon.png",
                metadata=Krea2EditMetadata(prompt="A white moon above a beach", origin="png"),
            )
            settings = Krea2EditSettings(
                model_name="Krea2/model.safetensors",
                aspect_ratio=Krea2AspectRatio.PORTRAIT_WIDESCREEN,
                megapixels=1.0,
                seed=11,
            )
            source = service.prepare_attempt(
                source.source_id,
                Krea2EditAttemptRequest(
                    "A detailed violet moon above the same beach with coherent reflections and preserved framing.",
                    settings,
                ),
            )
            attempt = source.attempts[-1]
            service.queue_attempt(source.source_id, attempt.attempt_id)
            source = service.execute_attempt(source.source_id, attempt.attempt_id)
            feedback = source.attempts[-1]

            terminal = list(
                service.stream_prepare_prompt(
                    source.source_id,
                    "Make the violet reflection consistent in the water",
                    "Qwen3.8-27B",
                    base_prompt="MANUALLY EDITED CURRENT PROMPT",
                    feedback_attempt_id=feedback.attempt_id,
                )
            )[-1].source

            request = gateway.requests[-1]
            self.assertIn("MANUALLY EDITED CURRENT PROMPT", request.user_prompt)
            self.assertIn("The next render still starts from STAGE SOURCE", request.user_prompt)
            self.assertEqual([image.label for image in request.images], ["STAGE SOURCE", "GENERATED FEEDBACK"])
            self.assertEqual(terminal.source_asset_id, asset.asset_id)
            self.assertEqual(terminal.revisions[-1].base_prompt, "MANUALLY EDITED CURRENT PROMPT")
            self.assertEqual(terminal.revisions[-1].feedback_attempt_id, feedback.attempt_id)

    def test_promoting_a_successful_attempt_creates_the_next_stage_in_the_same_project(self):
        with tempfile.TemporaryDirectory() as workspace:
            ids = iter(("project-root", "project-stage-2"))
            comfy = FakeComfy()
            assets = LocalAssetStore(workspace)
            asset = assets.create(PNG, media_type="image/png")
            store = LocalKrea2EditStore(workspace)
            service = Krea2EditService(
                gateway=FakeGateway(),
                workflow=load_krea2_edit_workflow(WORKFLOW),
                comfy=comfy,
                assets=assets,
                sources=store,
                project_exporter=LocalKrea2ProjectExporter(
                    Path(workspace) / "KREA2 Projects"
                ),
                source_id_factory=lambda: next(ids),
                poll_interval=0.001,
            )
            source = service.add_source(
                asset_id=asset.asset_id,
                filename="moon.png",
                metadata=Krea2EditMetadata(origin="none"),
            )
            settings = Krea2EditSettings(
                model_name="Krea2/model.safetensors",
                aspect_ratio=Krea2AspectRatio.PORTRAIT_WIDESCREEN,
                megapixels=1.0,
                seed=12,
            )
            source = service.prepare_attempt(
                source.source_id,
                Krea2EditAttemptRequest(
                    "A detailed violet moon above the same beach with coherent reflections and preserved framing.",
                    settings,
                ),
            )
            attempt = source.attempts[-1]
            service.queue_attempt(source.source_id, attempt.attempt_id)
            source = service.execute_attempt(source.source_id, attempt.attempt_id)
            succeeded = source.attempts[-1]

            child = service.promote_attempt(
                source.source_id,
                succeeded.attempt_id,
                project_name="Projet lune",
                step_name="Reflet violet",
            )
            parent = service.get(source.source_id)

            self.assertEqual(parent.state.value, "advanced")
            self.assertEqual(parent.accepted_attempt_id, succeeded.attempt_id)
            self.assertEqual(parent.project_name, "Projet lune")
            self.assertEqual(parent.accepted_label, "Reflet violet")
            self.assertEqual(child.project_id, parent.source_id)
            self.assertEqual(child.stage_index, 2)
            self.assertEqual(child.parent_source_id, parent.source_id)
            self.assertEqual(child.parent_attempt_id, succeeded.attempt_id)
            self.assertEqual(child.source_asset_id, succeeded.output_asset_id)
            self.assertEqual(child.generated_prompt, succeeded.prompt)
            self.assertEqual(child.project_name, "Projet lune")
            self.assertIsNone(child.export_error)
            self.assertTrue(Path(child.export_path).is_dir())
            self.assertEqual(store.get(child.source_id), child)

            service.set_state(child.source_id, Krea2EditSourceState.PROCESSED)
            project = [value for value in service.list(include_hidden=True) if value.project_id == parent.project_id]
            self.assertEqual({value.state.value for value in project}, {"processed"})

    def test_export_failure_does_not_undo_validation_and_can_be_retried(self):
        with tempfile.TemporaryDirectory() as workspace:
            ids = iter(("project-root", "project-stage-2"))
            comfy = FakeComfy()
            assets = LocalAssetStore(workspace)
            asset = assets.create(PNG, media_type="image/png")
            service = Krea2EditService(
                gateway=FakeGateway(),
                workflow=load_krea2_edit_workflow(WORKFLOW),
                comfy=comfy,
                assets=assets,
                sources=LocalKrea2EditStore(workspace),
                project_exporter=FailingProjectExporter(Path(workspace) / "offline"),
                source_id_factory=lambda: next(ids),
                poll_interval=0.001,
            )
            source = service.add_source(
                asset_id=asset.asset_id,
                filename="moon.png",
                metadata=Krea2EditMetadata(origin="none"),
            )
            settings = Krea2EditSettings(
                model_name="Krea2/model.safetensors",
                aspect_ratio=Krea2AspectRatio.SQUARE,
                megapixels=1.0,
                seed=12,
            )
            source = service.prepare_attempt(
                source.source_id,
                Krea2EditAttemptRequest(
                    "A detailed violet moon above the same beach with coherent reflections.",
                    settings,
                ),
            )
            attempt = source.attempts[-1]
            service.queue_attempt(source.source_id, attempt.attempt_id)
            source = service.execute_attempt(source.source_id, attempt.attempt_id)

            child = service.promote_attempt(
                source.source_id,
                source.attempts[-1].attempt_id,
                project_name="Projet lune",
                step_name="Lune violette",
            )

            parent = service.get(source.source_id)
            self.assertEqual(parent.state, Krea2EditSourceState.ADVANCED)
            self.assertEqual(child.stage_index, 2)
            self.assertIsNone(child.export_path)
            self.assertIn("external disk is offline", child.export_error)
            retried = service.retry_project_export(child.source_id)
            self.assertEqual(retried.source_id, child.source_id)
            self.assertIn("external disk is offline", retried.export_error)

    def test_repeated_render_attempt_uses_no_llm_and_imports_prefix_fallback(self):
        with tempfile.TemporaryDirectory() as workspace:
            gateway = FakeGateway()
            comfy = FakeComfy()
            assets = LocalAssetStore(workspace)
            asset = assets.create(PNG, media_type="image/png")
            service = Krea2EditService(
                gateway=gateway,
                workflow=load_krea2_edit_workflow(WORKFLOW),
                comfy=comfy,
                assets=assets,
                sources=LocalKrea2EditStore(workspace),
                poll_interval=0.001,
            )
            source = service.add_source(
                asset_id=asset.asset_id,
                filename="source.png",
                metadata=Krea2EditMetadata(origin="none"),
            )
            settings = Krea2EditSettings(
                model_name="Krea2/kroma-v0.2-turbo.safetensors",
                aspect_ratio=Krea2AspectRatio.PORTRAIT_WIDESCREEN,
                megapixels=1.0,
                seed=5,
            )
            source = service.prepare_attempt(source.source_id, Krea2EditAttemptRequest("A sufficiently detailed edited prompt that preserves the source identity and changes the pose.", settings))
            attempt = source.attempts[-1]
            service.queue_attempt(source.source_id, attempt.attempt_id)
            terminal = service.execute_attempt(source.source_id, attempt.attempt_id)
            self.assertEqual(len(gateway.requests), 0)
            self.assertEqual(terminal.attempts[-1].status, Krea2EditAttemptStatus.SUCCEEDED)
            self.assertEqual(comfy.download[0], f"{attempt.attempt_id}_00001_.png")
            self.assertEqual(comfy.workflow["72"]["inputs"]["image"], f"panelforge/krea2-edit/{source.source_id}.png")

    def test_detached_success_is_reconciled_and_frees_the_render_slot(self):
        with tempfile.TemporaryDirectory() as workspace:
            comfy = FakeComfy()
            assets = LocalAssetStore(workspace)
            asset = assets.create(PNG, media_type="image/png")
            store = LocalKrea2EditStore(workspace)
            service = Krea2EditService(
                gateway=FakeGateway(),
                workflow=load_krea2_edit_workflow(WORKFLOW),
                comfy=comfy,
                assets=assets,
                sources=store,
                poll_interval=0.001,
            )
            source = service.add_source(
                asset_id=asset.asset_id,
                filename="source.png",
                metadata=Krea2EditMetadata(origin="none"),
            )
            settings = Krea2EditSettings(
                model_name="Krea2/model.safetensors",
                aspect_ratio=Krea2AspectRatio.SQUARE,
                megapixels=1.0,
                seed=1,
            )
            source = service.prepare_attempt(
                source.source_id,
                Krea2EditAttemptRequest(
                    "A sufficiently detailed edit prompt preserving the source while changing the visible pose and camera framing.",
                    settings,
                ),
            )
            queued = source.attempts[-1].queue()
            running = queued.start("detached-execution", "0" * 64)
            store.save(source.replace_attempt(running))

            recovered = service.get(source.source_id)

            self.assertEqual(
                recovered.attempts[-1].status,
                Krea2EditAttemptStatus.SUCCEEDED,
            )
            self.assertIsNotNone(recovered.attempts[-1].output_asset_id)

    def test_source_upload_keeps_the_real_image_extension(self):
        with tempfile.TemporaryDirectory() as workspace:
            comfy = FakeComfy()
            assets = LocalAssetStore(workspace)
            asset = assets.create(b"\xff\xd8\xffsource", media_type="image/jpeg")
            service = Krea2EditService(
                gateway=FakeGateway(),
                workflow=load_krea2_edit_workflow(WORKFLOW),
                comfy=comfy,
                assets=assets,
                sources=LocalKrea2EditStore(workspace),
                poll_interval=0.001,
            )
            source = service.add_source(
                asset_id=asset.asset_id,
                filename="source.jpg",
                metadata=Krea2EditMetadata(origin="none"),
            )
            settings = Krea2EditSettings(
                model_name="Krea2/model.safetensors",
                aspect_ratio=Krea2AspectRatio.SQUARE,
                megapixels=1.0,
                seed=2,
            )
            source = service.prepare_attempt(
                source.source_id,
                Krea2EditAttemptRequest(
                    "A sufficiently detailed edit prompt preserving the source while changing the visible pose and camera framing.",
                    settings,
                ),
            )
            service.queue_attempt(source.source_id, source.attempts[-1].attempt_id)
            service.execute_attempt(source.source_id, source.attempts[-1].attempt_id)

            self.assertTrue(comfy.upload_filename.endswith(".jpg"))

    def test_already_finished_cancel_waits_for_history_then_recovers_output(self):
        with tempfile.TemporaryDirectory() as workspace:
            comfy = DeferredComfy()
            assets = LocalAssetStore(workspace)
            asset = assets.create(PNG, media_type="image/png")
            store = LocalKrea2EditStore(workspace)
            service = Krea2EditService(
                gateway=FakeGateway(),
                workflow=load_krea2_edit_workflow(WORKFLOW),
                comfy=comfy,
                assets=assets,
                sources=store,
                poll_interval=0.001,
            )
            source = service.add_source(
                asset_id=asset.asset_id,
                filename="source.png",
                metadata=Krea2EditMetadata(origin="none"),
            )
            settings = Krea2EditSettings(
                model_name="Krea2/model.safetensors",
                aspect_ratio=Krea2AspectRatio.SQUARE,
                megapixels=1.0,
                seed=3,
            )
            source = service.prepare_attempt(
                source.source_id,
                Krea2EditAttemptRequest(
                    "A sufficiently detailed edit prompt preserving the source while changing the visible pose and camera framing.",
                    settings,
                ),
            )
            running = source.attempts[-1].queue().start(
                "finished-execution",
                "0" * 64,
            )
            store.save(source.replace_attempt(running))

            pending = service.cancel_attempt(source.source_id, running.attempt_id)

            self.assertEqual(
                pending.attempts[-1].status,
                Krea2EditAttemptStatus.CANCEL_PENDING,
            )
            comfy.history = {
                "finished-execution": {
                    "status": {"completed": True, "status_str": "success"},
                    "outputs": {},
                }
            }
            recovered = service.get(source.source_id)
            self.assertEqual(
                recovered.attempts[-1].status,
                Krea2EditAttemptStatus.SUCCEEDED,
            )


def _png_with_text(key: str, value: str) -> bytes:
    data = key.encode("latin-1") + b"\0" + value.encode("latin-1")
    chunk = struct.pack(">I", len(data)) + b"tEXt" + data
    chunk += struct.pack(">I", zlib.crc32(b"tEXt" + data) & 0xFFFFFFFF)
    end = struct.pack(">I", 0) + b"IEND" + struct.pack(">I", zlib.crc32(b"IEND") & 0xFFFFFFFF)
    return b"\x89PNG\r\n\x1a\n" + chunk + end


if __name__ == "__main__":
    unittest.main()
