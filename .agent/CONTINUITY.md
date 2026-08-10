# CONTINUITY

## Goal

- Construire PanelForge comme atelier local de canon visuel et de recettes versionnées, réutilisables ensuite dans une Forge narrative de panels.

## Current state

- Works:
  - Image Lab : `character.change_view@0.2.0` exécute asset → ComfyUI → candidat persistant, avec provenance, contrôles, review et historique.
  - Prompt Lab : observations par image, Brief `minimax.h3.reference@0.3.0`, streaming, édition/révision, approbations et journal borné des appels LLM.
  - Fighter : `fighter.arcade_versus@0.1.0` fournit le flux Ref2VA supervisé plan de références → beat sheet → prompt H3.
  - I2V simple : `0.1.0` reste témoin et `0.2.0` est active. Le premier retour visuel est encourageant ; le prompt androïde respecte mieux durée, progression et état final.
  - Ref2V : `undressing.single_shot@0.9.0` est active. Elle conserve le plan V0.8 détaillé pour la revue, verrouille la construction visible des vêtements et rédige le prompt H3 avec les seuls jalons majeurs. Les résolutions décrivent des résultats observables, sans jargon de rendu 3D.
  - Une caméra explicitement fixe mais mal encodée par le LLM est normalisée en `camera: null` avec avertissement ; un vrai mouvement incohérent, l’ordre impossible, les chevauchements et le JSON illisible restent bloquants.
  - L’arbitrage V0.8 est opérationnel : cartes par conflit, recommandation/décision libre/risque accepté, instruction globale, puis troisième appel optionnel qui réécrit le plan. La nouvelle révision doit être revalidée ; les décisions ignorées ou les conflits supprimés sont rejetés.
  - Audit du run d’arbitrage réel : les trois appels réussissent, mais « reprendre toutes les recommandations » ne modifie que les résolutions. PanelForge signale désormais ce no-op par un avertissement non bloquant ; la densité 10 s et la dérive possible du décor restent à tester côté H3.
  - `0.7.1` reste disponible : elle répare automatiquement une pose finale placée à la fin demandée sans changer les prompts de `0.7.0`.
  - Les révisions Observation/Interprétation/Brief/cookbook extraient uniquement le document attendu. Le Brief normalise ses neuf titres avec ou sans tiret, rejette les sections absentes et revient en haut après génération ; le brut reste dans les logs.
  - llama.swap garde la responsabilité GPU ; le bouton global `Libérer la VRAM` décharge ses modèles via PanelForge, sans exposer le serveur au navigateur. Le sélecteur partagé privilégie `Qwen3.6-27B-Huihui-abliterated-Q8_0`. Suite complète : 195 tests verts.
- Broken / missing:
  - I2V simple, Ref2V et Fighter ne sont pas encore qualifiés visuellement de bout en bout dans MiniMax H3.
  - Les tags H3 stricts ne sont pas encore compilés : Qwen abrège de façon répétée `[French]` en `FR`/`fr`.
  - Une session ne porte qu’une composition ; comparaison de versions/forks à ajouter. Le journal n’a pas encore de statut distinct « LLM terminé, document rejeté ». Aucun test navigateur automatisé.
  - Aucun test navigateur automatisé ; le JSON reste l’éditeur avancé pour corriger précisément un plan.

## Decisions

