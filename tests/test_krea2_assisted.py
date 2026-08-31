import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from panelforge.application import (
    CompletionResult,
    CompletionStreamEvent,
    Krea2AssistedService,
    ModelDescriptor,
    StreamEventKind,
    StreamPhase,
)
from panelforge.domain import (
    Krea2AspectRatio,
    Krea2AssistedAttemptStatus,
    Krea2AssistedTurnMode,
    Krea2BatchSettings,
    Krea2LoraSelection,
    Krea2PromptLanguage,
)
from panelforge.infrastructure.krea2_batch_recipes import LocalKrea2VisualRecipeCatalog
from panelforge.infrastructure.krea2_creation_exports import LocalKrea2CreationExporter
from panelforge.infrastructure.presets import load_krea2_batch_workflow
from panelforge.infrastructure.storage import LocalAssetStore, LocalKrea2AssistedProjectStore


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / "workflows" / "image.generate.batch" / "krea2-community" / "0.2.0"
PNG = b"\x89PNG\r\n\x1a\n" + b"assisted"
PROMPT = (
    "A full-body fantasy tiger representing the Chinese zodiac, standing on a carved jade dais, "
    "with precise striped anatomy, ornate celestial jewelry, a layered temple environment, dramatic "
    "moonlit rim light, deep amber and turquoise color separation, cinematic depth and highly detailed "
    "photorealistic materials in a complete vertical 9:16 composition."
)
CHINESE_PROMPT = (
    "竖版9:16电影感画面，一只中国生肖白虎完整站立在雕刻玉石基座上，四肢与尾巴清晰可见，"
    "佩戴精致的金色天体珠宝，背景是层次丰富的月夜宫殿，琥珀色轮廓光与青绿色环境光分离，"
    "真实毛发与宝石材质，构图稳定，细节锐利，无文字，无水印。"
)


class Gateway:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.requests = []

    def list_models(self):
        return (ModelDescriptor("Qwen3.8-27B"),)

    def stream(self, request):
        self.requests.append(request)
        content = next(self.responses)
        if request.include_reasoning:
            yield CompletionStreamEvent(StreamEventKind.REASONING, StreamPhase.GENERATING, text="trace")
        yield CompletionStreamEvent(StreamEventKind.DELTA, StreamPhase.GENERATING, text=content)
        yield CompletionStreamEvent(
            StreamEventKind.COMPLETED,
            StreamPhase.COMPLETED,
            result=CompletionResult(request.model_id, content, call_id=f"call-{len(self.requests)}"),
        )


class Comfy:
    def __init__(self):
        self.workflows = []

    def submit_workflow(self, workflow):
        self.workflows.append(workflow)
        return f"prompt-{len(self.workflows)}"

    def get_history(self, prompt_id):
        return {
            prompt_id: {
                "status": {"completed": True, "status_str": "success"},
                "outputs": {
                    "299": {
                        "images": [
                            {"filename": f"{prompt_id}.png", "subfolder": "", "type": "output"}
                        ]
                    }
                },
            }
        }

    def download_output(self, **_values):
        return PNG

    def cancel_execution(self, _prompt_id):
        return None


class Resources:
    def __init__(self, model, lora):
        self.model = model
        self.lora = lora

    def list_models(self):
        return (SimpleNamespace(comfy_name=self.model),)

    def list_loras(self):
        return (SimpleNamespace(comfy_name=self.lora),)

    def inventory_warnings(self):
        return ("catalogue distant",)


