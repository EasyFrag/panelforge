# PanelForge — Histoires longues V2, 20 septembre 2026

Version de sauvegarde des changements depuis `8c8257e`, après PanelForge 1.0.0. La version de l’application et les versions propres aux recettes restent inchangées.

- Branche : `snapshots/long-stories-v2-2026-09-20`
- Tag : `snapshot-long-stories-v2-2026-09-20`

## Changements inclus

- Moteur des nouvelles histoires longues : une proposition, contrat narratif, architecture en séquences ou épisodes, mémoire et relectures ; les projets historiques conservent leur parcours.
- Modes Automatique et Manuel guidé, regroupement de certains appels, retours ciblés sur histoire/séquence/scène, corrections bornées et reprise de l’étape échouée.
- Création allégée, exemples et aides, suppression du nombre de propositions, explication du verrou de fabrication et action de reprise accessible.
- Récupération contrôlée de réponses avec mémoire mal imbriquée ou règles écrites en phrases ; brouillons et validations conservés.
- Plafond de sortie porté à 80 000 tokens pour les appels du moteur long, raisonnement inclus.
- Suivi Plan / Rédacteur / Vidéo / DLSS, couleurs et coches, correction du débordement du bandeau Traitements, suivi et pause des tâches en file.
- Corpus d’évaluation, fixtures et tests de régression déjà écrits, audits narratifs et brief d’adaptation français.

## Validation et limites

Les vérifications statiques de syntaxe Python/JavaScript et de structure JSON sont effectuées pour cette publication. Les tests automatisés ne sont pas exécutés, conformément au choix explicite de l’utilisateur ; les fichiers de tests sont inclus pour qu’il puisse les lancer. Aucun appel LLM, rendu ou redémarrage n’est déclenché pour publier cette version.

Les audits documentent les limites observées : arbitrage instable entre langue du brief et sélecteur, franglais introduit dans un contrat, relectures parfois coûteuses ou discutables. Ce snapshot conserve l’implémentation actuelle ; ces analyses ne constituent pas des correctifs supplémentaires ni une garantie de qualité narrative.

Les vidéos, assets, traces LLM complètes et projets de travail restent dans le workspace local ignoré par Git. Certains liens de preuves dans les audits renvoient donc à des fichiers locaux. Les fixtures éditoriales sélectionnées sont incluses dans les tests.

## Documentation

- [Guide Histoires longues V2](../long-stories-v2.md)
- [Audit des appels et de la version française](../diagnostics/audit-poison-langue-et-qualite-2026-09-20.md)
- [Réglages et brief français prêts à coller](../essai-poison-francais-2026-09-20.md)
- [Audit du registre de tromperie](../diagnostics/derive-trahison-gouttes-2026-09-20.md)

Pour utiliser ce code après mise à jour, redémarrer PanelForge lorsque les traitements sont terminés, puis recharger le navigateur avec Ctrl+F5. Le code fonctionne avec le workspace existant ; cette sauvegarde Git ne contient pas les projets générés.
