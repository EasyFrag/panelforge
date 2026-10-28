"""MiniMax endpoints with the same HTTP actions as the Qwen workshop."""
from panelforge.domain import minimax_edit as policy
from .qwen_edit_web import qwen_edit_router
from fastapi import HTTPException


def minimax_edit_router(service):
    router = qwen_edit_router(service, engine="minimax", label="Minimax", policy=policy, render_after_prompt=True)

    @router.get("/loras")
    def loras(refresh: bool = False):
        if service is None:
            raise HTTPException(503, "L’atelier MiniMax n’est pas configuré.")
        return service.lora_inventory(refresh=refresh)

    return router