class Krea2AssistedServiceTest(unittest.TestCase):
    def test_conversation_render_feedback_export_and_recipe_publication(self):
        creation = json.dumps({
            "message": "Voici une première direction exploitable.",
            "questions": ["Souhaites-tu une esthétique plus joaillière ?"],
            "prompt": PROMPT,
            "recommendations": ["Tester le checkpoint BF16."],
        })
        second_creation = json.dumps({
            "message": "J’ai renforcé le cadrage en pied après lecture du résultat.",
            "questions": [],
            "prompt": PROMPT + " The paws and tail are entirely visible with generous breathing room.",
            "recommendations": [],
        })
        recipe_response = json.dumps({
            "message": "Le résultat permet déjà une recette stable.",
            "questions": ["Les autres animaux doivent-ils garder le même socle ?"],
            "recipe": {
                "recipe_id": "fantasy_chinese_zodiac",
                "display_name": "Zodiaque fantastique",
                "description": "Animaux du zodiaque chinois en portraits fantastiques.",
                "identity": "A full-body Chinese zodiac animal rendered as a celestial luxury icon.",
                "invariants": ["Vertical 9:16 full-body composition", "Celestial jewelry and carved jade dais"],
                "variables": ["Chinese zodiac animal", "Primary gemstone palette"],
                "risks": ["Cropped paws or tail", "Generic costume replacing animal anatomy"],
                "canonical_prompt": PROMPT,
            },
        })
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            assets = LocalAssetStore(root)
            reference = assets.create(PNG, media_type="image/png")
            catalog = LocalKrea2VisualRecipeCatalog(ROOT / "krea2_batch_recipes", workspace_root=root)
            shipped = catalog.current()[0]
            lora = "krea2/detail.safetensors"
            gateway = Gateway((creation, second_creation, recipe_response))
            comfy = Comfy()
            store = LocalKrea2AssistedProjectStore(root)
            service = Krea2AssistedService(
                gateway=gateway,
                recipes=catalog,
                workflow=load_krea2_batch_workflow(WORKFLOW),
                comfy=comfy,
                assets=assets,
                projects=store,
                resources=Resources(shipped.settings.model_name, lora),
                exporter=LocalKrea2CreationExporter(root / "exports"),
                poll_interval=0.001,
                project_id_factory=lambda: "krea2-create-test",
                turn_id_factory=iter(("turn-1", "turn-2", "turn-3", "turn-4", "turn-5", "turn-6")).__next__,
                attempt_id_factory=lambda: "attempt-1",
                seed_factory=lambda: 42,
            )
            project = service.create_project(
                name="Zodiaque",
                intention="Créer un tigre du zodiaque chinois.",
                model_id="Qwen3.8-27B",
                reference_asset_id=reference.asset_id,
                reference_filename="tiger.png",
            )
            self.assertEqual(project.prompt_language, Krea2PromptLanguage.ENGLISH)
            events = list(service.stream_chat(
                project.project_id,
                project.intention,
                include_reasoning=True,
            ))
            project = events[-1].project
            self.assertEqual(project.current_prompt, PROMPT)
            self.assertEqual([image.label for image in gateway.requests[0].images], ["REFERENCE IMAGE"])
            self.assertIn("will NOT be sent", gateway.requests[0].system_prompt)
            self.assertIn(shipped.settings.model_name, gateway.requests[0].user_prompt)
            self.assertIn(lora, gateway.requests[0].user_prompt)

            settings = Krea2BatchSettings(
                model_name=shipped.settings.model_name,
                aspect_ratio=Krea2AspectRatio.PORTRAIT_WIDESCREEN,
                megapixels=2.1,
                loras=(Krea2LoraSelection(lora, 0.4),),
            )
            project = service.prepare_attempt(project.project_id, prompt=PROMPT, settings=settings)
            project = service.queue_attempt(project.project_id, "attempt-1")
            project = service.execute_attempt(project.project_id, "attempt-1")
            self.assertEqual(project.attempt("attempt-1").status, Krea2AssistedAttemptStatus.SUCCEEDED)
            self.assertEqual(len(comfy.workflows), 1)
            self.assertNotIn(reference.asset_id, json.dumps(comfy.workflows[0]))

            project = service.select_feedback(project.project_id, "attempt-1")
            guidance = assets.create(PNG + b"guidance", media_type="image/png")
            project = list(service.stream_chat(
                project.project_id,
                "Cadre-le entièrement en reprenant la posture de l’image d’appoint.",
                model_id="local::revision-qwen",
                guidance_asset_id=guidance.asset_id,
                guidance_filename="pose-guide.png",
            ))[-1].project
            self.assertEqual(
                [image.label for image in gateway.requests[1].images],
                ["REFERENCE IMAGE", "GENERATED RESULT", "TURN GUIDANCE IMAGE"],
            )
            self.assertIn("does not become persistent project identity", gateway.requests[1].user_prompt)
            self.assertEqual(project.turns[-2].guidance_asset_id, guidance.asset_id)
            self.assertEqual(project.turns[-2].guidance_filename, "pose-guide.png")
            self.assertIn('"seed": 42', gateway.requests[1].user_prompt)
            self.assertEqual(gateway.requests[1].model_id, "local::revision-qwen")
            self.assertEqual(gateway.requests[1].max_tokens, 131_072)
            self.assertEqual(project.model_id, "Qwen3.8-27B")
            self.assertEqual(project.revision_model_id, "local::revision-qwen")
            self.assertEqual(project.turns[-1].model_id, "local::revision-qwen")

            project = service.save_image(project.project_id, "attempt-1")
            self.assertIsNone(project.export_error)
            self.assertTrue(Path(project.export_path, "creation_001.png").is_file())
            self.assertTrue(Path(project.export_path, "creation_001.txt").is_file())

            project = list(service.stream_chat(
                project.project_id,
                "Prépare la recette.",
                mode=Krea2AssistedTurnMode.RECIPE,
            ))[-1].project
            self.assertEqual(
                [image.label for image in gateway.requests[2].images],
                ["REFERENCE IMAGE", "GENERATED RESULT"],
            )
            self.assertEqual(gateway.requests[2].model_id, "local::revision-qwen")
            self.assertIn("TURN GUIDANCE IMAGE USED: pose-guide.png", gateway.requests[2].user_prompt)
            self.assertEqual(project.recipe_draft.recipe_id, "fantasy_chinese_zodiac")
            project, published = service.publish_recipe(project.project_id)
            self.assertEqual(published.version, "0.1.0")
            self.assertEqual(published.settings, settings)
            self.assertEqual(published.prompt_language, Krea2PromptLanguage.ENGLISH)
            self.assertEqual(project.published_recipe_id, published.recipe_id)
            self.assertEqual(store.get(project.project_id), project)
            self.assertEqual(catalog.get("fantasy_chinese_zodiac", "0.1.0"), published)

    def test_switches_to_chinese_and_persists_the_choice_for_later_iterations(self):
        response = json.dumps({
            "message": "Voici une version chinoise directement exploitable.",
            "questions": [],
            "prompt": CHINESE_PROMPT,
            "recommendations": [],
        }, ensure_ascii=False)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            assets = LocalAssetStore(root)
            catalog = LocalKrea2VisualRecipeCatalog(ROOT / "krea2_batch_recipes", workspace_root=root)
            shipped = catalog.current()[0]
            gateway = Gateway((response,))
            store = LocalKrea2AssistedProjectStore(root)
            service = Krea2AssistedService(
                gateway=gateway,
                recipes=catalog,
                workflow=load_krea2_batch_workflow(WORKFLOW),
                comfy=Comfy(),
                assets=assets,
                projects=store,
                resources=Resources(shipped.settings.model_name, "krea2/detail.safetensors"),
                project_id_factory=lambda: "krea2-create-chinese",
                turn_id_factory=iter(("turn-zh-1", "turn-zh-2")).__next__,
            )
            project = service.create_project(
                name="Tigre chinois",
                intention="Créer un tigre céleste.",
                model_id="Qwen3.8-27B",
            )
            project_path = root / "krea2_assisted" / project.project_id / "project.json"
            legacy = json.loads(project_path.read_text(encoding="utf-8"))
            legacy.pop("prompt_language")
            project_path.write_text(json.dumps(legacy, ensure_ascii=False), encoding="utf-8")
            self.assertEqual(store.get(project.project_id).prompt_language, Krea2PromptLanguage.ENGLISH)

            terminal = list(service.stream_chat(
                project.project_id,
                project.intention,
                prompt_language=Krea2PromptLanguage.CHINESE_SIMPLIFIED,
            ))[-1].project

            self.assertEqual(terminal.current_prompt, CHINESE_PROMPT)
            self.assertEqual(terminal.prompt_language, Krea2PromptLanguage.CHINESE_SIMPLIFIED)
            self.assertEqual(store.get(project.project_id).prompt_language, Krea2PromptLanguage.CHINESE_SIMPLIFIED)
            self.assertIn("Simplified Chinese (简体中文)", gateway.requests[0].user_prompt)
            self.assertIn("Never duplicate the prompt bilingually", gateway.requests[0].user_prompt)

            stored = json.loads(project_path.read_text(encoding="utf-8"))
            for turn in stored["turns"]:
                turn.pop("guidance_asset_id")
                turn.pop("guidance_filename")
            project_path.write_text(json.dumps(stored, ensure_ascii=False), encoding="utf-8")
            self.assertTrue(all(
                turn.guidance_asset_id is None
                for turn in store.get(project.project_id).turns
            ))


if __name__ == "__main__":
    unittest.main()
