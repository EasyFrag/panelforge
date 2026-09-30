"""Separate MiniMax project journal with the existing atomic store contract."""
from .qwen_edits import LocalQwenEditStore


class LocalMinimaxEditStore(LocalQwenEditStore):
    engine = "minimax"
    label = "Minimax"
