# CONTINUITY

## Goal

- Construire PanelForge comme un monolithe modulaire centré sur un canon visuel approuvé et des presets ComfyUI versionnés.

## Current state

- Works:
  - Squelette Python minimal créé.
  - Frontières `domain`, `application`, `features` et `infrastructure` posées.
  - Convention initiale des workflows documentée.
  - Dépôt Git initialisé dans `D:\Code\panelforge`.
  - Test d'import standard library validé (`python -m unittest discover -s tests`).
  - Baseline minimale enregistrée dans un commit Git initial.
  - Audit legacy ciblé terminé: protocoles ComfyUI `queue/history/view/upload` et noyau d'appel LLM OpenAI-compatible isolés des anciennes couches d'orchestration.
  - `ComfyHttpClient` implémenté en standard library avec trois opérations: `submit_workflow`, `get_history`, `download_output`.
  - Le transport utilise `base_url`, `client_id` et timeout explicites; les erreurs HTTP, réseau et JSON ne sont pas interceptées.
  - Six tests unitaires passent, dont cinq sur le protocole ComfyUI sans serveur réel (`python -m unittest discover -s tests -v`).
  - Smoke test manuel ajouté dans `scripts/smoke_comfy.py`: chargement d'un workflow API externe, soumission, polling borné, extraction de la première image, téléchargement et validation PNG.
  - Le smoke test affiche le corps des erreurs HTTP ComfyUI et les causes d'accès réseau sans ajouter cette politique au client de transport.
  - Onze tests unitaires passent au total, dont cinq tests ciblés sur le polling et l'extraction du smoke test.
  - Smoke test réel réussi contre ComfyUI sur `http://192.168.1.72:8188`: prompt `6e32c579-b43d-4adb-a1fd-860553fb7888`, sortie PNG du node `15` téléchargée (`2699593` octets).
- Broken / missing:
  - Aucun contrat métier implémenté.
  - Aucun workflow ComfyUI intégré.
  - Aucun polling ou parsing des outputs n'est encore implémenté dans la couche application; aucun upload d'image n'est disponible.
  - Aucune interface utilisateur.

## Decisions

- Les expérimentations workflow/prompt ont lieu manuellement dans ComfyUI, hors de PanelForge.
- Un preset intégré est immuable et décrit explicitement workflow, prompt, bindings, modèles, LoRA et variables.
- Premier jalon: fiche personnage manuelle -> candidats -> sélection -> édition -> canon approuvé.
- Vidéo hors V1.
- Premier port technique retenu: transport ComfyUI minimal `submit/history/download`, configuration explicite, timeout explicite et exceptions remontées; pas de WebSocket, retry, logs ou politique d'erreurs dans cette première brique.
- L'adapter LLM viendra avec l'import d'histoire et n'exposera d'abord qu'un appel `complete`; parsing JSON et validation resteront hors du transport.
- Le polling présent dans `scripts/smoke_comfy.py` reste un harness de validation manuelle et ne constitue pas encore l'orchestration applicative.

## Next steps

1. Intégrer le workflow Qwen validé techniquement comme premier preset `character.bootstrap` avec son manifest de bindings.
2. Ajouter le polling et l'extraction des sorties dans la couche application, en réutilisant les comportements validés par le smoke test.
3. Ajouter ensuite `upload_image` pour l'édition du canon.

## Risks / open questions

- Le workflow Qwen candidat est fourni et validé techniquement, mais son manifest d'entrées/sorties n'est pas encore défini.
- Le workflow Qwen fonctionne sur l'instance cible, mais sa qualité comme recette canon reste à valider: prompts positif/négatif identiques, résolution lourde et bindings encore implicites.
- Le choix du framework UI reste volontairement ouvert.
- Le code legacy reste disponible en lecture dans `D:\Code\localQ`; tout portage devra rester ciblé et accompagné de tests plutôt que copier des modules entiers.
