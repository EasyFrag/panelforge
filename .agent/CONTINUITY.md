# CONTINUITY

## Goal

- Construire PanelForge comme atelier local de canon visuel et de recettes versionnées, réutilisables ensuite dans une Forge narrative de panels.

## Current state

- Works:
  - Image Lab : `character.change_view@0.2.0` exécute asset → ComfyUI → candidat persistant, avec provenance, contrôles, review et historique.
  - Prompt Lab : observations par image, Brief `minimax.h3.reference@0.3.0`, streaming, édition/révision, approbations et journal borné des appels LLM.
  - Fighter : `fighter.arcade_versus@0.1.0` fournit le flux Ref2VA supervisé plan de références → beat sheet → prompt H3.
  - I2V simple : `0.1.0` reste témoin et `0.2.0` est active. Le premier retour visuel est encourageant ; le prompt androïde respecte mieux durée, progression et état final.
  - Ref2V : `undressing.single_shot@0.2.0` compile correctement ses quatre champs LLM en prompt mono-plan verrouillé ; le premier run est cohérent et plus direct, mais omet les repères temporels et retarde le regard joueur demandé. `0.1.0` reste le témoin à six sections.
  - Les révisions Observation/Interprétation/Brief/cookbook extraient uniquement le document attendu ; le Brief reconnaît ses titres `- TITRE` et rejette strictement les sorties incomplètes, tandis que le brut reste dans les logs. Le linter Ref2VA exige toujours une définition autonome de `<Picture 1>`.
  - llama.swap garde la responsabilité GPU ; le bouton global `Libérer la VRAM` décharge ses modèles via PanelForge, sans exposer le serveur au navigateur. Les assets du Lab sont servis sans cache. Suite complète : 149 tests verts.
- Broken / missing:
  - I2V simple, Ref2V et Fighter ne sont pas encore qualifiés visuellement de bout en bout dans MiniMax H3.
  - Les tags H3 stricts ne sont pas encore compilés : Qwen abrège de façon répétée `[French]` en `FR`/`fr`.
  - Une session ne porte qu’une composition ; comparaison de versions/forks à ajouter. Le journal n’a pas encore de statut distinct « LLM terminé, document rejeté ». Aucun test navigateur automatisé.

## Decisions

- Les profils portent l’analyse/Brief LLM ; les cookbooks portent les slots, étapes et contrats vidéo. Les deux restent versionnés séparément.
- I2V réutilise l’orchestration existante mais déclare seulement `final_prompt` : aucune étape Fighter cachée.
- Ref2V réutilise le profil Observation/Brief générique et spécialise seulement son cookbook final ; aucune validation adulte n’est dupliquée dans PanelForge, ce contrôle étant assuré en amont du serveur.
- Le format strict Ref2V V0.2 est compilé par le code depuis quatre champs LLM ; les révisions repassent par le même compilateur et le Brief partagé reste inchangé.
- `minimax.h3.i2v.simple@0.1.0` reste immuable ; l’onglet sélectionne explicitement `0.2.0` pour les nouveaux parcours.
- La prose reste au LLM, mais les futurs tags H3 stricts seront insérés/normalisés par code depuis des champs structurés ; ne pas surcharger `0.2.0` pour ce cas.
- Chaque livrable reste générable, éditable, révisable et approuvable manuellement ; pas de chaîne d’agents autonome en V1.

## Next steps

1. Réviser puis rendre le premier prompt Ref2V V0.2 avec 2–3 repères temporels et le regard joueur dès l’action ; comparer ensuite sur un second couple de références.
2. Définir le petit contrat structuré de dialogue I2V avant l’intégration/export H3.
3. Ajouter plusieurs compositions/forks par session avant le cookbook Transition.

## Risks / open questions

- La conformité du prompt ne garantit pas la qualité vidéo ; seuls les essais MiniMax H3 qualifient une recette.
- Une rotation à 180° depuis une unique vue frontale force H3 à inventer le dos du sujet ; ce cas bénéficiera d’une référence arrière en Ref2VA.
- L’onglet I2V réutilise pour l’instant le profil générique d’observation/Brief `minimax.h3.reference@0.3.0` ; un profil I2V dédié ne se justifiera que si les tests montrent un manque.
- Ref2V fait le même choix ; la seconde image peut influencer excessivement pose ou décor malgré le contrat textuel, ce qui doit être mesuré dans H3.
- La variante Ref2V à une seule référence corporelle, avec vêtements initiaux décrits, est différée à une version ultérieure.
- llama.swap ne fournit pas de pourcentage fiable de chargement ; un stream interrompu ne reprend pas après redémarrage.
- Libérer la VRAM pendant un appel LLM interrompt potentiellement sa génération ; l’interface l’indique dans l’infobulle.
