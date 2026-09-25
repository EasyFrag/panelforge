"""Bounded editorial orchestration. Each step uses the existing story worker and gateway."""
from copy import deepcopy
from uuid import uuid4

from panelforge.domain import long_stories as narrative
from panelforge.domain.story_diagnostics import project_quality


def new_workflow(mode):
    if mode not in {"automatic", "manual"}:
        raise ValueError("Choisissez Automatique ou Manuel guidé.")
    return dict(mode=mode, status="paused", message="Prêt à imaginer l’histoire.", approvals={},
                repairs={}, calls=0, budget_calls=0, wait_target=None, pause_requested=False)


class StoryWorkflow:
    def __init__(self, service):
        self.service = service

    def advance(self, project_id, expected_version, mode=None, architect_model_id=None, writer_model_id=None):
        with self.service._lock:
            project = self.service._editable(project_id, expected_version)
            if not narrative.is_v2(project):
                raise ValueError("Le parcours guidé concerne les histoires longues V2.")
            for role, model in (("architect_model_id", architect_model_id), ("writer_model_id", writer_model_id)):
                if model is not None:
                    if not isinstance(model, str) or not model.strip() or len(model) > 300:
                        raise ValueError("Choisissez un modèle disponible pour chaque rôle.")
                    project[role] = model.strip()
            flow = project.setdefault("workflow", new_workflow(mode or "manual"))
            if mode is not None:
                if mode not in {"manual", "automatic"}:
                    raise ValueError("Mode de rédaction inconnu.")
                flow["mode"] = mode
            if flow.get("wait_target") and flow["status"] == "awaiting_author":
                target = flow["wait_target"]
                flow["approvals"][target] = narrative.source_hash(project, target)
            if flow.get("status") == "blocked" and flow.get("budget_calls", flow["calls"]) >= 4 * project["long_options"]["unit_count"] + 8:
                flow["budget_calls"] = 0  # Explicit author continuation opens a new bounded budget.
            flow.update(status="running", pause_requested=False, wait_target=None)
            # Repair allowances persist across resume: continuing must not create an unbounded loop.
            project = self.service.store.save(project)
            return self.tick(project)

    def correct_and_continue(self, project_id, *, expected_version, unit_id, mode=None,
                             architect_model_id=None, writer_model_id=None):
        """One explicit repair, then a mandatory review before resuming the chosen mode."""
        with self.service._lock:
            project = self.service._editable(project_id, expected_version)
            flow, doc = project.get("workflow"), project["document"]
            if (not narrative.is_v2(project) or not flow or flow["status"] != "blocked"
                    or flow.get("wait_target") != unit_id or unit_id == "outline"
                    or unit_id not in doc.get("episode_scenarios", {})):
                raise ValueError("Ouvre la séquence bloquée avant de demander sa correction.")
            if not narrative.review_current(project, unit_id):
                raise ValueError("Le scénario a changé depuis sa relecture. Relis cette séquence avant de la corriger.")
            if not any(i["severity"] == "blocking" for i in doc["reviews"][unit_id]["issues"]):
                raise ValueError("Cette séquence ne présente que des observations facultatives : aucune correction automatique à lancer.")
            status = narrative.status(project)
            if (not status["outline_reviewed"] or not status["units"][unit_id]["previous_ready"]
                    or status["units"][unit_id]["stale"]):
                raise ValueError("Valide d’abord l’histoire et les séquences précédentes ; cette séquence doit être à jour.")
            for role, model in (("architect_model_id", architect_model_id), ("writer_model_id", writer_model_id)):
                if model is not None:
                    if not isinstance(model, str) or not model.strip() or len(model) > 300:
                        raise ValueError("Choisissez un modèle disponible pour chaque rôle.")
                    project[role] = model.strip()
            if mode is not None:
                if mode not in {"manual", "automatic"}:
                    raise ValueError("Mode de rédaction inconnu.")
                flow["mode"] = mode
            flow.update(status="running", pause_requested=False, budget_calls=0,
                        correction=dict(unit_id=unit_id, phase="repair"))
            # Consume the allowance up front: continuing or reloading cannot silently repair again.
            flow["repairs"][unit_id] = flow["repairs"].get(unit_id, 0) + 1
            return self._call(project, "repair_episode", target=unit_id)

    def pause(self, project_id):
        with self.service._lock:
            project = self.service.get(project_id)
            flow = project.get("workflow")
            if not flow:
                raise ValueError("Cette histoire n’utilise pas encore le parcours guidé.")
            flow.pop("correction", None)
            flow.update(mode="manual", pause_requested=True,
                        message="Reprise en main demandée : l’appel actif termine, puis l’enchaînement s’arrête.")
            if project_id not in self.service._active:
                flow.update(status="paused", pause_requested=False, message="Tu peux maintenant écrire ton retour.")
            return self.service.store.save(project)

    def _stop(self, project, status, message, target=None):
        project["workflow"].pop("correction", None)
        project["workflow"].update(status=status, message=message, wait_target=target)
        if target and target != "outline" and project["document"]["episode_scenarios"].get(target):
            project["document"]["selected_episode_id"] = target
            project["document"]["scenario"] = deepcopy(project["document"]["episode_scenarios"][target])
        return self.service._normalize(self.service.store.save(project))

    def _call(self, project, operation, *, target=None, block=None):
        doc, flow = project["document"], project["workflow"]
        if flow.get("budget_calls", flow["calls"]) >= 4 * project["long_options"]["unit_count"] + 8:
            return self._stop(project, "blocked", "La limite de travail automatique est atteinte. Les textes sont conservés.")
        if target:
            doc["selected_episode_id"] = target
            doc["scenario"] = deepcopy(doc["episode_scenarios"].get(target))
        labels = {"compose": "Invention de l’histoire et de sa progression…", "edit_outline": "Vérification et ajustement de l’histoire…",
                  "develop": "Rédaction de la séquence…", "review_block": "Vérification des scènes et de leurs raccords…",
                  "repair_episode": "Correction ciblée de la séquence…"}
        flow.update(message=labels[operation], wait_target=None)
        project = self.service.store.save(project)
        try:
            return self.service.start(project["project_id"], operation=operation, instruction="",
                expected_version=project["version"], request_id=str(uuid4()), review_unit_ids=block,
                workflow_step=True)
        except Exception as error:
            return self._stop(self.service.store.get(project["project_id"]), "blocked", str(error), target)

    def tick(self, project):
        """Called under the service lock, at a boundary with no active LLM worker."""
        flow, doc = project.get("workflow"), project["document"]
        if not flow or flow["status"] != "running":
            return self.service._normalize(project)
        if flow.get("pause_requested"):
            flow["pause_requested"] = False
            return self._stop(project, "paused", "Enchaînement suspendu. Écris ton retour ou continue quand tu veux.")
        job = project.get("job") or {}
        if job.get("operation") != "discuss" and job.get("status") in {"failed", "interrupted", "cancelled"} and job.get("narrative_input_hash") in {None, narrative.input_hash(project)}:
            if not (job.get("draft") or "").strip():
                return self._stop(project, "blocked", "L’étape a été arrêtée avant réception d’un scénario. Les détails sont conservés ; reprends l’étape pour faire un nouvel essai.")
            return self._stop(project, "blocked", "L’étape a été arrêtée. Le résultat et les détails sont conservés ; revalide le brouillon ou reprends l’étape.")
        correction = flow.get("correction")
        if correction:
            target = correction["unit_id"]
            if correction["phase"] == "repair":
                if job.get("operation") != "repair_episode" or job.get("status") != "succeeded":
                    return self._stop(project, "blocked", "La correction n’a pas abouti. Le scénario précédent est conservé.", target)
                correction["phase"] = "review"
                return self._call(project, "review_block", target=target, block=[target])
            if not narrative.review_current(project, target):
                return self._stop(project, "blocked", "La relecture de la correction n’a pas abouti. Relis cette séquence pour poursuivre.", target)
            if not narrative.review_clear(project, target):
                return self._stop(project, "blocked", "Des points bloquants subsistent après cette correction et sa relecture. Aucune autre correction n’a été lancée.", target)
            # The explicit 'continue' approves only this corrected unit. Other manual checkpoints stay intact.
            flow["approvals"][target] = narrative.source_hash(project, target)
            flow.pop("correction", None)
        if not doc.get("series_outline"):
            return self._call(project, "compose")
        if not narrative.review_current(project, "outline"):
            return self._call(project, "edit_outline")
        if not narrative.review_clear(project, "outline"):
            if flow["repairs"].get("outline", 0) < 1:
                flow["repairs"]["outline"] = 1
                return self._call(project, "edit_outline")
            return self._stop(project, "blocked", "Un choix reste à préciser dans l’histoire. Écris ton retour sur l’histoire complète.", "outline")
        if flow["mode"] == "manual" and flow["approvals"].get("outline") != narrative.source_hash(project, "outline"):
            return self._stop(project, "awaiting_author", "L’histoire est prête à discuter. Valide sa direction pour développer les scènes.", "outline")
        flow["approvals"]["outline"] = narrative.source_hash(project, "outline")
        units = doc["series_outline"]["episodes"]
        states = narrative.status(project)["units"]
        pending = []
        block_size = 2 if flow["mode"] == "automatic" and project["long_options"]["delivery"] == "continuous" else 1
        for unit in units:
            identity, state = unit["id"], states[unit["id"]]
            if not state["written"] or state["stale"]:
                if pending and flow["mode"] == "manual":
                    return self._call(project, "review_block", block=pending)
                return self._call(project, "develop", target=identity)
            if (not narrative.review_current(project, identity) and
                    any(item["level"] == "blocking" for item in project_quality(project, identity))):
                # A proven local budget problem does not need a model call to be discovered.
                # It blocks approval and triggers the existing single correction allowance.
                doc.setdefault("reviews", {})[identity] = narrative.validate_review(project,
                    {"summary": "Contrôle local de faisabilité ; relecture éditoriale encore nécessaire.", "issues": []}, identity)
            if not narrative.review_current(project, identity):
                pending.append(identity)
                if len(pending) >= block_size:
                    return self._call(project, "review_block", block=pending)
                continue
            if pending:
                return self._call(project, "review_block", block=pending)
            if not narrative.review_clear(project, identity):
                if flow["repairs"].get(identity, 0) >= 1:
                    return self._stop(project, "blocked", "Une difficulté subsiste après la correction. Écris un retour sur cette séquence.", identity)
                flow["repairs"][identity] = flow["repairs"].get(identity, 0) + 1
                return self._call(project, "repair_episode", target=identity)
            if flow["mode"] == "manual" and flow["approvals"].get(identity) != narrative.source_hash(project, identity):
                doc["selected_episode_id"] = identity
                doc["scenario"] = deepcopy(doc["episode_scenarios"][identity])
                return self._stop(project, "awaiting_author", "Cette séquence est prête. Écris ton retour ou valide pour continuer.", identity)
            flow["approvals"][identity] = narrative.source_hash(project, identity)
        if pending:
            return self._call(project, "review_block", block=pending)
        return self._stop(project, "ready", "Le scénario est prêt. Tu peux le parcourir, le modifier ou préparer sa fabrication.")

    def feedback(self, project_id, *, expected_version, unit_id, scene_index, instruction, question=False):
        if not isinstance(instruction, str) or not instruction.strip() or len(instruction) > 12000:
            raise ValueError("Écris un retour ou une question de 1 à 12 000 caractères.")
        with self.service._lock:
            project = self.service._editable(project_id, expected_version)
            if not narrative.is_v2(project) or not project["document"].get("series_outline"):
                raise ValueError("Ouvre une histoire longue déjà proposée pour lui adresser un retour.")
            doc = project["document"]
            known = {u["id"] for u in doc["series_outline"]["episodes"]}
            if unit_id not in known | {"outline"}:
                raise ValueError("La cible de ton retour n’existe pas.")
            if unit_id != "outline":
                scenario = doc["episode_scenarios"].get(unit_id)
                if not scenario:
                    raise ValueError("Cette séquence n’est pas rédigée ; adresse ton retour à l’histoire complète.")
                if scene_index is not None and (type(scene_index) is not int or not 0 <= scene_index < len(scenario["scenes"])):
                    raise ValueError("Scène ciblée introuvable.")
                if not question:
                    doc["selected_episode_id"] = unit_id
                    doc["scenario"] = deepcopy(scenario)
            elif scene_index is not None:
                raise ValueError("Une scène doit être rattachée à sa séquence.")
            flow = project.setdefault("workflow", new_workflow("manual"))
            if not question:
                flow.update(mode="manual", status="running", pause_requested=False, budget_calls=0, wait_target=None)
                flow["repairs"].pop(unit_id, None)
            elif flow["status"] == "running":
                flow.update(status="paused", message="Question en cours. Continue le parcours après la réponse.")
            feedback_target = dict(unit_id=unit_id, scene_index=scene_index,
                                   source_hash=narrative.source_hash(project, unit_id), version=project["version"])
            project = self.service.store.save(project)
            try:
                return self.service.start(project_id, operation="discuss" if question else "revise", instruction=instruction,
                    expected_version=project["version"], request_id=str(uuid4()), feedback_target=feedback_target,
                    workflow_step=True)
            except Exception as error:
                if not question:
                    self._stop(self.service.store.get(project_id), "blocked", str(error), unit_id)
                raise
