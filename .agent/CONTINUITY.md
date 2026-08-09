# CONTINUITY

## Goal

- Construire PanelForge comme atelier local de canon visuel et de recettes versionnées, réutilisables ensuite dans une Forge narrative de panels.

## Current state

- Works:
  - Image Lab : `character.change_view@0.2.0` exécute asset → ComfyUI → candidat persistant, avec provenance, contrôles, review et historique.
  - Prompt Lab : observations par image, Brief `minimax.h3.reference@0.3.0`, streaming, édition/révision, approbations et journal borné des appels LLM.
  - Fighter : `fighter.arcade_versus@0.1.0` fournit le flux Ref2VA supervisé plan de références → beat sheet → prompt H3.
  - I2V simple : `0.1.0` reste témoin et `0.2.0` est active. Le premier retour visuel est encourageant ; le prompt androïde respecte mieux durée, progression et état final.
  - Les révisions Observation/Interprétation/Brief/cookbook extraient uniquement le document attendu ; le brut reste dans les logs. Le linter I2VA accepte l’ancre officielle sans répétition, et un résultat LLM terminal n’est plus marqué annulé à cause d’une validation aval.
  - llama.swap garde la responsabilité GPU ; le bouton global `Libérer la VRAM` décharge ses modèles via PanelForge, sans exposer le serveur au navigateur. Les assets du Lab sont versionnés et servis sans cache pour éviter un HTML/JS décalé. Suite complète : 140 tests verts.
- Broken / missing:
  - I2V simple et Fighter ne sont pas encore qualifiés visuellement de bout en bout dans MiniMax H3.
  - Les tags H3 stricts ne sont pas encore compilés : Qwen abrège de façon répétée `[French]` en `FR`/`fr`.
  - Une session ne porte qu’une composition ; comparaison de versions/forks à ajouter. Aucun test navigateur automatisé.

## Decisions

- Les profils portent l’analyse/Brief LLM ; les cookbooks portent les slots, étapes et contrats vidéo. Les deux restent versionnés séparément.
- I2V réutilise l’orchestration existante mais déclare seulement `final_prompt` : aucune étape Fighter cachée.
- `minimax.h3.i2v.simple@0.1.0` reste immuable ; l’onglet sélectionne explicitement `0.2.0` pour les nouveaux parcours.
- La prose reste au LLM, mais les futurs tags H3 stricts seront insérés/normalisés par code depuis des champs structurés ; ne pas surcharger `0.2.0` pour ce cas.
- Chaque livrable reste générable, éditable, révisable et approuvable manuellement ; pas de chaîne d’agents autonome en V1.

## Next steps

1. Rendre et évaluer la vidéo androïde `0.2.0` : rythme, voix/lip-sync et immobilité demandée.
2. Définir le petit contrat structuré de dialogue avant l’intégration/export H3.
3. Ajouter plusieurs compositions/forks par session avant le cookbook Transition.

## Risks / open questions

- La conformité du prompt ne garantit pas la qualité vidéo ; seuls les essais MiniMax H3 qualifient une recette.
- Une rotation à 180° depuis une unique vue frontale force H3 à inventer le dos du sujet ; ce cas bénéficiera d’une référence arrière en Ref2VA.
- L’onglet I2V réutilise pour l’instant le profil générique d’observation/Brief `minimax.h3.reference@0.3.0` ; un profil I2V dédié ne se justifiera que si les tests montrent un manque.
- llama.swap ne fournit pas de pourcentage fiable de chargement ; un stream interrompu ne reprend pas après redémarrage.
- Libérer la VRAM pendant un appel LLM interrompt potentiellement sa génération ; l’interface l’indique dans l’infobulle.
