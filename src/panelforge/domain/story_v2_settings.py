"""Preparation choices for Story V2, using the shared image and video contracts."""
from copy import deepcopy
from dataclasses import asdict
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from .episodes import default_render_setup
from .krea2_batch import Krea2AspectRatio, Krea2LoraSelection
from .krea2_sampling import Krea2AssistedSettings, sampling_from_dict
from .krea2_assisted_workflows import workflow_selection_from_dict
from .h3_render import H3VideoLoraStack, validate_h3_initial_megapixels
from .h3_bunny import H3BunnySettings, bunny_geometry
from .video_lab import VideoLabSettings, VideoAspectRatio
from .qwen_edit import RATIOS

PROMPT_MODEL = "local::unsloth/gemma-4-31B-it-qat-GGUF"
PLAN_MODEL = "local::unsloth/Qwen3.8-27B-GGUF"
CHECKPOINT = "Krea2/kroma-v0.3-turbo.safetensors"
DEFAULT_IMAGE_PRESET = "style-642721e10d124d5a83ad6bb907ef8fd3"  # Bananita fresh
DEFAULT_VIDEO_VERSION = "0.1.3+vae-int8-convrot.1"


def default_video_render():
    render = default_render_setup(10)
    render["recipe"]["version"] = DEFAULT_VIDEO_VERSION
    return render

class Options(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

class ImageOptions(Options):
    assistance_recipe_version: Literal["1.0.0", "2.0.0", "3.0.0", "4.0.0", "5.0.0", "6.0.0"] = "6.0.0"
    local_inspiration_enabled: bool = False
    style_preset_id: str | None = Field(default=DEFAULT_IMAGE_PRESET, max_length=128)
    art_style_id: str | None = Field(default=None, max_length=240)
    prompt_language: Literal["en", "zh"] = "en"
    workflow: dict = Field(default_factory=lambda: dict(recipe_id="krea2-flux-klein", version="1.0.0"))
    aspect_ratio: str = "9:16 (Portrait Widescreen)"
    megapixels: float = Field(default=2.1, ge=.5, le=4, allow_inf_nan=False)
    sampling: dict = Field(default_factory=lambda: asdict(sampling_from_dict(None, default_preset_id="finish_4")))
    loras: list[dict] = Field(default_factory=list, max_length=10)
    edit_engine: Literal["minimax", "qwen"] = "minimax"
    edit_model: str = Field(default=PROMPT_MODEL, min_length=1, max_length=300)
    thumbnail: bool = True

    @model_validator(mode="after")
    def valid_choices(self):
        try:
            image_settings(self.model_dump(), CHECKPOINT)
        except (TypeError, KeyError) as error:
            raise ValueError("Réglages image incomplets ou inconnus.") from error
        if self.thumbnail and self.aspect_ratio.split(" ")[0] not in RATIOS:
            raise ValueError("Pour la miniature, choisissez un format commun : " + ", ".join(RATIOS))
        if self.art_style_id and self.assistance_recipe_version != "6.0.0":
            raise ValueError("La direction artistique nécessite la recette V6.")
        return self

def image_settings(options, checkpoint):
    return Krea2AssistedSettings(model_name=checkpoint,
        aspect_ratio=Krea2AspectRatio(options["aspect_ratio"]), megapixels=options["megapixels"],
        loras=tuple(Krea2LoraSelection(**v) for v in options["loras"]),
        sampling=sampling_from_dict(options["sampling"]),
        workflow=workflow_selection_from_dict(options["workflow"]))

class CreativeAxes(Options):
    scene_life: int = Field(default=3, ge=0, le=3, strict=True)
    camera: int = Field(default=3, ge=0, le=3, strict=True)
    extra_motion: int = Field(default=3, ge=0, le=3, strict=True)
    dialogue: int = Field(default=1, ge=0, le=3, strict=True)

class VideoOptions(Options):
    plan_model: str = Field(default=PLAN_MODEL, min_length=1, max_length=300)
    prompt_model: str = Field(default=PROMPT_MODEL, min_length=1, max_length=300)
    shot_count: int | None = Field(default=None, ge=1, le=6, strict=True)
    audacity: int = Field(default=3, ge=0, le=3, strict=True)
    creative_axes: CreativeAxes = Field(default_factory=CreativeAxes)
    render: dict = Field(default_factory=default_video_render)

    @field_validator("render")
    @classmethod
    def shared_render_contract(cls, value):
        allowed = set(default_render_setup(10)) | {"video_lora"}
        if set(value) - allowed:
            raise ValueError("Réglage vidéo inconnu.")
        result = deepcopy(value)
        recipe = result.get("recipe")
        if not isinstance(recipe, dict) or set(recipe) != {"id", "version"} or not all(isinstance(v, str) and v for v in recipe.values()):
            raise ValueError("Choisissez une recette vidéo versionnée.")
        settings = dict(result.get("settings", {}))
        if set(settings) != {"aspect_ratio", "megapixels", "duration_seconds", "steps", "seed"}:
            raise ValueError("Réglages de rendu vidéo incomplets ou inconnus.")
        settings["aspect_ratio"] = VideoAspectRatio(settings["aspect_ratio"])
        settings["seed"] = int(settings.get("seed") or 0)
        params = VideoLabSettings(**settings, seed_locked=result.get("seed_locked", True))
        validate_h3_initial_megapixels(result.get("initial_megapixels", .9))
        for key in ("seed_locked", "music_enabled", "spectrum_enabled", "force_upscale"):
            if type(result.get(key, False)) is not bool:
                raise ValueError("Activation vidéo invalide.")
        bunny = result.get("bunny")
        if bunny:
            H3BunnySettings(**bunny)
            if result.get("spectrum_enabled"):
                raise ValueError("Spectrum est indisponible avec BUNNY.")
            bunny_geometry(params, result.get("initial_megapixels", .9))
        if bool(bunny) != (recipe["id"] == "minimax-h3-bunny"):
            raise ValueError("Les réglages BUNNY doivent correspondre à la recette choisie.")
        stack = H3VideoLoraStack.from_dict(result.get("video_loras"))
        if stack:
            stack.validate_mode(bool(bunny))
        result["settings"]["seed"] = str(settings["seed"])
        return result
