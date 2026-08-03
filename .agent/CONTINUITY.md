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
- Broken / missing:
  - Aucun contrat métier implémenté.
  - Aucun workflow ComfyUI intégré.
  - Aucune interface utilisateur.

## Decisions

- Les expérimentations workflow/prompt ont lieu manuellement dans ComfyUI, hors de PanelForge.
- Un preset intégré est immuable et décrit explicitement workflow, prompt, bindings, modèles, LoRA et variables.
- Premier jalon: fiche personnage manuelle -> candidats -> sélection -> édition -> canon approuvé.
- Vidéo hors V1.

## Next steps

1. Définir les contrats minimaux `Asset`, `IntegratedWorkflow`, `GenerationRun` et `CharacterCanon`.
2. Intégrer un premier workflow `character.bootstrap` validé manuellement.
3. Implémenter le cas d'usage de génération de candidats sans choisir encore un framework UI complet.

## Risks / open questions

- Le premier workflow et son contrat d'entrées/sorties ne sont pas encore fournis.
- Le choix du framework UI reste volontairement ouvert.
- Le code legacy reste disponible en lecture dans `D:\Code\localQ`; tout portage devra rester ciblé et accompagné de tests plutôt que copier des modules entiers.
