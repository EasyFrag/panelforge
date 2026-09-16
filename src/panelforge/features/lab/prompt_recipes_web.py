"""Small recipe editor and lazy, durable video LLM history endpoints."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, ConfigDict

from panelforge.domain import CompositionStage
from panelforge.application.prompt_recipes import preparation_call_ids


class SaveRecipe(BaseModel):
    model_config = ConfigDict(extra="forbid")
    base_revision: int = Field(ge=1)
    expected_active: int = Field(ge=1)
    fields: dict[str, str]
    note: str = Field(default="", max_length=200)


class ActivateRecipe(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=1)
    expected_active: int = Field(ge=1)


def prompt_recipes_router(recipes, traces, compositions, renders, *, stories=None):
    router = APIRouter(prefix="/api/prompt-recipes")

    def require(value):
        if value is None:
            raise HTTPException(503, "Édition des recettes non configurée. Redémarrez PanelForge avec le nouveau lanceur.")
        return value

    def execute(action):
        try:
            return action()
        except KeyError as error:
            raise HTTPException(404, str(error)) from error
        except ValueError as error:
            raise HTTPException(409, str(error)) from error

    def recipe_store(key):
        from panelforge.domain.stories import RECIPE_ID
        return require(stories.recipes if key == RECIPE_ID and stories is not None else recipes)

    @router.get("")
    def catalog():
        if recipes is None and stories is None:
            require(None)
        entries = recipes.list() if recipes is not None else []
        if stories is not None:
            entries += stories.recipes.list()
        return {"recipes": entries}

    @router.get("/recipe/{key}/{version}")
    def read(key: str, version: str, revision: int | None = None):
        def load():
            store = recipe_store(key)
            return {"recipe": store.get(key, version, revision), "history": store.history(key, version)}
        return execute(load)

    @router.put("/recipe/{key}/{version}")
    def save(key: str, version: str, body: SaveRecipe):
        return execute(lambda: {"recipe": recipe_store(key).save(key, version, **body.model_dump()),
                                "history": recipe_store(key).history(key, version)})

    @router.post("/recipe/{key}/{version}/activate")
    def activate(key: str, version: str, body: ActivateRecipe):
        return execute(lambda: {"recipe": recipe_store(key).activate(key, version, body.revision, body.expected_active),
                                "history": recipe_store(key).history(key, version)})

    @router.get("/preview/{session_id}/{stage}")
    def preview(session_id: str, stage: str):
        # Construct exactly the next request; never dispatch it to a gateway.
        def load():
            if stage not in {"beat_sheet", "final_prompt"}:
                raise ValueError("Choisissez Plan ou Rédaction pour cet aperçu.")
            service = require(compositions)
            request = service.preview_request(session_id, CompositionStage(stage))
            return {"system_prompt": request.system_prompt, "user_prompt": request.user_prompt,
                    "model": request.model_id, "context": request.trace_context,
                    "image_count": len(request.images), "sent": False}
        return execute(load)

    @router.get("/history/session/{session_id}")
    def session_history(session_id: str):
        def load():
            require(compositions).get(session_id)
            return {"calls": require(traces).list(session_id=session_id), "scope": "Préparation de cet atelier"}
        return execute(load)

    @router.get("/history/render/{project_id}/{attempt_id}")
    def render_history(project_id: str, attempt_id: str):
        def load():
            project = require(renders).get(project_id)
            attempt = project.attempt(attempt_id)
            store = require(traces)
            snapshot = store.render_snapshot(attempt_id)
            # DLSS variants reuse the same written prompt; no LLM call is implied.
            if snapshot is None and attempt.dlss:
                snapshot = store.render_snapshot(attempt.dlss.root_attempt_id)
            if snapshot and snapshot["project_id"] != project_id:
                raise ValueError("Le rendu ne correspond pas à cette archive.")
            if snapshot is not None:
                used_calls = set(snapshot["preparation_call_ids"])
            else:
                try:
                    composition = require(compositions).get(project.source_session_id)
                except KeyError:
                    composition = None
                used_calls = set(preparation_call_ids(composition, project.source_prompt_revision_id)) if composition else set()
            calls = store.list(session_id=project.source_session_id, project_id=project_id)
            related = []
            for call in calls:
                context = call["context"]
                if context.get("project_id"):
                    if context["project_id"] != project_id:
                        continue
                    if snapshot is None or context.get("turn_id") not in snapshot["turn_ids"]:
                        continue
                elif call["call_id"] not in used_calls:
                    continue
                related.append(call)
            return {"calls": related, "scope": f"Échanges liés à l'essai {attempt.index}",
                    "manual_prompt": bool(snapshot and snapshot["manual_prompt"]),
                    "historical": snapshot is None}
        return execute(load)

    return router
