"""User-run regressions for story addressees; no real models or renders."""
from copy import deepcopy
import json
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
import unittest

from panelforge.application.story_v2 import StoryV2Service
from panelforge.application.story_v2_production import StoryV2Production
from panelforge.domain.episodes import scene_inputs
from panelforge.domain.story_v2 import audience_view, validate_script, validate_polish, writing_schema
from panelforge.infrastructure.storage.episodes import LocalEpisodeStore
from panelforge.infrastructure.storage.story_v2 import LocalStoryV2Store
from tests.test_story_v2 import Gateway, Production, screenplay, settings


def addressed_script():
    script = screenplay()
    script["characters"].append(dict(id="leo", name="Léo", description="Adulte en sweat bleu",
                                      relationship="Ami de Mia et Marc"))
    scene = script["sequences"][0]
    scene.update(character_ids=["mia", "marc", "leo"], appearances=[],
                 action="Mia donne son assiette à Léo puis répond à Marc.")
    scene["dialogue"] = [dict(speaker_id="mia", text="Je suis déjà avec Léo.", delivery="spoken",
        addressee_ids=["marc"], address_cue="Mia tourne brièvement son regard vers Marc pour lui répondre.")]
    return script


class StoryV2AddressingTest(unittest.TestCase):
    def test_old_script_round_trips_without_new_empty_keys_or_guessed_recipients(self):
        script = screenplay()
        self.assertEqual(validate_script(script, settings()), script)
        explicit = deepcopy(script)
        explicit["sequences"][0]["dialogue"][0].update(addressee_ids=[], address_cue="")
        self.assertEqual(validate_script(explicit, settings()), script)
        schema = writing_schema(settings())["$defs"]["Dialogue"]
        self.assertTrue({"addressee_ids", "address_cue"} <= set(schema["required"]))

    def test_unknown_duplicate_and_self_recipients_are_rejected(self):
        for recipients in (["unknown"], ["marc", "marc"], ["mia"]):
            with self.subTest(recipients=recipients):
                script = addressed_script()
                script["sequences"][0]["dialogue"][0]["addressee_ids"] = recipients
                with self.assertRaisesRegex(ValueError, "destinataire"):
                    validate_script(script, settings())
        script = addressed_script()
        script["sequences"][0]["dialogue"][0].update(addressee_ids=["marc", "leo"], address_cue="")
        self.assertEqual(validate_script(script, settings())["sequences"][0]["dialogue"][0]["addressee_ids"], ["marc", "leo"])

    def test_cues_are_short_and_need_an_identified_recipient(self):
        for update in ({"addressee_ids":[]}, {"address_cue":"a"*181}, {"address_cue":"Regarde Marc.\nPuis Léo."}):
            with self.subTest(update=update):
                script = addressed_script()
                script["sequences"][0]["dialogue"][0].update(update)
                with self.assertRaises(ValueError):
                    validate_script(script, settings())

    def test_export_addresses_the_listener_not_the_person_named_in_the_line(self):
        script = addressed_script()
        with TemporaryDirectory() as folder:
            store = LocalEpisodeStore(folder)
            adapter = StoryV2Production(NS(store=store), None)
            project = dict(id="storyv2-"+"c"*32, version=1, settings=settings(), script=script, episode_id=None)
            identity = adapter.export(project)
            self.assertEqual(adapter.export(project), identity)
            episode = store.get(identity)
            raw = scene_inputs(episode, episode["scenes"][0], require_images=False)["source_text"]
            self.assertIn("Réplique 1 — Mia s'adresse à Marc.", raw)
            self.assertNotIn("Mia s'adresse à Léo", raw)
            self.assertIn(script["sequences"][0]["dialogue"][0]["address_cue"], raw)
            self.assertEqual(raw.count("Je suis déjà avec Léo."), 1)
            self.assertIn("Rythme de l'échange", raw)
            self.assertEqual(set(episode["scenario"]["scenes"][0]["dialogue"][0]), {"speaker_id", "text", "delivery"})
            self.assertEqual(episode["scenes"][0]["duration"], 10)
            self.assertEqual(episode["scenes"][0]["preparations"], [])
            self.assertEqual(episode["scenes"][0]["creative_axes"], project["settings"]["video"]["creative_axes"])

    def test_offscreen_or_remote_recipient_does_not_add_a_visible_reference(self):
        for delivery in ("spoken", "off_screen", "mediated"):
            with self.subTest(delivery=delivery), TemporaryDirectory() as folder:
                script = addressed_script()
                scene = script["sequences"][0]
                scene["character_ids"] = ["mia", "leo"]
                scene["dialogue"][0].update(delivery=delivery,
                    address_cue="Mia répond à Marc, qui reste hors champ." if delivery != "mediated" else "")
                script = validate_script(script, settings())
                store = LocalEpisodeStore(folder)
                adapter = StoryV2Production(NS(store=store), None)
                episode = store.get(adapter.export(dict(id="storyv2-"+"d"*32, version=1,
                    settings=settings(), script=script, episode_id=None)))
                refs = {r["id"]:r for r in episode["references"]}
                self.assertNotIn("marc", [refs[r["reference_id"]]["source_id"] for r in episode["scenes"][0]["references"]])
                self.assertEqual(episode["scenario"]["scenes"][0]["dialogue"][0]["delivery"], delivery)
                self.assertIn("Mia s'adresse à Marc", scene_inputs(episode, episode["scenes"][0], require_images=False)["source_text"])

    def test_polish_keeps_recipients_and_reader_gets_only_the_visible_cue(self):
        original = addressed_script()
        patch = dict(sequences=[dict(id=s["id"], action=s["action"], dialogue=[d["text"] for d in s["dialogue"]])
                                for s in original["sequences"]])
        patch["sequences"][0]["dialogue"][0] = "Je vois déjà Léo ce soir."
        polished = validate_polish(patch, original, settings())
        line = polished["sequences"][0]["dialogue"][0]
        self.assertEqual(line["addressee_ids"], ["marc"])
        self.assertEqual(line["address_cue"], original["sequences"][0]["dialogue"][0]["address_cue"])
        evidence = audience_view(polished)[0]["dialogue"][0]
        self.assertEqual(evidence["visible_address"], line["address_cue"])
        self.assertNotIn("addressee_ids", evidence)
        self.assertNotIn("visible_address", audience_view(screenplay())[0]["dialogue"][0])
        self.assertEqual(original["sequences"][0]["dialogue"][0]["text"], "Je suis déjà avec Léo.")

    def test_automatic_path_keeps_two_calls_and_stops_in_factory_preparation(self):
        with TemporaryDirectory() as folder:
            store = LocalStoryV2Store(folder)
            gateway = Gateway([addressed_script(), dict(understood="Mia répond à Marc au sujet de Léo.", issues=[])])
            production = Production()
            service = StoryV2Service(store, gateway, production)
            project = service.create("addressee-patch-test", settings("automatic"))
            service.tick(project["id"])
            current = store.get(project["id"])
            self.assertEqual(current["status"], "references", current.get("error"))
            self.assertEqual(current["script"]["sequences"][0]["dialogue"][0]["addressee_ids"], ["marc"])
            self.assertEqual(len(gateway.requests), 2)
            self.assertEqual(len(production.started), 1)
            evidence = json.loads(gateway.requests[1].user_prompt)
            self.assertIn("visible_address", evidence["scenes"][0]["dialogue"][0])
            production.ready = True
            production.episode["reference_batch"] = {"status":"completed"}
            service.tick(project["id"])
            self.assertEqual(store.get(project["id"])["status"], "prepared")
            self.assertEqual(production.rows[0]["status"], "preparation")
            self.assertEqual(len(gateway.requests), 2)
            self.assertFalse(production.launched)


if __name__ == "__main__":
    unittest.main()
