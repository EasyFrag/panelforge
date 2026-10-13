"""Contracts for culinary films; no rendering or vendor dependencies."""
from copy import deepcopy
from datetime import UTC, datetime
import hashlib
import json
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator
from .video_lab import VideoAspectRatio
from .video_factory import configuration

MODEL = "local::unsloth/gemma-4-31B-it-qat-GGUF"
PLAN_MODEL = "local::unsloth/Qwen3.8-27B-GGUF"
ACTIVE = {"queued", "working", "waiting"}


def now():
    return datetime.now(UTC).isoformat()


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()).hexdigest()


def identity(prefix):
    return prefix + "-" + uuid4().hex


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Settings(Contract):
    intention: str = Field(default="", max_length=6000)
    target_duration: int = Field(default=45, ge=15, le=180, strict=True)
    aspect_ratio: VideoAspectRatio = VideoAspectRatio.PORTRAIT_WIDESCREEN
    world: str = Field(default="Tout en laine ou crochet : décor, aliments, ustensiles, eau, huile, vapeur et flammes. Conserver le style et les couleurs de l’image du plat ; les décors et accessoires peuvent varier entre les plans.", min_length=1, max_length=3000)
    cook: str = Field(default="Mains et avant-bras humains réalistes, gestes naturels. Le reste du corps est hors champ.", min_length=1, max_length=1500)
    camera: str = Field(default="Cadrages variés, surtout des gros plans sur les gestes ; caméra stable à l’intérieur de chaque plan.", min_length=1, max_length=1500)
    audio: str = Field(default="Sons rapprochés des gestes et de la cuisine, esprit ASMR. Aucune voix, aucun dialogue, aucune musique.", min_length=1, max_length=1500)
    model_id: str = Field(default=MODEL, min_length=1, max_length=300)
    edit_model_id: str = Field(default=MODEL, min_length=1, max_length=300)
    plan_model_id: str = Field(default=PLAN_MODEL, min_length=1, max_length=300)
    writer_model_id: str = Field(default=MODEL, min_length=1, max_length=300)
    style_preset_id: str | None = Field(default=None, max_length=128)


class Shot(Contract):
    id: str = Field(pattern=r"^shot-[a-zA-Z0-9_-]{1,64}$")
    title: str = Field(min_length=1, max_length=160)
    action: str = Field(min_length=1, max_length=3000)
    framing: str = Field(min_length=1, max_length=1000)
    opening: str = Field(min_length=1, max_length=3000)
    ending: str = Field(default="", max_length=3000)
    duration: float = Field(default=6, ge=5, le=15, allow_inf_nan=False)
    mode: Literal["animate", "endpoints"] = "animate"

    @model_validator(mode="after")
    def require_ending(self):
        if self.mode == "endpoints" and not self.ending:
            raise ValueError("Décris l’état d’arrivée pour un plan à deux images.")
        return self


class Breakdown(Contract):
    title: str = Field(min_length=1, max_length=120)
    shots: list[Shot] = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def unique_ids(self):
        if len({s.id for s in self.shots}) != len(self.shots):
            raise ValueError("Chaque plan doit avoir un identifiant distinct.")
        return self


def image_context(p, shot):
    s = p["settings"]
    return dict(master=p["master_asset_id"], world=s["world"], cook=s["cook"],
                ratio=s["aspect_ratio"], opening=shot["opening"], ending=shot["ending"],
                framing=shot["framing"], mode=shot["mode"], model=s["edit_model_id"])


def image_key(p, shot):
    return digest(image_context(p, shot))


def selected_image(p, shot):
    holder = p["media"].get(shot["id"], {})
    return next((a for a in holder.get("images", []) if a["id"] == holder.get("selected_image")), None)


def clip_key(p, shot, image):
    s = p["settings"]
    shot = {k:shot[k] for k in Shot.model_fields}
    return digest(dict(shot=shot, image=image["id"], start=image["start_asset_id"], end=image.get("end_asset_id"),
                       world=s["world"], cook=s["cook"], camera=s["camera"], audio=s["audio"],
                       ratio=s["aspect_ratio"], plan=s["plan_model_id"], writer=s["writer_model_id"]))


def factory_entry(p, shot, image, attempt_id):
    s = p["settings"]
    config = configuration("h3")
    config.update(preset="custom", shot_count=1, cinematic_settings={"shot_count": 1},
                  plan_model_id=s["plan_model_id"], writer_model_id=s["writer_model_id"],
                  creative_axes=dict(scene_life=1, camera=0, extra_motion=0, dialogue=0),
                  creative_audacity=1, creative_freedom=25)
    config["references"] = [dict(asset_id=image["start_asset_id"], role="first_frame", label="Début du geste")]
    if shot["mode"] == "endpoints":
        if not image.get("end_asset_id"):
            raise ValueError("L’image d’arrivée est manquante.")
        config["references"].append(dict(asset_id=image["end_asset_id"], role="last_frame", label="Fin du geste"))
    config["intention"] = "\n".join([
        f"Un seul plan de cuisine continu, {shot['duration']:g} secondes, sans coupe interne.",
        "Une personne cuisine : gestes causaux lisibles, contact des mains et outils avant leur effet. Une seule action principale. Ne pas anticiper les étapes suivantes.",
        "Action : " + shot["action"], "Cadrage : " + shot["framing"],
        "Départ : " + shot["opening"], "Arrivée : " + shot["ending"],
        "Monde matériel : " + s["world"], "Personne : " + s["cook"],
        "Caméra : " + s["camera"], "Son : " + s["audio"],
        "Aucun dialogue, voix off, sous-titre, musique ni titre incrusté. L’image du plat définit son identité et ses ingrédients, pas un état cuit à copier dans une étape crue.",
    ])
    config["render"]["settings"].update(duration_seconds=shot["duration"], aspect_ratio=s["aspect_ratio"])
    config["render"]["music_enabled"] = False
    config["render"]["seed_locked"] = False
    config["dlss"]["enabled"] = False
    config["social"]["enabled"] = False
    return dict(name=(p["name"] + " · " + shot["title"])[:160], config=config,
                source=dict(kind="cooking_recipe", id=p["id"], shot_id=shot["id"],
                            attempt_id=attempt_id, index=p["shots"].index(shot), group=p["name"], view="recipes"))


def new_project(command, name, settings, master=None):
    validated = Settings.model_validate(settings).model_dump(mode="json")
    return dict(schema_version=1, id="recipe-" + digest(command)[:32], version=0,
                name=name.strip() or "Nouvelle recette", settings=validated,
                creation_key=digest(dict(name=name, settings=validated, master=master)),
                master_asset_id=master, master_images=[], shots=[], media={}, jobs=[], commands={},
                breakdown_history=[], approved=None, paused=False, created_at=now(), updated_at=now())
