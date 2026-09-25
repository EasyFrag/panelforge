"""Library-only commands; no writing or production endpoint is invoked."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from panelforge.application.story_library import StoryLibraryService
from panelforge.domain.story_library import LibraryConflict


class GroupEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=0, strict=True)
    title: str | None = Field(default=None, min_length=1, max_length=160)
    favorite: bool | None = Field(default=None, strict=True)


class ProjectEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=0, strict=True)
    trashed: bool | None = Field(default=None, strict=True)
    group_id: str | None = Field(default=None, pattern="^story-[a-f0-9]{32}$")
    episode_number: int | None = Field(default=None, ge=1, le=9999, strict=True)


def story_library_router(stories, episodes=None):
    router = APIRouter(prefix="/api/stories/library")
    library = StoryLibraryService(stories, episodes) if stories is not None else None

    def invoke(action):
        if library is None:
            raise HTTPException(503, "La bibliothèque Histoires n’est pas configurée.")
        try:
            return action()
        except FileNotFoundError as error:
            raise HTTPException(404, "Histoire introuvable.") from error
        except LibraryConflict as error:
            raise HTTPException(409, str(error)) from error
        except (ValueError, TypeError) as error:
            raise HTTPException(422, str(error)) from error

    @router.get("")
    def get_library():
        return invoke(lambda: library.view())

    @router.patch("/groups/{identity}")
    def edit_group(identity: str, body: GroupEdit):
        return invoke(lambda: library.update("group", identity, **body.model_dump(exclude_unset=True)))

    @router.patch("/projects/{identity}")
    def edit_project(identity: str, body: ProjectEdit):
        return invoke(lambda: library.update("project", identity, **body.model_dump(exclude_unset=True)))

    return router
