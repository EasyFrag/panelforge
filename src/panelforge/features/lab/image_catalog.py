"""Fast Image Lab specs, independent from project/history reads."""
from threading import Lock

from panelforge.infrastructure.background_snapshot import BackgroundSnapshot
from panelforge.infrastructure.krea2_resources import serialize_krea2_resource


class ImageLabCatalogs:
    def __init__(self):
        self._llm = {}
        self._lock = Lock()

    def read(self, resources, service, serialize_llm, *, refresh=False):
        snapshot = getattr(resources, "ui_snapshot", None)
        if not callable(snapshot):
            # Other injected catalog implementations retain their existing contract.
            return {
                "render_models": [serialize_krea2_resource(r) for r in resources.list_models()] if resources else [],
                "loras": [serialize_krea2_resource(r) for r in resources.list_loras()] if resources else [],
                "resource_warnings": list(getattr(resources, "inventory_warnings", lambda: ())()),
                "llm_models": [serialize_llm(m) for m in service.list_models()],
            }
        value, resource_status = snapshot(force=refresh)
        key = id(getattr(service, "gateway", service))
        with self._lock:
            if key not in self._llm:
                def load():
                    models = [serialize_llm(m) for m in service.list_models()]
                    if not models:
                        raise RuntimeError("Inventaire LLM indisponible")
                    return models
                self._llm[key] = BackgroundSnapshot(load)
            cache = self._llm[key]
        models, llm_status = cache.read(force=refresh)
        return {**value, "llm_models": models or [],
                "catalog_status": {"resources": resource_status, "llm": llm_status}}
