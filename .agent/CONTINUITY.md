# CONTINUITY

## Goal

- Construire PanelForge comme atelier local de canon visuel et de recettes versionnées, puis réutiliser ces briques dans une Forge narrative de panels.

## Current state

- Works:
  - Image Lab : `character.change_view@0.2.0` exécute asset → ComfyUI → candidat persistant, avec provenance, contrôles, review et historique.
  - Prompt Lab : 1–8 images → observations approuvées → Brief `minimax.h3.reference@0.3.0`, avec streaming, édition, révision, invalidation et journal borné des appels LLM.
  - `fighter.arcade_versus@0.1.0/readable-v1` ajoute un flux Ref2VA supervisé : affectations structurées → plan de références → beat sheet → prompt H3 final, chaque étape étant persistée, révisable et approuvable.
  - Les définitions approuvées sont compilées sans régénération ; summary/rétention sont écrits après la beat sheet. Mapping Picture local, usages requis, linter H3, snapshots et sauvegarde CAS sont couverts.
  - llama.swap garde la responsabilité GPU ; ComfyUI et LLM restent des services distants. Suite complète : 121 tests verts.
- Broken / missing:
  - Fighter V1 n’a pas encore été qualifié visuellement de bout en bout avec le LLM local puis MiniMax H3 ; ses paramètres sont encore fixes.
  - Une session ne porte qu’une composition ; comparaison de versions/forks à ajouter avant Transition. `Qwen3.6-27B` dense et les variantes LoRA hors `1.0` ne sont pas qualifiés.

## Decisions

- Les profils décrivent le travail LLM ; les cookbooks décrivent un type de vidéo et ses slots. Ils sont versionnés séparément.
- Fighter est le premier cas visible ; le socle Ref2VA commun reste générique. Transition utilisera ensuite son propre contrat T2VA/FL2VA.
- Chaque étape reste déclenchable, éditable et approuvable ; pas de chaîne d’agents autonome en V1.
- Les labels et dépendances sont structurés ; le LLM rédige les documents mais ne décide ni des affectations ni de leur numérotation.

## Next steps

1. Tester manuellement Fighter V1 sur le serveur local et examiner chaque document intermédiaire.
2. Versionner les corrections de recette/linter issues des sorties H3 réelles.
3. Ajouter plusieurs compositions par session, puis Transition comme deuxième cookbook.

## Risks / open questions

- Les contraintes de forme ne garantissent pas la qualité vidéo ; les tests H3 réels restent la source de qualification.
- Le navigateur n’a pas encore de test automatisé ; l’API et les contrats sont couverts, mais le parcours UI doit être smoke-testé manuellement.
- llama.swap ne fournit pas de vrai pourcentage de chargement ; un stream interrompu ne reprend pas après redémarrage.
