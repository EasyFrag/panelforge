# REF2V 0.2.1 — deux résolutions indépendantes

Évolution du rendu courant 0.2.0, conservé intact pour les essais historiques.

- `initial_megapixels` expose la résolution de première passe via le manifeste.
- `megapixels` reste la cible finale après upscale.
- Preset : **0,2 MP initiaux et 0,2 MP finaux**, tous deux modifiables. Le Lab propose la réutilisation du seed par défaut.
- Même graphe, modèles, LoRA, références, steps et progression ; seule la valeur par défaut du nœud de MP finaux passe de 1,2 à 0,2. Aucun nouveau traitement ajouté.

Les valeurs choisies sont conservées dans l’essai et transmises par le service au workflow compilé. Le 0.2.0 est toujours accessible en reprise avec sa version et son empreinte d’origine.

Régressions préparées : `tests.test_ref2v_render_resolution`, assemblage Lab et contrôles navigateur H3/REF2V. **Non exécutées par l’agent**, aucun appel LLM ou génération.
