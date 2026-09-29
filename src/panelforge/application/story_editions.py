"""Version selection and provenance, without model calls or text changes."""
from copy import deepcopy
from panelforge.domain import long_stories as narrative
from panelforge.domain.story_editions import reference_fingerprint


class StoryEditionSelection:
    def __init__(self, service):
        self.service = service

    def catalog(self):
        recipes = self.service.long_recipes
        return recipes.editions.public_catalog() if recipes else dict(latest=None, editions=[])

    def package(self, project, *, retry_job=None):
        if self.service.long_recipes is None:
            raise ValueError("Le catalogue des versions d’écriture n’est pas configuré dans ce Lab.")
        editions = self.service.long_recipes.editions
        selection = project.get("writing_edition")
        if retry_job is not None:
            package = editions.identify(retry_job.get("editorial_fingerprint"))
            if package is None:
                raise ValueError("La version de cet appel interrompu n’est pas disponible. Choisis une version et lance une nouvelle opération ; le brouillon reste conservé.")
            if selection and package["fingerprint"] != selection["fingerprint"]:
                raise ValueError("La version sélectionnée a changé. Rétablis celle de l’appel pour le reprendre, ou lance une nouvelle opération.")
            return package
        if selection:
            package = editions.get(selection["id"])
            if package["fingerprint"] != selection["fingerprint"]:
                raise ValueError("L’empreinte de la version enregistrée ne correspond plus au catalogue.")
            return package
        fingerprint = reference_fingerprint(project)
        if fingerprint:
            package = editions.identify(fingerprint)
            if package:
                return package
        doc = project.get("document") or {}
        if not fingerprint and not any(doc.get(key) for key in ("concepts", "series_outline", "scenario")) and not project.get("job"):
            return editions.get()
        raise ValueError("Version historique non identifiée. Choisis une version d’écriture à côté de Mes histoires pour les prochains appels. Les textes actuels restent conservés.")

    def describe(self, project):
        if not narrative.is_v2(project):
            return None
        try:
            selected = deepcopy(self.package(project)["edition"])
            error = None
        except (ValueError, OSError) as exc:
            selected, error = None, str(exc)
        last = next((r for r in reversed(project.get("revisions", [])) if r.get("editorial_fingerprint")), {})
        result_edition = last.get("writing_edition")
        if not result_edition and last.get("editorial_fingerprint"):
            try:
                identified = self.service.long_recipes.editions.identify(last["editorial_fingerprint"]) if self.service.long_recipes else None
                result_edition = identified["edition"] if identified else None
            except (ValueError, OSError):
                result_edition = None
        return dict(selected=selected, error=error,
                    result_edition=result_edition, result_fingerprint=last.get("editorial_fingerprint"))

    def select(self, project_id, *, expected_version, edition_id):
        service = self.service
        with service._lock:
            project = service._editable(project_id, expected_version)
            if not narrative.is_v2(project):
                raise ValueError("Les versions d’écriture concernent le mode histoire longue.")
            if (project.get("workflow") or {}).get("status") == "running" or (project.get("job") or {}).get("status") in {"running", "cancelling"}:
                from .stories import StoryConflict
                raise StoryConflict("Attends la fin ou suspends la chaîne avant de changer de version d’écriture.")
            package = service.long_recipes.editions.get(edition_id)
            project["writing_edition"] = deepcopy(package["edition"])
            # Existing results and approvals are not invalidated by a preference change.
            project.pop("writing_edition_info", None)
            service.store.save(project)
            return service.get(project_id)
