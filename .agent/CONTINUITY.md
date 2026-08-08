# CONTINUITY

## Goal

- Construire PanelForge comme un atelier de canon visuel et de recettes ComfyUI versionnées, réutilisable ensuite par une Forge narrative de panels.

## Current state

- Works:
  - `character.change_view@0.2.0` exécute asset → ComfyUI → candidat persistant avec provenance, contrôles, review et historique dans l’Image Lab.
  - Le Prompt Lab découvre les modèles llama.swap et gère 1–8 références avec analyses, corrections, révisions et approbations par image.
  - `minimax.h3.reference@0.2.0` sépare observation visuelle riche et interprétation textuelle selon les usages MiniMax (`subject`, `first_frame`, `keyframe`, etc.) ; une modification amont invalide l’approbation dérivée sans effacer l’historique.
  - L’ajout d’images dans l’UI est cumulatif, avec dédoublonnage, suppression et usages multiples par image.
  - Sessions et images sont persistées ; le domaine reste immuable et indépendant de FastAPI, OpenAI et ComfyUI.
  - L’adaptateur OpenAI-compatible est validé en réel sur le MoE Qwen : 18 modèles listés et inférence image réussie. ComfyUI est joignable via Tailscale.
  - Le venv inclut le SDK `openai` validé. La dernière base vérifiée comptait 85 tests verts ; les changements `0.2.0` n’ont volontairement pas été exécutés pendant la maintenance du serveur. Détails réseau : `docs/local-services.md`.
- Broken / missing:
  - Le Prompt Lab s’arrête après l’interprétation des références : brief français, liberté créative, labels globaux, composition et prompt MiniMax final restent à implémenter.
  - `Qwen3.6-27B` dense n’est pas encore qualifié ; l’UI le préfère dès qu’un ID correspondant apparaît, sinon elle utilise le MoE testé.
  - Le smoke applicatif ComfyUI `character.change_view@0.2.0` n’a pas été rejoué ; la force LoRA `1.0` reste la seule valeur qualifiée.

## Decisions

- PanelForge appelle des APIs ; llama.swap et ComfyUI restent responsables des modèles et du GPU.
- Chaque étape et chaque image ont une action, une révision et une approbation explicites ; aucune chaîne d’agents autonome en V1.
- Workflows et profils de prompt sont des recettes immuables versionnées ; les adapters fournisseur restent en infrastructure.
- UI native FastAPI + HTML/CSS/JS, sans Gradio, Node, base SQL ni framework agentique pour ce jalon.

## Next steps

1. Qualifier `Qwen3.6-27B` dense avec les probes texte, UTF-8, JSON et multi-image.
2. Vérifier localement la migration des sessions, l’ajout cumulatif et les deux portes observation/interprétation lorsque le serveur est stable.
3. Ajouter brief → découpage → direction → prompt final, chacun éditable et approuvable, avec une politique explicite de liberté créative.

## Risks / open questions

- `/v1/models` ne déclare pas fiablement les capacités vision ; conserver un registre de qualifications observées.
- Une révision LLM peut dériver malgré les instructions : approbation humaine et historique restent obligatoires.
- Les sessions et runs en cours ne sont pas repris automatiquement après redémarrage.
