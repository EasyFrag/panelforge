"""Manifest-owned BUNNY graph, adapted to the existing H3 render ports."""

from dataclasses import replace
import hashlib
import json
from pathlib import Path

from panelforge.domain.h3_bunny import BUNNY_RECIPE_ID, H3BunnySettings, bunny_geometry
from panelforge.domain.h3_render import H3RenderInputMode, derive_h3_render_input_mode
from panelforge.domain.recipes import RecipeRef
from panelforge.domain.video_lab import VideoAspectRatio
from .h3_render import H3RenderPreset
from .render_progress import validate_render_progress_profile


class BunnyH3RenderRecipe:
    status = "experimental"
    supports_video_lora = True
    supports_initial_megapixels = True
    minimum_reference_images = 1
    maximum_reference_images = 9
    output_history_field = "images"

    def __init__(self, directory: Path):
        self.manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        m = self.manifest
        self._raw = (directory / m["workflow"]["file"]).read_bytes()
        digest = hashlib.sha256(self._raw).hexdigest()
        if digest != m["workflow"]["sha256"] or m["recipe_id"] != BUNNY_RECIPE_ID:
            raise ValueError("BUNNY : empreinte ou identité du workflow invalide.")
        self.reference = RecipeRef(m["operation_id"], m["recipe_id"], m["version"], digest)
        graph = json.loads(self._raw)
        for ids in m["nodes"].values():
            for node_id in ids if isinstance(ids, list) else [ids]:
                if node_id not in graph:
                    raise ValueError(f"BUNNY : liaison absente du workflow : {node_id}")
        self.output_node_id = m["nodes"]["output"]
        self.maximum_keyframes = m["templates"]["keyframes"]["maximum"]
        self.keyframe_margin_ms = m["templates"]["keyframes"]["margin_ms"]
        self.progress_profile = validate_render_progress_profile(m["progress"], graph)
        self.presets = {"bunny": H3RenderPreset(
            "bunny", "BUNNY · Turbo", VideoAspectRatio.PORTRAIT_WIDESCREEN,
            0.9, 10.0, 9, 8, 12, 75, 768, initial_megapixels=0.9,
        )}

    def keyframe_output_nodes(self, count):
        if type(count) is not int or not 0 <= count <= self.maximum_keyframes:
            raise ValueError("Nombre de keyframes BUNNY invalide.")
        base = self.manifest["templates"]["keyframes"]["save_base"]
        return tuple(str(base + i) for i in range(count))

    def progress_for(self, bunny):
        return replace(self.progress_profile, phases=tuple(
            replace(p, expected_steps=(bunny.coarse_steps if p.phase_id == "coarse" else bunny.refine_steps))
            if p.tracks_steps else p for p in self.progress_profile.phases
        ))

    def controls_spec(self, input_mode):
        graph = json.loads(self._raw)
        nodes = self.manifest["nodes"]
        model = graph[nodes["plain_model"]]["inputs"]["unet_name"]
        if input_mode is H3RenderInputMode.REF2VA:
            hybrid = graph[nodes["hybrid_model"]]["inputs"]
            model = f"Hybride : {hybrid['base_model']} + {hybrid['overlay_model']}"
        first = graph[nodes["loras"][0]]["inputs"]
        second = graph[nodes["loras"][1]]["inputs"]
        return {
            "model_label": model,
            "turbo_strength": graph[nodes["turbo"]]["inputs"]["strength_model"],
            "default_lora": first["lora_name"], "lora_first_strength": first["strength_model"],
            "lora_second_strength": second["strength_model"],
            "turbo_profiles": {"on": {"base_steps": 9, "coarse_steps": 4, "refine_steps": 5},
                               "off": {"base_steps": 30, "coarse_steps": 25, "refine_steps": 5}},
        }

    def build_workflow(self, *, prompt, settings, output_filename_prefix, keyframe_indices,
                       bunny: H3BunnySettings, initial_megapixels=0.9,
                       input_mode=H3RenderInputMode.REF2VA, first_frame=None, last_frame=None,
                       source_images=(), video_lora=None, spectrum_enabled=False):
        if not isinstance(bunny, H3BunnySettings):
            raise TypeError("Réglages BUNNY requis.")
        if spectrum_enabled or (video_lora and video_lora.clip_last_layer is not None):
            raise ValueError("BUNNY ne prend pas en charge Spectrum ou CLIP Last Layer.")
        if not prompt.strip():
            raise ValueError("Prompt BUNNY vide.")
        bunny_geometry(settings, initial_megapixels)
        is_ref = input_mode is H3RenderInputMode.REF2VA
        if is_ref:
            if first_frame or last_frame or not 1 <= len(source_images) <= 9:
                raise ValueError("REF2VA requiert 1 à 9 références, sans first/last frame.")
        elif source_images or input_mode is not derive_h3_render_input_mode(first_frame is not None, last_frame is not None):
            raise ValueError("Le mode BUNNY ne correspond pas aux images d’entrée.")
        self.keyframe_output_nodes(len(keyframe_indices))
        if any(type(i) is not int or not 0 <= i < settings.frame_count for i in keyframe_indices):
            raise ValueError("Index de keyframe invalide.")
        graph = json.loads(self._raw)
        nodes, templates = self.manifest["nodes"], self.manifest["templates"]

        def inputs(name):
            return graph[nodes[name]]["inputs"]

        inputs("prompt")["value"] = prompt
        inputs("resolution").update(aspect_ratio=settings.aspect_ratio.value, megapixels=initial_megapixels)
        inputs("duration")["value"] = settings.duration_seconds
        inputs("noise")["noise_seed"] = settings.seed
        inputs("plan").update(base_steps=bunny.base_steps, coarse_steps=bunny.coarse_steps, refine_steps=bunny.refine_steps)
        # The clock's own schedule is unused: both samplers take plan sigmas.
        # Both MP fields use ResolutionSelector's 1024² convention. T8 then
        # preserves the initial aspect and aligns the requested target area.
        target_width, target_height = settings.resolution
        inputs("upscale").update(size_mode="target_dimensions", target_width=target_width, target_height=target_height)
        inputs("output")["filename_prefix"] = output_filename_prefix
        base_model = nodes["hybrid_model"] if is_ref else nodes["plain_model"]
        inputs("turbo")["model"] = [base_model, 0]
        inputs("attention")["model"] = [nodes["turbo"] if bunny.turbo_enabled else base_model, 0]
        for i, lora_id in enumerate(nodes["loras"]):
            graph[lora_id]["inputs"]["model"] = [nodes["attention"], 0]
            if video_lora:
                graph[lora_id]["inputs"].update(
                    lora_name=video_lora.name,
                    strength_model=video_lora.strength if i == 0 else bunny.lora_second_strength,
                )
            upstream = lora_id if video_lora else nodes["attention"]
            if bunny.preview_enabled:
                preview = templates["preview"]
                preview_id = preview["ids"][i]
                graph[preview_id] = {"class_type": preview["class_type"],
                    "inputs": {**preview["inputs"], "model": [upstream, 0]}}
                upstream = preview_id
            inputs("clock" if i == 0 else "detail")["model"] = [upstream, 0]

        anchors = {}
        for role, image in (("first", first_frame), ("last", last_frame)):
            if image:
                t = templates[role]
                graph[t["id"]] = {"class_type": t["class_type"], "inputs": {t["input"]: image}}
                anchors[f"{role}_frame"] = [t["id"], 0]
        for i, image in enumerate(source_images):
            t = templates["references"]
            node_id = str(t["base"] + i)
            graph[node_id] = {"class_type": t["class_type"], "inputs": {t["input"]: image}}
            anchors[f"ref_images.ref_image_{i}"] = [node_id, 0]
        for node_id in nodes["conditionings"]:
            graph[node_id]["inputs"].update(anchors)
            graph[node_id]["inputs"]["task_type"] = self.manifest["tasks"][input_mode.value]

        keyframes = templates["keyframes"]
        outputs = [self.output_node_id]
        for i, frame_index in enumerate(keyframe_indices):
            extract_id = str(keyframes["extract_base"] + i)
            save_id = str(keyframes["save_base"] + i)
            graph[extract_id] = {"class_type": keyframes["extract_class"], "inputs": {
                "image": [nodes["decode"], 0], "batch_index": frame_index, "length": 1}}
            graph[save_id] = {"class_type": keyframes["save_class"], "inputs": {
                "images": [extract_id, 0], "filename_prefix": f"{output_filename_prefix}_frame_{i}"}}
            outputs.append(save_id)
        # Remove inactive models, bypassed LoRAs and unused author controls.
        required = set()
        def visit(node_id):
            if node_id in required:
                return
            required.add(node_id)
            for value in graph[node_id]["inputs"].values():
                if isinstance(value, list) and len(value) == 2 and isinstance(value[0], str):
                    visit(value[0])
        for node_id in outputs:
            visit(node_id)
        return {node_id: node for node_id, node in graph.items() if node_id in required}

    def validate_dependencies(self, comfy, workflow, *, resources=None):
        """Read node descriptions only; no load, validation execution or fallback."""
        descriptions = {}
        for node in workflow.values():
            name = node["class_type"]
            if name not in descriptions:
                try:
                    info = comfy.describe_node(name)
                except Exception as error:
                    raise ValueError(f"BUNNY : impossible de vérifier le nœud {name} : {error}") from error
                if name not in info:
                    raise ValueError(f"BUNNY : nœud ComfyUI manquant : {name}")
                descriptions[name] = info[name]
        for node_id, fields in (resources if resources is not None else self.manifest["resources"]).items():
            if node_id not in workflow:
                continue
            node = workflow[node_id]
            description = descriptions[node["class_type"]].get("input", {})
            declared = {**description.get("required", {}), **description.get("optional", {})}
            for field in fields:
                schema = declared.get(field)
                if not schema:
                    raise ValueError(f"BUNNY : entrée indisponible : {node['class_type']}.{field}")
                options = schema[0] if isinstance(schema[0], list) else schema[1].get("options") if len(schema) > 1 else None
                value = node["inputs"][field]
                if options is not None and value.replace("\\", "/") not in {str(v).replace("\\", "/") for v in options}:
                    raise ValueError(f"BUNNY : modèle absent de ComfyUI : {value}")
