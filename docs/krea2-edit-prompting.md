# Modifier avec KREA2 — prompting V3

Patch du 8 septembre 2026. Implémenté, tests préparés mais non exécutés.

Évolution suivante : [workflow de rendu 0.2.0 importé, indépendant du prompting](krea2-edit-workflow-base-2026-09-08.md). Le Lab charge désormais les workflows 0.2.0/0.1.0 et écrit le schéma Edit 7 ; les indications de schéma/cache plus bas décrivent le patch initial de prompting seul.

## Utilisation

Dans **Modifier avec KREA2**, sous l'instruction de modification, **Version du prompting** propose :

- **V3 — Modifications ciblées** : instructions d'édition relatives à l'image source de l'étape. Défaut d'un nouvel atelier.
- **V2 — Description complète** : ancien writer conversationnel conservé tel quel pour comparaison.

Une étape ayant déjà des échanges reprend la version de son dernier échange enregistré. Une nouvelle étape hérite de la version du dernier échange de son parent, sinon V3. Les très anciens échanges sans version restent identifiés V1 ; cette option historique est affichée à leur réouverture.

Changer le sélecteur s'applique au **prochain échange LLM**. Cela ne réécrit pas le prompt courant, ne lance rien et ne modifie aucun réglage. Le choix reste en mémoire de l'onglet pendant la navigation ; après un échange réussi, sa version est enregistrée avec la révision et retrouvée au rechargement. Chaque entrée « Voir le prompt » affiche sa version. Les étapes validées et historiques restent en lecture seule.

La conversation reste la même quand on change de writer : ce n'est pas un retour en arrière de mémoire. Pour comparer, conserver la même source, le même prompt de départ et les mêmes réglages/seed ; les changements déjà discutés peuvent continuer d'influencer le contexte. Les anciens prompts et rendus restent consultables.

## Ce que change V3

Le prompt commence par l'opération demandée et sa localisation : remplacer une tache par de la terre, agrandir une ouverture, tapisser son intérieur, etc. Il précise les matériaux et relations utiles, puis quelques contraintes de préservation. Les grandes modifications restent possibles et ne sont pas limitées à une phrase.

Chaque rendu repart de la **source fixe de l'étape**. V3 conserve donc tous les changements encore souhaités dans cette étape ; une correction apportée à un résultat ne doit pas oublier les autres changements absents de la source. L'image sélectionnée en feedback reste une preuve du résultat, jamais une nouvelle source implicite. Après validation, l'image devient la source de l'étape suivante avec une conversation vide.

Le prompt issu des métadonnées de la source est signalé comme description de contexte, pas comme travail à refaire. Un ancien prompt complet V2 ou un prompt modifié manuellement peut servir de cible : V3 doit en exprimer les différences utiles par rapport à la source.

Pour une suppression, décrire ce qui occupe la zone libérée et éviter de répéter l'élément refusé en longues listes de négations. Les exclusions indispensables restent possibles. Le message français explique une proposition ; il n'annonce pas un résultat acquis.

## Contrats

- Writer séparé : `application/krea2_edit_assistance_v3.py`, opération `krea2.edit.conversation@3.0.0`.
- V2 reste dans `krea2_edit_assistance.py`, système, contexte et validation historiques préservés. V1 API reste inchangée ; une requête sans `assistance_version` garde le défaut V1.
- V3 conserve la réponse JSON `message` / `prompt`, six échanges récents, un appel LLM, les mêmes limites de sortie et les mêmes images jointes. Aucun filtrage de mots ou validateur spatial ajouté.
- Les instructions courtes V3 sont admises sans le minimum historique de 80 caractères anglais / 40 chinois. Réponse vide, objet invalide, Markdown ambigu et réponse tronquée restent refusés. Un échec conserve le prompt accepté et les révisions précédentes.
- Version persistée dans le champ existant des révisions ; schéma Edit 6 inchangé, lecture des anciens schémas conservée.
- Workflow Identity Edit `0.1.0`, checkpoints, LoRA, CFG, grounding, géométrie, MP, retouche et upscaling inchangés. Cache Edit JS **20260908.2**.

## Vérification à lancer par l'utilisateur

```powershell
python -m unittest tests.test_krea2_edit_assistance_v3 tests.test_krea2_edit_workshop tests.test_krea2_edit_web tests.test_krea2_edit_versions_browser
```

Tests avec faux gateway et stores temporaires : versions V1/V2/V3, anciens prompts figés, instructions courtes EN/ZH, contexte de source distinct de la cible, feedback exact, validation vers une nouvelle source, persistance, rejet sans perte et API. Scénario Chromium local : sélection, navigation, envoi de la version choisie et échec sans perte de brouillon ; aucun endpoint GPU.

L'agent a uniquement contrôlé la syntaxe Python et compilé le JavaScript/scénario navigateur sans les exécuter. La qualité visuelle de V3 reste à évaluer par l'utilisateur. Aucun test, appel LLM, rendu ou redémarrage de service pendant l'implémentation.
