"""Dedicated MH journal; shared atomic project/asset/workflow persistence."""
from .qwen_edits import LocalQwenEditStore


class LocalMhAssistedStore(LocalQwenEditStore):
    engine = "mh"
    label = "Création Assistée MH"
