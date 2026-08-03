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
- Broken / missing:
  - Aucun contrat métier implémenté.
  - Aucun workflow ComfyUI intégré.
  - Le transport ComfyUI n'est pas encore validé contre une instance réelle.
  - Aucun polling, parsing des outputs ou upload d'image n'est encore implémenté.
  - Aucune interface utilisateur.

## Decisions

- Les expérimentations workflow/prompt ont lieu manuellement dans ComfyUI, hors de PanelForge.
- Un preset intégré est immuable et décrit explicitement workflow, prompt, bindings, modèles, LoRA et variables.
- Premier jalon: fiche personnage manuelle -> candidats -> sélection -> édition -> canon approuvé.
- Vidéo hors V1.
- Premier port technique retenu: transport ComfyUI minimal `submit/history/download`, configuration explicite, timeout explicite et exceptions remontées; pas de WebSocket, retry, logs ou politique d'erreurs dans cette première brique.
- L'adapter LLM viendra avec l'import d'histoire et n'exposera d'abord qu'un appel `complete`; parsing JSON et validation resteront hors du transport.

## Next steps

1. Fournir puis intégrer un premier workflow `character.bootstrap` validé manuellement, avec son manifest de bindings.
2. Ajouter dans la couche application le polling et l'extraction des références de sortie, puis valider le transport sur une instance ComfyUI réelle.
3. Ajouter `upload_image` pour l'édition du canon, puis l'adapter LLM minimal lors de l'import d'histoire.

## Risks / open questions

- Le premier workflow et son contrat d'entrées/sorties ne sont pas encore fournis.
- Le choix du framework UI reste volontairement ouvert.
- Le code legacy reste disponible en lecture dans `D:\Code\localQ`; tout portage devra rester ciblé et accompagné de tests plutôt que copier des modules entiers.
