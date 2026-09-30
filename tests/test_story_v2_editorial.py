"""User-run editorial regressions; fake model/production clients only."""
from copy import deepcopy
import json
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from panelforge.application.story_v2 import StoryV2Service
from panelforge.application.story_v2_production import StoryV2Production
from panelforge.domain.story_v2 import (
    Settings, default_settings, scene_durations, validate_script, validate_polish, writing_schema,
)
from panelforge.infrastructure.storage.story_v2 import LocalStoryV2Store
from tests.test_story_v2 import Gateway, Production, screenplay, settings

GOOD = dict(understood="Le couple accueille son enfant.", issues=[])
BAD = dict(understood="La naissance est ambiguë.", issues=["Clarifier la naissance."])


def polish_of(script=None):
    script = script or screenplay()
    value = dict(sequences=[dict(id=s["id"], action=s["action"],
        dialogue=[line["text"] for line in s["dialogue"]]) for s in script["sequences"]])
    value["sequences"][0]["dialogue"][0] = "Notre bébé arrive bientôt."
    return value


class StoryV2EditorialTest(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = LocalStoryV2Store(self.temp.name)
        self.gateway, self.production = Gateway([]), Production()
        self.service = StoryV2Service(self.store, self.gateway, self.production)

    def create(self, values, *, enabled=True, mode="manual", final_review=True):
        self.gateway.values = deepcopy(values)
        config = {**settings(mode), "writer_model":"author", "reader_model":"reader",
                  "polish_enabled":enabled, "polish_model":"prose", "final_review_enabled":final_review}
        p = self.service.create("editorial-command", config)
        self.identity = p["id"]
        return p

    def latest(self):
        return self.store.get(self.identity)

    def tick(self):
        self.service.tick(self.identity)
        return self.latest()

    def test_defaults_and_exact_sixty_second_plan_reject_five_twelve_second_scenes(self):
        self.assertEqual(default_settings()["scene_duration"], 10)
        self.assertFalse(default_settings()["polish_enabled"])
        self.assertFalse(default_settings()["final_review_enabled"])
        config = {**settings(), "duration":60}
        self.assertEqual(scene_durations(config), [10]*6)
        schema = writing_schema(config)
        self.assertEqual(schema["properties"]["sequences"]["minItems"], 6)
        self.assertEqual(schema["properties"]["sequences"]["maxItems"], 6)
        self.assertEqual(schema["$defs"]["Sequence"]["properties"]["duration"]["enum"], [10])
        script = screenplay()
        script["sequences"] = [dict(deepcopy(script["sequences"][0]), id=f"seq-{i+1}", duration=12) for i in range(5)]
        with self.assertRaisesRegex(ValueError, "Découpage attendu"):
            validate_script(script, config)
        with self.assertRaisesRegex(ValueError, "Découpage attendu"):
            StoryV2Production(None, None).export({"script":script, "settings":config})
        script["sequences"] = [dict(deepcopy(script["sequences"][0]), id=f"seq-{i+1}", duration=10) for i in range(6)]
        self.assertEqual(validate_script(script, config), script)

    def test_non_multiple_totals_are_preserved_with_valid_clip_lengths(self):
        self.assertEqual(scene_durations(dict(duration=61, scene_duration=10)), [10]*5+[6,5])
        self.assertEqual(scene_durations(dict(duration=26, scene_duration=10)), [10,10,6])
        for total in range(10,181):
            for target in range(5,16):
                durations = scene_durations(dict(duration=total, scene_duration=target))
                self.assertEqual(sum(durations), total)
                self.assertTrue(all(5 <= v <= 15 for v in durations))
                self.assertLessEqual(len(durations), 36)
                if total % target == 0:
                    self.assertTrue(all(v == target for v in durations))
        with self.assertRaisesRegex(ValueError, "18 scènes"):
            Settings.model_validate({**settings(), "duration":180, "scene_duration":5})
        self.assertEqual(len(scene_durations(dict(duration=180, scene_duration=10))), 18)
        for value in (4,16,True):
            with self.assertRaises(ValueError):
                Settings.model_validate({**settings(), "scene_duration":value})

    def test_disabled_polish_keeps_two_call_path_when_first_review_passes(self):
        self.create([screenplay(),GOOD], enabled=False)
        out = self.tick()
        self.assertEqual([r.model_id for r in self.gateway.requests], ["author","reader"])
        self.assertEqual(out["progress"]["index"], 2)
        self.assertEqual(out["progress"]["total"], 2)
        self.assertFalse(out["history"])

    def test_four_calls_use_independent_models_and_final_reader_sees_before_after(self):
        self.create([screenplay(),GOOD,polish_of(),GOOD])
        observed = []
        self.gateway.hook = lambda: observed.append(self.service.get(self.identity)["progress"])
        out = self.tick()
        self.assertEqual(out["status"], "awaiting_review", out.get("error"))
        self.assertEqual([r.model_id for r in self.gateway.requests], ["author","reader","prose","reader"])
        self.assertEqual([(p["index"],p["total"]) for p in observed], [(1,4),(2,4),(3,4),(4,4)])
        self.assertTrue(all(p["status"] == "running" and p["started_at"] for p in observed))
        self.assertTrue(all(c["finished_at"] and c["elapsed_seconds"] >= 0 for c in out["calls"]))
        self.assertEqual(out["progress"]["status"], "succeeded")
        evidence = json.loads(self.gateway.requests[-1].user_prompt)
        self.assertEqual(evidence["scenes"][0]["dialogue"][0]["text"], "Notre bébé arrive bientôt.")
        self.assertEqual(evidence["pre_polish_scenes"][0]["dialogue"][0]["text"], "Notre bébé va bientôt naître.")
        self.assertNotIn("intention", evidence["scenes"][0])
        public = self.service.get(self.identity)
        self.assertTrue(all("result" not in c for c in public["calls"]))
        self.assertNotIn("pre_polish", public["scenario"])
        self.assertEqual(len(out["history"]), 2)
        self.assertEqual([h["reason"] for h in out["history"]], ["A · avant retouche","B · après retouche"])
        self.service.restore(self.identity, out["version"], 0)
        self.assertEqual(self.latest()["script"], screenplay())
        self.service.restore(self.identity, self.latest()["version"], 1)
        self.assertEqual(self.latest()["script"], out["script"])
        self.assertEqual(len(self.gateway.requests), 4)

    def test_repair_precedes_polish_and_five_calls_are_the_normal_maximum(self):
        repaired = screenplay()
        repaired["sequences"][1]["action"] = "Mia et Marc rentrent de la maternité avec leur nouveau-né."
        self.create([screenplay(),BAD,repaired,polish_of(repaired),GOOD])
        out = self.tick()
        self.assertEqual([c["step"] for c in out["calls"]], ["write","review","repair","polish","final_review"])
        self.assertEqual([(c["index"],c["total"]) for c in out["calls"]], [(1,4),(2,4),(3,5),(4,5),(5,5)])
        self.assertEqual([r.model_id for r in self.gateway.requests], ["author","reader","author","prose","reader"])
        self.assertEqual(json.loads(self.gateway.requests[3].user_prompt)["screenplay"], repaired)
        self.assertEqual(len(out["history"]), 2)

    def test_final_review_problem_stops_automatic_media_and_does_not_loop(self):
        self.create([screenplay(),GOOD,polish_of(),BAD], mode="automatic")
        out = self.tick()
        self.assertEqual(out["status"], "awaiting_review")
        self.assertEqual(len(self.gateway.requests), 4)
        self.assertFalse(self.production.exported or self.production.started or self.production.sent)
        self.tick()
        self.assertEqual(len(self.gateway.requests), 4)

    def test_successful_automatic_polish_continues_to_references_then_preparation_only(self):
        self.create([screenplay(),GOOD,polish_of(),GOOD], mode="automatic")
        out = self.tick()
        self.assertEqual(out["status"], "references")
        self.assertEqual(len(self.production.started), 1)
        self.production.ready = True
        self.production.episode["reference_batch"] = {"status":"completed"}
        out = self.tick()
        self.assertEqual(out["status"], "prepared")
        self.assertEqual(self.production.rows[0]["status"], "preparation")
        self.assertFalse(self.production.launched)
        self.assertEqual(len(self.gateway.requests), 4)

    def test_final_control_options_adjust_calls_and_automatic_continues_after_repair(self):
        for polish in (False, True):
            for final in (False, True):
                for repair in (False, True):
                    with self.subTest(polish=polish, final=final, repair=repair), TemporaryDirectory() as temp:
                        values = [screenplay(), BAD if repair else GOOD]
                        steps = ["write", "review"]
                        if repair:
                            values.append(screenplay());steps.append("repair")
                        if polish:
                            values.append(polish_of());steps.append("polish")
                        if final and (repair or polish):
                            values.append(GOOD);steps.append("final_review")
                        gateway, production = Gateway(values), Production()
                        store = LocalStoryV2Store(temp)
                        service = StoryV2Service(store, gateway, production)
                        p = service.create("option-matrix", {**settings("automatic"),
                            "polish_enabled":polish, "final_review_enabled":final})
                        service.tick(p["id"])
                        out = store.get(p["id"])
                        self.assertEqual(out["status"], "references", out.get("error"))
                        self.assertEqual([c["step"] for c in out["calls"]], steps)
                        initial = 2 + int(polish) * (1 + int(final))
                        self.assertEqual([(c["index"], c["total"]) for c in out["calls"]],
                            [(i, initial if i <= 2 else len(steps)) for i in range(1, len(steps)+1)])
                        if not final and (repair or polish):
                            self.assertIsNone(out["review"])  # Earlier issues describe a replaced version.
                        self.assertEqual(out["script"]["sequences"][0]["dialogue"][0]["text"],
                            "Notre bébé arrive bientôt." if polish else "Notre bébé va bientôt naître.")
                        production.ready = True
                        production.episode["reference_batch"] = {"status":"completed"}
                        service.tick(p["id"])
                        self.assertEqual(store.get(p["id"])["status"], "prepared")
                        self.assertFalse(production.launched)
                        self.assertEqual(len(gateway.requests), len(steps))

    def test_final_control_choice_is_saved_independently_from_polish(self):
        out = self.create([], enabled=True, final_review=False)
        self.assertFalse(self.service.preferences()["final_review_enabled"])
        out["status"] = "draft";self.store.save(out)
        self.service.update(out["id"], out["version"], None, {**out["settings"], "final_review_enabled":True})
        service = StoryV2Service(self.store, self.gateway, self.production)
        self.assertTrue(service.preferences()["final_review_enabled"])
        self.assertTrue(service.preferences()["polish_enabled"])
        self.assertFalse(self.gateway.requests)

    def test_disabled_final_control_still_rejects_invalid_polish(self):
        invalid = polish_of();invalid["sequences"][0]["dialogue"] = []
        self.create([screenplay(), GOOD, invalid], mode="automatic", final_review=False)
        out = self.tick()
        self.assertEqual(out["status"], "failed")
        self.assertEqual(out["script"], screenplay())
        self.assertFalse(self.production.exported or self.production.started)

    def test_pause_after_polish_without_final_control_resumes_at_references(self):
        self.create([screenplay(), GOOD, polish_of()], mode="automatic", final_review=False)
        self.gateway.hook = lambda: self.service.pause(self.identity) if len(self.gateway.requests)==3 else None
        out = self.tick()
        self.assertEqual(out["status"], "paused")
        self.assertEqual(out["scenario"]["next_step"], "done")
        self.assertFalse(self.production.exported)
        self.gateway.hook = None
        self.service.resume(self.identity, out["version"])
        out = self.tick()
        self.assertEqual(out["status"], "references")
        self.assertEqual(len(self.gateway.requests), 3)

    def test_legacy_pending_final_control_is_preserved_until_explicit_resume(self):
        out = self.create([BAD], mode="automatic")
        out["settings"].pop("final_review_enabled")
        out["scenario"].pop("final_review")
        out["scenario"]["next_step"] = "final_review"
        out.update(status="paused", resume_stage="reviewing", script=screenplay(), needs_review=True)
        self.store.save(out)
        self.assertTrue(self.service.get(self.identity)["settings"]["final_review_enabled"])
        self.assertNotIn("final_review_enabled", self.latest()["settings"])
        self.assertFalse(self.gateway.requests)
        self.service.resume(self.identity, out["version"])
        out = self.tick()
        self.assertEqual([c["step"] for c in out["calls"]], ["final_review"])
        self.assertEqual(out["status"], "awaiting_review")
        self.assertEqual(out["review"]["issues"], BAD["issues"])
        self.assertFalse(self.production.exported)

    def test_polish_cannot_change_cast_speakers_duration_or_dialogue_density(self):
        original = screenplay()
        value = validate_polish(polish_of(), original, settings())
        frozen = deepcopy(value)
        for before,after in zip(original["sequences"], frozen["sequences"]):
            after["action"] = before["action"]
            for old,new in zip(before["dialogue"], after["dialogue"]):
                new["text"] = old["text"]
        self.assertEqual(frozen, original)
        changes = []
        v = polish_of();v["characters"] = [];changes.append(v)
        v = polish_of();v["sequences"][0]["duration"] = 12;changes.append(v)
        v = polish_of();v["sequences"].reverse();changes.append(v)
        v = polish_of();v["sequences"][0]["dialogue"].append("Nouvelle réplique.");changes.append(v)
        v = polish_of();v["sequences"][0]["dialogue"] = ["mot "*40];changes.append(v)
        for invalid in changes:
            with self.subTest(value=invalid), self.assertRaises(ValueError):
                validate_polish(invalid, original, settings())
        self.assertEqual(original, screenplay())

    def test_pause_after_polish_resumes_with_only_final_review(self):
        self.create([screenplay(),GOOD,polish_of(),GOOD])
        self.gateway.hook = lambda: self.service.pause(self.identity) if len(self.gateway.requests)==3 else None
        out = self.tick()
        self.assertEqual(out["status"], "paused")
        self.assertEqual(out["scenario"]["next_step"], "final_review")
        self.assertEqual(len(out["history"]), 2)
        self.gateway.hook = None
        self.service.resume(self.identity, out["version"])
        out = self.tick()
        self.assertEqual(len(self.gateway.requests), 4)
        self.assertEqual(len(out["history"]), 2)
        self.assertEqual(out["status"], "awaiting_review")

    def test_invalid_polish_keeps_A_and_explicit_retry_does_not_rewrite(self):
        invalid = polish_of();invalid["sequences"][0]["dialogue"] = []
        self.create([screenplay(),GOOD,invalid,polish_of(),GOOD])
        out = self.tick()
        self.assertEqual(out["status"], "failed")
        self.assertEqual(out["script"], screenplay())
        self.assertEqual(out["scenario"]["next_step"], "polish")
        self.service.resume(self.identity, out["version"])
        out = self.tick()
        self.assertEqual([c["step"] for c in out["calls"]], ["write","review","polish","polish","final_review"])
        self.assertEqual(len(out["history"]), 2)
        self.assertEqual(out["progress"]["index"], 5)
        self.assertEqual(out["progress"]["total"], 5)

    def test_checkpointed_accepted_response_is_applied_without_a_duplicate_call(self):
        self.create([screenplay(),GOOD], enabled=False)
        save = self.service._save
        def interrupted(p):
            if p.get("scenario",{}).get("next_step") == "review" and p.get("script"):
                raise RuntimeError("Simulated interruption before applying the checkpoint")
            return save(p)
        with patch.object(self.service, "_save", side_effect=interrupted):
            out = self.tick()
        self.assertEqual(out["status"], "failed")
        self.assertTrue(out["calls"][0]["accepted"])
        self.assertIsNone(out["script"])
        self.service.resume(self.identity, out["version"])
        out = self.tick()
        self.assertEqual(out["status"], "awaiting_review")
        self.assertEqual(len(self.gateway.requests), 2)
        self.assertEqual(len(out["calls"]), 2)

    def test_new_rewrite_cycle_resets_counter_and_uses_current_settings(self):
        self.create([screenplay(),GOOD], enabled=False)
        out = self.tick()
        first_cycle = out["scenario"]["id"]
        self.gateway.values = [screenplay(),GOOD]
        self.service.revise(self.identity, out["version"], "Conserve les événements, précise les intentions.")
        out = self.tick()
        self.assertNotEqual(out["scenario"]["id"], first_cycle)
        self.assertEqual([c["index"] for c in out["calls"]], [1,2,1,2])

    def test_new_duration_can_be_saved_but_must_be_rewritten_before_approval(self):
        self.create([screenplay(),GOOD], enabled=False)
        out = self.tick()
        changed = {**out["settings"], "duration":30}
        self.service.update(self.identity, out["version"], out["script"], changed)
        out = self.latest()
        self.assertTrue(out["timing_pending"])
        self.assertEqual(out["script"], screenplay())
        self.assertEqual(len(self.gateway.requests), 2)
        with self.assertRaisesRegex(ValueError, "Découpage attendu"):
            self.service.approve(self.identity, out["version"])

    def test_restart_freezes_interrupted_timer_and_waits_for_explicit_resume(self):
        out = self.create([polish_of(),GOOD])
        out.update(status="polishing", script=screenplay())
        out["scenario"]["next_step"] = "polish"
        call = dict(id="interrupted-call", cycle_id=out["scenario"]["id"], step="polish", role="polish",
                    model="prose", index=1, total=2, label="Retouche des dialogues",
                    started_at=out["created_at"], status="running", accepted=False)
        out["calls"].append(call)
        out["progress"] = deepcopy(call)
        self.store.save(out)
        with patch("panelforge.application.story_v2.Thread"):
            self.service.start_worker()
        out = self.latest()
        self.assertEqual(out["status"], "paused")
        self.assertEqual(out["progress"]["status"], "interrupted")
        self.assertGreaterEqual(out["progress"]["elapsed_seconds"], 0)
        self.assertFalse(self.gateway.requests)
        self.service.resume(self.identity, out["version"])
        out = self.tick()
        self.assertEqual(out["status"], "awaiting_review")
        self.assertEqual([r.model_id for r in self.gateway.requests], ["prose","reader"])

    def test_legacy_load_and_restore_keep_existing_timing_without_runtime_migration(self):
        out = self.create([], enabled=False)
        old = screenplay()
        old["sequences"][0]["duration"],old["sequences"][1]["duration"] = 12,8
        legacy_settings = {k:v for k,v in out["settings"].items() if k not in {"scene_duration","polish_enabled","polish_model"}}
        out.update(settings=legacy_settings, status="awaiting_review", script=old,
                   history=[dict(at="2026-09-29T00:00:00+00:00",script=old,settings=legacy_settings,reason="Legacy")])
        self.store.save(out)
        public = self.service.get(self.identity)
        self.assertIsNone(public["settings"]["scene_duration"])
        self.assertNotIn("scene_duration", self.latest()["settings"])
        self.service.restore(self.identity, public["version"], 0)
        self.assertEqual(self.latest()["script"], old)
        self.assertIsNone(self.latest()["settings"]["scene_duration"])
        self.assertFalse(self.gateway.requests)


if __name__ == "__main__":
    unittest.main()
