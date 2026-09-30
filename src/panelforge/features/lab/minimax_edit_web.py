"""MiniMax endpoints with the same HTTP actions as the Qwen workshop."""
from panelforge.domain import minimax_edit as policy
from .qwen_edit_web import qwen_edit_router


def minimax_edit_router(service):
    return qwen_edit_router(service, engine="minimax", label="Minimax", policy=policy, render_after_prompt=True)
