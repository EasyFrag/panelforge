import json
from io import BytesIO
from pathlib import Path
import tempfile
from threading import Event, Thread
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import HTTPError

from panelforge.application import (
    CompletionResult,
    CompletionStreamEvent,
    Krea2BatchRequest,
    Krea2BatchService,
    ModelDescriptor,
    StreamEventKind,
    StreamPhase,
)
from panelforge.domain import (
    KREA2_BATCH_RGTHREE_MAX_SEED,
    Krea2BatchStatus,
    Krea2LoraSelection,
    Krea2PromptLanguage,
    Krea2ReviewDecision,
)
from panelforge.infrastructure.krea2_batch_recipes import LocalKrea2VisualRecipeCatalog
from panelforge.infrastructure.presets import load_krea2_batch_workflow
from panelforge.infrastructure.storage import LocalAssetStore, LocalKrea2BatchStore


ROOT = Path(__file__).resolve().parents[1]
PNG = b"\x89PNG\r\n\x1a\n" + b"rendered"


def generated_response(count):
    prompts = []
    for index in range(1, count + 1):
        prompt = (
            f"vertical 9:16 variation {index}. "
            + "A complete standalone KREA2 prompt with a strong foreground, layered middle ground, "
            + "deep background, precise materials, cinematic lighting, controlled color separation, "
            + "fine environmental details and a coherent visual identity. " * 5
        )
        prompts.append({"signature": f"variation-{index}", "prompt": prompt})
    return json.dumps({"prompts": prompts})


class Gateway:
    def __init__(self, content):
        self.content = content
        self.completion_content = content
        self.requests = []

    def list_models(self):
        return (ModelDescriptor("Qwen3.8-27B"),)

    def stream(self, request):
        self.requests.append(request)
        if request.include_reasoning:
            yield CompletionStreamEvent(StreamEventKind.REASONING, StreamPhase.GENERATING, text="trace")
        yield CompletionStreamEvent(StreamEventKind.DELTA, StreamPhase.GENERATING, text=self.content)
        yield CompletionStreamEvent(
            StreamEventKind.COMPLETED,
            StreamPhase.COMPLETED,
            result=CompletionResult(request.model_id, self.content, call_id="call-1"),
        )

    def complete(self, request):
        self.requests.append(request)
        return CompletionResult(
            request.model_id,
            self.completion_content,
            call_id=f"call-{len(self.requests)}",
        )


class Comfy:
    def __init__(self):
        self.workflows = []

    def submit_workflow(self, workflow):
        self.workflows.append(workflow)
        return f"prompt-{len(self.workflows)}"

    def get_history(self, prompt_id):
        return {prompt_id: {"status": {"completed": True, "status_str": "success"}, "outputs": {
            "299": {"images": [{"filename": f"{prompt_id}.png", "subfolder": "", "type": "output"}]}
        }}}

    def download_output(self, **_):
        return PNG

    def cancel_execution(self, _):
        return None


class SaveImageKJComfy(Comfy):
    """Mirror the installed KJ node: files exist but history outputs is empty."""

    def __init__(self, *, expose_prompt=True):
        super().__init__()
        self.expose_prompt = expose_prompt
        self.downloads = []

    def get_history(self, prompt_id):
        index = int(prompt_id.removeprefix("prompt-")) - 1
        record = {
            "status": {"completed": True, "status_str": "success"},
            "outputs": {},
        }
        if self.expose_prompt:
            record["prompt"] = [index + 1, prompt_id, self.workflows[index], {}]
        return {prompt_id: record}

    def download_output(self, **values):
        self.downloads.append(values)
        return PNG


class BlockingSubmitComfy(Comfy):
    def __init__(self):
        super().__init__()
        self.entered = Event()
        self.release = Event()
        self.cancelled = []

    def submit_workflow(self, workflow):
        self.workflows.append(workflow)
        self.entered.set()
        if not self.release.wait(2):
            raise TimeoutError("test did not release submission")
        return "prompt-blocked"

    def get_history(self, prompt_id):
        return {prompt_id: {"status": {"completed": False, "status_str": "running"}, "outputs": {}}}

    def cancel_execution(self, prompt_id):
        self.cancelled.append(prompt_id)
        return None


class RejectedSubmitComfy(Comfy):
    def submit_workflow(self, workflow):
        self.workflows.append(workflow)
        seed = workflow["287"]["inputs"]["seed"]
        payload = json.dumps({
            "error": {"message": "Prompt outputs failed validation"},
            "node_errors": {
                "287": {
                    "errors": [{
                        "message": (
                            f"Value {seed} bigger than max of "
                            f"{KREA2_BATCH_RGTHREE_MAX_SEED}"
                        )
                    }]
                }
            },
        }).encode("utf-8")
        raise HTTPError(
            "http://bucket:8188/prompt",
            400,
            "Bad Request",
            hdrs=None,
            fp=BytesIO(payload),
        )


