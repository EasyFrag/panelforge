# CONTINUITY

## Goal

- Construire PanelForge comme un atelier de canon visuel et de recettes ComfyUI versionnées, réutilisable ensuite par une Forge narrative de panels.

## Current state

- Works:
  - `ComfyHttpClient` couvre upload, soumission, history et téléchargement.
  - `character.change_view` possède un contrat métier pur et deux recettes immuables ; `0.2.0` ajoute le contrôle explicite de `multiple_angles_lora_strength`.
  - Assets et runs sont persistés localement avec hashes, prompt exact, workflow compilé, contrôles, lineage, statut et décision humaine.
  - Le cas d’usage complet `asset -> upload -> workflow -> run -> output` utilise le node de sortie déclaré par le manifest.
  - PanelForge Lab fournit upload/réutilisation, contrôles de caméra, slider LoRA, seed exacte, comparaison, review et historique via FastAPI + HTML/CSS/JS natif.
  - Le venv local est installé ; 75 tests passent.
- Broken / missing:
  - Le smoke applicatif réel du 2026-08-08 n’a pas pu démarrer : `192.168.1.72:8188` est injoignable (ping et port TCP 8188 en timeout). Aucun workflow n’a été soumis.
  - La recette d’angle reste `experimental` : seule la force LoRA `1.0` et un cas visuel ont été testés réellement.
  - `character.bootstrap` reste une expérience locale, pas encore une recette intégrée.

## Decisions

- Le Lab et la future Forge restent dans le même monolithe ; ComfyUI demeure l’outil de découverte manuelle des workflows.
- Pas de Gradio, Node, base SQL, moteur de jobs externe ou wrapper universel en V0 ; l’UI est un adapter remplaçable.
- Une recette publiée est immuable, déclare ses bindings et expose seulement des contrôles sélectionnés. Toute valeur non qualifiée est tracée comme override expérimental.
- Le prompt de `change_view` est entièrement verrouillé. Le futur `prompt jitter` Qwen reformulera seulement les prompts déclarés mutables ou protégés, avec invariants explicites ; la seed restera secondaire.
- Un résultat reste candidat jusqu’à décision humaine et ne remplace jamais automatiquement son asset source.

## Next steps

1. Rendre ComfyUI joignable, exécuter le smoke applicatif `0.2.0`, puis qualifier la matrice angle/LoRA sur plusieurs personnages.
2. Promouvoir `character.bootstrap` et ajouter le mode Generate au Lab.
3. Ajouter l’adapter LLM local et le premier profil versionné de compilation / `prompt jitter` Qwen.

## Risks / open questions

- Les vues arrière et cadrages élargis inventent nécessairement des surfaces absentes de la référence ; l’approbation humaine reste indispensable.
- Les plages de sliders expriment une zone d’expérimentation, pas une qualité garantie ; seule `1.0` est qualifiée pour la LoRA d’angle.
- Les runs en cours ne sont pas repris automatiquement après redémarrage du Lab.
