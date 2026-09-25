"""Reference-batch adapter to the existing Qwen queue; no new model-writing call."""
from copy import deepcopy
from threading import Thread
from panelforge.domain import episode_continuity as continuity


class EpisodeStateImages:
    def _is_state_image(self, value, ref):
        return continuity.required_states(value) and bool(ref.get("continuity_state_id"))

    def _queue_state_image(self, identity, batch_id, ref_id):
        with self._lock:
            value = self.store.get(identity)
            batch = value["reference_batch"]
            if batch["batch_id"] != batch_id or batch.get("cancel_requested"):
                return
            ref = self._item(value, "references", ref_id)
            item = self._batch_item(batch, ref_id)
            base = continuity.variant_base(value, ref)
            if not base or not base.get("image_asset_id"):
                item.update(status="waiting_source", phase="En attente de l’image validée de " + (base["name"] if base else ref["name"]), error=None)
                self.store.save(value)
                return
            if self.qwen_edit is None:
                raise ValueError("Qwen est indisponible : importe une image dans cette fiche d’état.")
            signature = continuity.variant_signature(value, ref)
            link = ref.get("qwen_variant") or {}
            project = None
            if link.get("signature") == signature and link.get("project_id"):
                try:
                    project = self.qwen_edit.get(link["project_id"])
                except (KeyError, FileNotFoundError):
                    pass
            if project is None:
                project = self.qwen_edit.create(name=ref["name"][:120], content=self.assets.read_bytes(base["image_asset_id"]))
            stage = project["stages"][0]
            # A previous queue reservation / finished image is reused only for this exact state and base image.
            previous = next((a for a in stage["attempts"] if a["id"] == link.get("batch_attempt_id")
                or (link.get("queue_request_id") and a["request_id"] == link["queue_request_id"])), None)
            retry = previous is None or previous["status"] in {"failed", "cancelled", "interrupted"}
            regenerate = previous and previous["status"] == "succeeded" and ref.get("image_asset_id") == previous.get("output_asset_id")
            if retry or regenerate:
                if stage.get("accepted_attempt_id") or project.get("active_stage_id", stage["id"]) != stage["id"]:
                    project = self.qwen_edit.create(name=ref["name"][:120], content=self.assets.read_bytes(base["image_asset_id"]))
                    stage = project["stages"][0]
                prompt = ("Edit <image1> to depict the same subject in the following persistent visual state. "
                          "Preserve identity, face, style, framing, background and every attribute not explicitly changed. "
                          "The variant appearance below takes priority over any description of an earlier body or outfit. "
                          "One single view of the subject, no text or before/after panel. Requested state:\n" + ref["description"])
                project = self.qwen_edit.update(project["id"], stage["id"], revision=stage["revision"],
                    changes=dict(prompt=prompt, draft=""))
                stage = project["stages"][0]
                ref["qwen_variant"] = dict(project_id=project["id"], signature=signature, source_asset_id=base["image_asset_id"],
                    queue_request_id=f"{batch_id}-{ref_id}")
                item.update(qwen_project_id=project["id"], qwen_stage_id=stage["id"], source_signature=signature,
                            status="queued_render", phase="Variante Qwen · mise en file")
                self.store.save(value)  # Explicit IDs survive interruption before queue submission.
                project = self.qwen_edit.queue_attempt(project["id"], stage["id"], revision=stage["revision"],
                    request_id=f"{batch_id}-{ref_id}")
                previous = next(a for a in project["stages"][0]["attempts"] if a["request_id"] == f"{batch_id}-{ref_id}")
            ref["qwen_variant"] = dict(project_id=project["id"], signature=signature,
                source_asset_id=base["image_asset_id"], batch_attempt_id=previous["id"], queue_request_id=previous["request_id"])
            item.update(qwen_project_id=project["id"], qwen_stage_id=stage["id"], source_signature=signature,
                        attempt_id=previous["id"], status="queued_render", phase="Variante Qwen en file", error=None)
            ref["revision"] += 1
            self.store.save(value)

    def _reconcile_state_image(self, value, item, ref):
        if not item.get("qwen_project_id"):
            return False
        before = deepcopy((item, ref))
        if self.qwen_edit is None:
            item.update(status="failed", phase="Qwen indisponible", error="Importe une image dans cette fiche ou réactive Qwen.")
            return before != (item, ref)
        try:
            project = self.qwen_edit.get(item["qwen_project_id"])
            stage = next(s for s in project["stages"] if s["id"] == item["qwen_stage_id"])
            attempt = next((a for a in stage["attempts"] if a["id"] == item.get("attempt_id")
                           or a["request_id"] == f"{value['reference_batch']['batch_id']}-{ref['id']}"), None)
            if attempt and (ref.get("qwen_variant") or {}).get("project_id") == project["id"]:
                ref["qwen_variant"].update(batch_attempt_id=attempt["id"], queue_request_id=attempt["request_id"])
                item["attempt_id"] = attempt["id"]
            if attempt is None:
                item.update(status="failed", phase="Mise en file interrompue · relancer ce lot", error="Aucun essai Qwen enregistré.")
            elif item.get("source_signature") != continuity.variant_signature(value, ref):
                item.update(status="failed", phase="Variante à actualiser", error="L’image d’identité ou l’état a changé depuis la préparation.")
            elif attempt["status"] == "succeeded":
                asset_id = attempt["output_asset_id"]
                if not any(i["asset_id"] == asset_id for i in ref["images"]):
                    ref["images"].append(dict(asset_id=asset_id, label="Variante Qwen", source_signature=item["source_signature"]))
                selected = ref.get("image_asset_id")
                validated = bool(selected and (selected == asset_id or selected != item.get("initial_asset_id"))
                    and not continuity.variant_stale(value, ref))
                item.update(status="validated" if validated else "ready_for_review",
                    phase="Variante validée" if validated else "Variante prête à valider",
                    selected_asset_id=selected if validated else None,
                    attempt_id=attempt["id"], output_asset_id=asset_id, error=None)
            elif attempt["status"] in {"failed", "cancelled", "interrupted"}:
                item.update(status="failed", phase="Échec de la variante Qwen", error=attempt.get("error") or "Rendu interrompu.")
            else:
                item.update(status="rendering" if attempt["status"] != "queued" else "queued_render",
                    phase="Variante Qwen en cours" if attempt["status"] != "queued" else "Variante Qwen en file")
        except (KeyError, FileNotFoundError, StopIteration) as error:
            item.update(status="failed", phase="Variante Qwen indisponible", error=str(error))
        return before != (item, ref)

    def _resume_state_dependencies(self, identity):
        """Continue only work explicitly selected in the batch, after its source was accepted."""
        with self._lock:
            value = self.store.get(identity)
            batch = value.get("reference_batch")
            if not batch or batch.get("status") != "waiting_review" or batch.get("cancel_requested") or identity in self._active_batches:
                return
            refs = {r["id"]: r for r in value["references"]}
            eligible = [i for i in batch["items"] if i["status"] == "waiting_source"
                        and (continuity.variant_base(value, refs[i["reference_id"]]) or {}).get("image_asset_id")]
            if not eligible:
                return
            batch.update(status="running", phase="Préparation des variantes Qwen")
            self.store.save(value)
            self._active_batches.add(identity)
            try:
                Thread(target=self._reference_batch_worker, args=(identity, batch["batch_id"], {}), daemon=True,
                       name=f"episode-state-images-{identity}").start()
            except BaseException:
                self._active_batches.discard(identity)
                raise

    def _inherit_state_image(self, episode, target, sources):
        from panelforge.domain import story_continuity as ledger
        element = next(e for e in ledger.elements(episode["scenario"]) if e["id"] == target["source_id"])
        change = next(s for s in element["states"] if s["id"] == target["continuity_state_id"])
        wanted = ledger.state_at(element, change["scene_index"], end=change["at"] == "end")
        for _, _, _, same_story, source in sources:
            old = next((e for e in ledger.elements(source["scenario"]) if e["id"] == target["source_id"]
                and e["kind"] == element["kind"] and (same_story or self._identity_key(e["name"]) == self._identity_key(element["name"]))), None)
            if old is None:
                continue
            for state in reversed(old["states"]):
                resolved = ledger.state_at(old, state["scene_index"], end=state["at"] == "end")
                if not resolved["reference_state_id"] or any(resolved[k] != wanted[k] for k in ("appearance", "clothing")):
                    continue
                ref_id = ledger.reference_id(old["id"], resolved["reference_state_id"])
                ref = next((r for r in source["references"] if r["id"] == ref_id and r.get("image_asset_id")
                            and not r.get("continuity_archived") and not continuity.variant_stale(source, r)), None)
                if ref:
                    target.update(image_asset_id=ref["image_asset_id"], image_style=deepcopy(ref.get("image_style")),
                        images=[dict(asset_id=ref["image_asset_id"], label="État visuel hérité")],
                        continuity_source_signature=continuity.variant_signature(episode, target),
                        inherited_image=dict(episode_id=source["episode_id"], reference_id=ref_id, name=ref["name"]))
                    target["images"][0]["source_signature"] = target["continuity_source_signature"]
                    return 1
        return 0