- Les profils portent l’analyse/Brief LLM ; les cookbooks portent les slots, étapes et contrats vidéo. Les deux restent versionnés séparément.
- I2V réutilise l’orchestration existante mais déclare seulement `final_prompt` : aucune étape Fighter cachée.
- Ref2V réutilise le profil Observation/Brief générique et spécialise seulement son cookbook final ; aucune validation adulte n’est dupliquée dans PanelForge, ce contrôle étant assuré en amont du serveur.
- Le format strict Ref2V V0.2 est compilé par le code depuis quatre champs LLM ; les révisions repassent par le même compilateur et le Brief partagé reste inchangé.
- Ref2V V0.3+ conserve les trois étapes visibles Observation → Brief → Prompt, mais son bouton final orchestre deux appels : plan JSON validé et auto-approuvé, puis rédaction. La seconde observation est filtrée en apparence seule avant le planner ; aucune règle n’a été ajoutée au Brief partagé.
- Ref2V V0.6 versionne un retiming entièrement algorithmique : mêmes templates que V0.5, gestes simples inchangés, redistribution bornée et métadonnées d’ajustement retirées avant le writer.
- Ref2V V0.7 garde les contrôles structurels indispensables, mais rend consultatifs les labels, landmarks et durées supérieures à 15 s. Elle conserve le décalage pose → caméra au lieu de raccourcir la mise en scène.
- Ref2V V0.7.1 ne change aucun prompt : son parseur tolère une marge finale récupérable, puis le retiming ajoute la tenue manquante. Un ordre ou un chevauchement impossible reste bloquant.
- Ref2V V0.8 sépare le planner et le writer par une approbation humaine. Le code ne devine plus la durée d’une action ; il valide les intervalles, répare seulement la marge finale et conserve les ambiguïtés comme avertissements.
- Une réconciliation d’arbitrage est un troisième appel LLM explicite et optionnel. Le code contrôle la structure et la traçabilité des décisions ; l’utilisateur contrôle toujours la pertinence du plan réécrit avant approbation.
- Le run V0.3 du 2026-08-09 a validé les deux appels mais révélé un rejet applicatif des champs inline et une contradiction `frontal_axis`/orbite ; correctifs portés par le compilateur et la V0.4 sans altérer la recette témoin.
- `minimax.h3.i2v.simple@0.1.0` reste immuable ; l’onglet sélectionne explicitement `0.2.0` pour les nouveaux parcours.
- La prose reste au LLM, mais les futurs tags H3 stricts seront insérés/normalisés par code depuis des champs structurés ; ne pas surcharger `0.2.0` pour ce cas.
- Chaque livrable reste générable, éditable, révisable et approuvable manuellement ; pas de chaîne d’agents autonome en V1.

## Next steps

1. Rejouer V0.9 sur les mêmes références et comparer fluidité, topologie et décor avec V0.8.
2. Valider la grammaire par jalons majeurs sur un second vêtement de construction différente.
3. Prototyper ensuite un cookbook de scène complexe fondé sur invariants → beats → réactions → états persistants.

## Risks / open questions

- La conformité du prompt ne garantit pas la qualité vidéo ; seuls les essais MiniMax H3 qualifient une recette.
- Une rotation à 180° depuis une unique vue frontale force H3 à inventer le dos du sujet ; ce cas bénéficiera d’une référence arrière en Ref2VA.
- L’onglet I2V réutilise pour l’instant le profil générique d’observation/Brief `minimax.h3.reference@0.3.0` ; un profil I2V dédié ne se justifiera que si les tests montrent un manque.
- Ref2V fait le même choix ; la seconde image peut influencer excessivement pose ou décor malgré le contrat textuel, ce qui doit être mesuré dans H3.
- La détection des contradictions V0.8 vient du planner LLM ; le code sait les conserver et les signaler, pas comprendre arbitrairement quelles zones un vêtement couvre.
- Les sous-gestes réduisent le risque de clipping mais ne garantissent pas la simulation des doigts, du tissu ou de la gravité par H3. Une durée supérieure à 15 s reste dépendante du moteur ciblé.
- La topologie V0.9 est guidée par les observations et contrôlée humainement ; le code ne sait pas encore prouver qu’un terme vestimentaire est visuellement exact.
- La variante Ref2V à une seule référence corporelle, avec vêtements initiaux décrits, est différée à une version ultérieure.
- llama.swap ne fournit pas de pourcentage fiable de chargement ; un stream interrompu ne reprend pas après redémarrage.
- Libérer la VRAM pendant un appel LLM interrompt potentiellement sa génération ; l’interface l’indique dans l’infobulle.