class Resources:
    def __init__(self, model, loras=()):
        self.model = model
        self.loras = tuple(loras)

    def list_models(self):
        return (SimpleNamespace(comfy_name=self.model),)

    def list_loras(self):
        return tuple(SimpleNamespace(comfy_name=value) for value in self.loras)


class Krea2BatchServiceTest(unittest.TestCase):
    def make_service(self, temporary, count=3, *, comfy=None, default_seeds=False):
        workspace = Path(temporary)
        catalog = LocalKrea2VisualRecipeCatalog(ROOT / "krea2_batch_recipes", workspace_root=workspace)
        recipe = catalog.get("space_megastructure_photoreal_v1", "0.1.0")
        gateway = Gateway(generated_response(count))
        comfy = comfy or Comfy()
        arguments = dict(
            gateway=gateway,
            recipes=catalog,
            workflow=load_krea2_batch_workflow(ROOT / "workflows" / "image.generate.batch" / "krea2-community" / "0.2.0"),
            comfy=comfy,
            assets=LocalAssetStore(workspace),
            batches=LocalKrea2BatchStore(workspace),
            resources=Resources(recipe.settings.model_name),
            poll_interval=0.001,
        )
        if not default_seeds:
            arguments["seed_factory"] = iter(range(1, 20)).__next__
        service = Krea2BatchService(**arguments)
        return service, gateway, comfy, recipe

    @patch("panelforge.application.krea2_batch.secrets.randbelow")
    def test_default_seed_generation_matches_the_rgthree_limit(self, randbelow):
        randbelow.return_value = KREA2_BATCH_RGTHREE_MAX_SEED
        with tempfile.TemporaryDirectory() as temporary:
            service, _, _, recipe = self.make_service(
                temporary,
                count=1,
                default_seeds=True,
            )
            batch = service.prepare(
                Krea2BatchRequest(recipe.recipe_id, recipe.version, 1, "Qwen3.8-27B")
            )
            list(service.stream_generate_prompts(batch.batch_id))
            item = service.get(batch.batch_id).items[0]

        randbelow.assert_called_once_with(KREA2_BATCH_RGTHREE_MAX_SEED + 1)
        self.assertEqual(item.seed, KREA2_BATCH_RGTHREE_MAX_SEED)

    def test_one_llm_call_generates_all_prompts_then_renders_sequentially(self):
        with tempfile.TemporaryDirectory() as temporary:
            service, gateway, comfy, recipe = self.make_service(temporary)
            batch = service.prepare(Krea2BatchRequest(recipe.recipe_id, recipe.version, 3, "Qwen3.8-27B"))
            events = list(service.stream_generate_prompts(batch.batch_id, include_reasoning=True))
            ready = service.get(batch.batch_id)
            self.assertEqual(ready.status, Krea2BatchStatus.READY)
            self.assertEqual(len(ready.items), 3)
            self.assertEqual(len(gateway.requests), 1)
            self.assertEqual(gateway.requests[0].max_tokens, 262_144)
            self.assertTrue(gateway.requests[0].include_reasoning)
            self.assertTrue(any(event.kind is StreamEventKind.REASONING for event in events))
            service.start_rendering(batch.batch_id)
            completed = service.render(batch.batch_id)
            self.assertEqual(completed.status, Krea2BatchStatus.COMPLETED)
            self.assertEqual(len(comfy.workflows), 3)
            self.assertTrue(all(item.output_asset_id for item in completed.items))
            first_sidecar = json.loads(comfy.workflows[0]["299"]["inputs"]["caption"])
            self.assertEqual(first_sidecar["schema_version"], 1)
            self.assertEqual(first_sidecar["prompt"], completed.items[0].prompt)
            self.assertEqual(
                first_sidecar["variation_signature"],
                completed.items[0].variation_signature,
            )
            self.assertEqual(first_sidecar["render"]["seed"], completed.items[0].seed)
            self.assertEqual(first_sidecar["render"]["model_name"], recipe.settings.model_name)
            self.assertEqual(first_sidecar["render"]["aspect_ratio"], recipe.settings.aspect_ratio.value)
            self.assertEqual(first_sidecar["workflow"]["version"], "0.2.0")
            self.assertEqual(comfy.workflows[0]["299"]["class_type"], "SaveImageKJ")
            reviewed = service.review_item(completed.batch_id, "image-01", Krea2ReviewDecision.LIKE, "Belle palette")
            self.assertEqual(reviewed.items[0].comment, "Belle palette")

    def test_recipe_workshop_iterates_tests_and_publishes_only_on_accept(self):
        with tempfile.TemporaryDirectory() as temporary:
            service, gateway, _, recipe = self.make_service(temporary, count=1)
            source = service.prepare(
                Krea2BatchRequest(recipe.recipe_id, recipe.version, 1, "Qwen3.8-27B")
            )
            list(service.stream_generate_prompts(source.batch_id))
            service.start_rendering(source.batch_id)
            source = service.render(source.batch_id)
            service.review_item(
                source.batch_id,
                "image-01",
                Krea2ReviewDecision.LIKE,
                "Conserver la profondeur",
            )
            gateway.completion_content = json.dumps({
                "reply": "J’ai renforcé la profondeur. Faut-il aussi refroidir la palette ?",
                "recipe": {
                    "identity": recipe.identity + " Stronger depth hierarchy.",
                    "invariants": list(recipe.invariants),
                    "variables": list(recipe.variables),
                    "risks": list(recipe.risks),
                    "canonical_prompt": recipe.canonical_prompt,
                },
            })

            proposed = service.propose_recipe_revision(
                source.batch_id,
                "Renforce la profondeur",
                prompt_language=Krea2PromptLanguage.CHINESE_SIMPLIFIED,
            )

            workshop = json.loads(proposed.recipe_workshop)
            self.assertEqual(workshop["active_draft_id"], "D1")
            self.assertEqual([turn["role"] for turn in workshop["turns"]], ["user", "assistant"])
            self.assertEqual(json.loads(proposed.recipe_revision_draft)["prompt_language"], "zh")
            self.assertIn("Simplified Chinese", gateway.requests[-1].system_prompt)
            self.assertFalse(any(
                value.recipe_id == recipe.recipe_id and value.version == "0.1.1"
                for value in service.recipes.list()
            ))

            test_batch, proposed = service.prepare_recipe_revision_test(
                proposed.batch_id,
                image_count=1,
                direction="cooler palette",
                model_id="Qwen3.8-27B",
            )
            self.assertEqual(test_batch.workshop_source_batch_id, source.batch_id)
            self.assertIsNotNone(test_batch.recipe_snapshot)
            self.assertEqual(json.loads(test_batch.recipe_snapshot)["prompt_language"], "zh")
            list(service.stream_generate_prompts(test_batch.batch_id))
            service.start_rendering(test_batch.batch_id)
            test_batch = service.render(test_batch.batch_id)
            service.review_item(
                test_batch.batch_id,
                "image-01",
                Krea2ReviewDecision.DISLIKE,
                "Palette trop froide",
            )
            gateway.completion_content = json.dumps({
                "reply": "Je conserve la profondeur mais réchauffe la palette.",
                "recipe": {
                    "identity": recipe.identity + " Strong depth with a warmer palette.",
                    "invariants": list(recipe.invariants),
                    "variables": list(recipe.variables),
                    "risks": list(recipe.risks),
                    "canonical_prompt": recipe.canonical_prompt,
                },
            })

            second = service.propose_recipe_revision(test_batch.batch_id, "Corrige le test")
            workshop = json.loads(second.recipe_workshop)
            self.assertEqual(workshop["active_draft_id"], "D2")
            self.assertIn("Palette trop froide", gateway.requests[-1].user_prompt)

            published = service.accept_recipe_revision(second.batch_id)
            reloaded = service.get(source.batch_id)
            self.assertEqual(published.version, "0.1.1")
            self.assertIs(published.prompt_language, Krea2PromptLanguage.CHINESE_SIMPLIFIED)
            self.assertEqual(json.loads(reloaded.recipe_workshop)["status"], "published")
            self.assertEqual(service.recipes.get(recipe.recipe_id, "0.1.0").identity, recipe.identity)
            with self.assertRaisesRegex(ValueError, "already published"):
                service.accept_recipe_revision(second.batch_id)

    def test_save_image_kj_output_is_imported_from_its_prompt_prefix(self):
        with tempfile.TemporaryDirectory() as temporary:
            comfy = SaveImageKJComfy()
            service, _, _, recipe = self.make_service(temporary, count=1, comfy=comfy)
            batch = service.prepare(
                Krea2BatchRequest(recipe.recipe_id, recipe.version, 1, "Qwen3.8-27B")
            )
            list(service.stream_generate_prompts(batch.batch_id))
            service.start_rendering(batch.batch_id)

            completed = service.render(batch.batch_id)

            self.assertEqual(completed.status, Krea2BatchStatus.COMPLETED)
            self.assertIsNotNone(completed.items[0].output_asset_id)
            self.assertEqual(comfy.downloads, [{
                "filename": "image-01_00001_.png",
                "subfolder": f"image/krea2-batch/{batch.batch_id}",
                "folder_type": "output",
            }])

    def test_failed_kj_import_is_recovered_when_history_becomes_available(self):
        with tempfile.TemporaryDirectory() as temporary:
            comfy = SaveImageKJComfy(expose_prompt=False)
            service, _, _, recipe = self.make_service(temporary, count=1, comfy=comfy)
            batch = service.prepare(
                Krea2BatchRequest(recipe.recipe_id, recipe.version, 1, "Qwen3.8-27B")
            )
            list(service.stream_generate_prompts(batch.batch_id))
            service.start_rendering(batch.batch_id)
            failed = service.render(batch.batch_id)
            self.assertEqual(failed.status, Krea2BatchStatus.FAILED)
            self.assertIn("expected PNG", failed.items[0].error)

            comfy.expose_prompt = True
            recovered = service.get(batch.batch_id)

            self.assertEqual(recovered.status, Krea2BatchStatus.COMPLETED)
            self.assertEqual(recovered.items[0].status.value, "succeeded")
            self.assertIsNotNone(recovered.items[0].output_asset_id)
            self.assertTrue(any("rÃ©importÃ©es" in warning for warning in recovered.warnings))

    def test_missing_lora_warns_and_is_omitted_without_blocking_render(self):
        with tempfile.TemporaryDirectory() as temporary:
            service, _, comfy, recipe = self.make_service(temporary, count=1)
            settings = recipe.settings.__class__(
                model_name=recipe.settings.model_name,
                aspect_ratio=recipe.settings.aspect_ratio,
                megapixels=recipe.settings.megapixels,
                loras=(Krea2LoraSelection("krea2/missing.safetensors", 0.8),),
            )
            batch = service.prepare(Krea2BatchRequest(recipe.recipe_id, recipe.version, 1, "Qwen3.8-27B", settings=settings))
            self.assertTrue(any("LoRA indisponible" in warning for warning in batch.warnings))
            list(service.stream_generate_prompts(batch.batch_id))
            service.start_rendering(batch.batch_id)
            service.render(batch.batch_id)
            self.assertEqual(comfy.workflows[0]["418"]["inputs"]["lora_01"], "None")

    def test_invalid_single_response_is_kept_without_retry(self):
        with tempfile.TemporaryDirectory() as temporary:
            service, gateway, _, recipe = self.make_service(temporary, count=2)
            gateway.content = '{"prompts": []}'
            batch = service.prepare(Krea2BatchRequest(recipe.recipe_id, recipe.version, 2, "Qwen3.8-27B"))
            list(service.stream_generate_prompts(batch.batch_id))
            failed = service.get(batch.batch_id)
            self.assertEqual(failed.status, Krea2BatchStatus.FAILED)
            self.assertEqual(failed.raw_prompt_response, gateway.content)
            self.assertEqual(len(gateway.requests), 1)

    def test_all_rejected_comfy_submissions_fail_the_batch_with_server_detail(self):
        with tempfile.TemporaryDirectory() as temporary:
            comfy = RejectedSubmitComfy()
            service, _, _, recipe = self.make_service(
                temporary,
                count=2,
                comfy=comfy,
            )
            batch = service.prepare(
                Krea2BatchRequest(recipe.recipe_id, recipe.version, 2, "Qwen3.8-27B")
            )
            list(service.stream_generate_prompts(batch.batch_id))
            service.start_rendering(batch.batch_id)

            failed = service.render(batch.batch_id)

            self.assertEqual(failed.status, Krea2BatchStatus.FAILED)
            self.assertIn("Tous les rendus", failed.error)
            self.assertTrue(all(item.status.value == "failed" for item in failed.items))
            self.assertTrue(all("HTTP 400 Bad Request" in item.error for item in failed.items))
            self.assertTrue(all("nœud 287" in item.error for item in failed.items))
            self.assertTrue(all("Prompt outputs failed validation" in item.error for item in failed.items))

    def test_cancel_waits_for_submission_id_and_cannot_resurrect_the_batch(self):
        with tempfile.TemporaryDirectory() as temporary:
            comfy = BlockingSubmitComfy()
            service, _, _, recipe = self.make_service(temporary, count=1, comfy=comfy)
            batch = service.prepare(Krea2BatchRequest(recipe.recipe_id, recipe.version, 1, "Qwen3.8-27B"))
            list(service.stream_generate_prompts(batch.batch_id))
            service.start_rendering(batch.batch_id)
            render = Thread(target=service.render, args=(batch.batch_id,))
            render.start()
            self.assertTrue(comfy.entered.wait(1))
            cancelled = []
            cancel = Thread(target=lambda: cancelled.append(service.cancel(batch.batch_id)))
            cancel.start()
            comfy.release.set()
            cancel.join(2)
            render.join(2)
            self.assertFalse(cancel.is_alive())
            self.assertFalse(render.is_alive())
            self.assertEqual(service.get(batch.batch_id).status, Krea2BatchStatus.CANCELLED)
            self.assertEqual(comfy.cancelled, ["prompt-blocked"])


if __name__ == "__main__":
    unittest.main()
