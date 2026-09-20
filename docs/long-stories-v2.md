# Histoires longues V2

Implémentation du 20 septembre 2026, à la suite de l’[audit](diagnostics/audit-histoires-longues-2026-09-20.md). La V2 remplace le parcours des **nouvelles histoires longues créées dans le Lab**. Les projets enregistrés avec le moteur historique gardent leur parcours, leurs versions et leurs fabrications.

## Utilisation

Après redémarrage du serveur par l’utilisateur lorsque ses traitements sont terminés, puis `Ctrl+F5`, ouvrir **Histoires → Nouvelle histoire → Histoire suivie**. Cette appellation désigne le moteur long V2, utilisable aussi pour une seule minute. Le scénario court garde son parcours historique.

1. Écrire une idée, choisir l’univers, une vidéo continue ou une série, puis la durée souhaitée pour **l’ensemble**. Les préréglages **L’addition qui dérape**, **Les gouttes d’eau** et **Le temps de vie** remplissent ces choix avec un brief modifiable.
2. Choisir **Manuel guidé** pour discuter de la direction puis de chaque séquence, ou **Automatique** pour enchaîner jusqu’au scénario prêt. Les mêmes contrôles s’appliquent ; une difficulté persistante arrête l’automatisation.
3. Laisser les orientations narratives en **Automatique**, ou ouvrir **Orienter l’histoire**. Cinq profils sont disponibles : conflit du quotidien/joute verbale, mélodrame, transformation, suspense et fantastique. Chaque bouton `ⓘ` explique l’effet du réglage avec des exemples. Le choix **Développer mon récit fourni** préserve les moments et la fin imposés, sans promettre une transcription mot pour mot.
4. La durée propose le découpage. **Production avancée** permet d’ajuster 1 à 12 unités, 1 à 12 clips maximum par unité et 5 à 15 secondes par clip. Le budget arrondi est affiché et reste fixe après création ; le scénario peut utiliser moins de clips. Les modèles sont dans un panneau replié.
5. Lancer l’histoire. Une seule proposition, directement accompagnée de son architecture, est créée puis vérifiée. En manuel, **Développer le scénario** valide la direction ; **Valider et continuer** valide chaque séquence relue. Ces clics de validation seuls ne consomment pas d’appel.
6. Écrire dans **Ton retour**, avec une cible explicite : histoire complète, séquence ou scène. **Commenter cette scène** sélectionne la cible. **Appliquer mon retour** révise le texte et relance les contrôles utiles ; **Poser une question** répond sans modifier le document. Les échanges et versions permettent de suivre les changements. Un retour local qui exigerait de modifier l’architecture doit ouvrir une discussion.
7. Pendant l’automatique, **Reprendre la main** laisse finir l’appel actif puis suspend l’enchaînement. Le texte saisi reste en brouillon. Le mode manuel permet alors de modifier ou de poursuivre.
8. **Valider et préparer la fabrication** réutilise la chaîne existante. Aucun de ces modes ne lance automatiquement les images, vidéos ou DLSS.

Si ce bouton est désactivé, le panneau **Avant la fabrication** explique l’étape manquante et propose l’action à cet endroit : poursuivre les vérifications, traiter une erreur ou préciser un retour. Un scénario déjà écrit mais jamais relu reste verrouillé. Si le mode manuel attend encore l’accord sur sa direction, **Valider l’histoire et relire le scénario** reprend le parcours en conservant les scènes à jour. L’avertissement orange sur une durée estimée ne bloque pas à lui seul la fabrication ; c’est la relecture et son éventuel problème bloquant qui comptent.

Le nouveau parcours regroupe proposition et arc dans `compose`. Un second appel distinct, `edit_outline`, contrôle l’arc et applique les petites corrections en une passe. Chaque unité est rédigée séparément ; en automatique continu, les unités sont relues deux par deux. Le canon provisoire de la première permet la rédaction de la seconde, mais ne débloque pas leur fabrication avant relecture. En manuel et en feuilleton, la relecture reste unitaire.

Hors corrections, le parcours automatique continu compte **2 + N + ceil(N/2) appels**, soit **4 pour une unité, 5 pour deux**, contre 7 pour deux unités avec l’ancienne proposition séparée. Manuel/feuilleton : **2 + 2N**. Une unité bloquée reçoit au maximum une correction automatique avant une nouvelle relecture ; un blocage persistant est présenté à l’auteur. Le compteur de corrections ne se réarme pas par un simple clic Continuer. Chaque reprise a aussi un plafond global de `4N + 8` appels. Un retour explicite de l’auteur ouvre une nouvelle tentative sur sa cible. Le nombre d’appels réduit n’est pas une mesure du gain de temps ni une preuve de meilleure qualité.

L’Architecte conçoit et relit ; le Rédacteur développe et corrige les scènes. Ils peuvent utiliser le même modèle avec des contextes distincts. Les projets V2 existants peuvent activer ce parcours avec **Continuer le parcours** ; aucune génération ne démarre à leur seule ouverture.

## Exemple : la dispute au restaurant

L’[analyse de Download(29).mp4](diagnostics/reference-addition-et-parcours-guide-2026-09-20.md) décrit une joute verbale de 76,67 secondes : condition imposée, refus, tentatives de report de la note, intervention de la serveuse, retournement final.

Cliquer **L’addition qui dérape** configure une vidéo continue de **80 secondes maximum**, une séquence de huit clips de dix secondes, univers fruits, profil quotidien, dialogues, fin avec retournement, vocabulaire 1. Garder les modèles habituels et choisir Manuel guidé pour le premier essai. Le brief est original et modifiable. Pour mesurer l’autonomie ensuite, le réduire à « Un premier rendez-vous dérape à l’arrivée de l’addition » et passer les orientations en Automatique. Une question finale au public se demande dans le brief ; aucun sélecteur supplémentaire n’est nécessaire.

## Reprendre une erreur existante

- Pour l’erreur `world_rules doit contenir exactement : id rule limits`, les règles reçues en phrases sont maintenant conservées et structurées sans inventer leurs limites. Les futurs appels reçoivent le format détaillé des règles et secrets facultatifs. Après redémarrage, **Revalider la réponse reçue** récupère le brouillon existant sans relancer la conception, puis **Continuer le parcours** reprend les contrôles narratifs. [Diagnostic des deux runs concernées](diagnostics/erreur-world-rules-2026-09-20.md).
- `projectCount` a été retiré du message affiché entre sauvegarde et premier appel : un projet créé sans job peut maintenant s’ouvrir et démarrer.
- Les relectures acceptent les IDs réels des règles, secrets, personnages, unités et événements ; un ID inconnu reste rejeté. Le budget distingue explicitement plafond par unité et durée totale.
- Si le modèle a placé `episode_state` dans `scenario`, le moteur replace cette mémoire existante à la racine puis effectue toute la validation. Il conserve la réponse brute, n’invente aucun état manquant et rejette deux mémoires contradictoires. Sur l’ancien brouillon en échec, utiliser **Revalider la réponse reçue**, puis Continuer. Ce bouton ne rappelle pas le LLM ; d’autres erreurs de contenu peuvent encore être signalées.
- **Relancer le LLM** conserve l’opération, le retour, sa cible et les unités d’une relecture groupée. Une reprise est refusée si le document a changé : il faut adresser un nouveau retour à la version actuelle. Un redémarrage de service ne reprend pas silencieusement les appels.

## Ce qui change dans le moteur

Le contrat narratif contient `promise`, `protagonist_goal`, `stakes`, `must_keep` et `freedoms`. Les contraintes à préserver viennent du brief ; les inventions du modèle ne doivent pas toutes devenir intouchables. Chaque événement possède un ID, une cause ou un objectif, un changement, une information à montrer/faire entendre et des dépendances antérieures. Les règles et secrets sont facultatifs ; lorsqu’ils existent, leurs IDs distinguent révélation au public et connaissance des personnages. Une dispute ordinaire n’a pas besoin de mythologie.

Le rédacteur reçoit l’unité sélectionnée, la bible, le canon des unités précédentes et les événements réservés au futur. Sa réponse associe chaque clip aux événements servis et fournit faits établis, changements de connaissances et fils ouverts/résolus. Le backend vérifie les IDs, l’ordre des dépendances, la couverture des événements, les révélations déclarées, le casting et le plafond de clips.

La critique narrative utilise un appel séparé et cite des problèmes localisés. Elle juge ce que les actions montrent, pas seulement ce que les états finaux déclarent. Une empreinte lie son résultat au document effectivement relu. La détection sémantique des contradictions, de la fidélité au brief et des révélations non déclarées reste une tâche du modèle et du lecteur humain, pas une garantie du validateur JSON.

Modifier une scène invalide sa relecture. Modifier l’arc ou un épisode précédent rend les unités dépendantes **à réécrire**, sans supprimer leur texte. Le backend bloque leur fabrication jusqu’à la validation du passé ; seule la rédaction provisoire dans un bloc automatique est permise avant relecture. Une restauration récupère un instantané cohérent, y compris les choix narratifs résolus ; un ancien brouillon LLM ne peut pas être réappliqué à un document qui a changé depuis son appel.

L’adaptateur Fabrication produit toujours `characters / locations / scenes`. Il ajoute l’information indispensable de chaque clip à son intention, afin qu’elle atteigne effectivement les prompts. Le calcul d’identité d’une fabrication utilise cette même sortie. Génération des fiches, héritage des images, prompts H3/REF2V, files, vidéos et DLSS continuent sur leurs contrats existants. Les fabrications déjà créées restent des instantanés autonomes.

## Contrats et compatibilité

- Recette éditoriale : `prompt_sources/story.long/2.0.0/manifest.json`, prompts séparés pour propositions, arc, rédaction et critique. Chaque job conserve la version et l’empreinte du contenu éditorial utilisé.
- Ces prompts V2 sont versionnés dans le dépôt ; le bouton historique **Consignes LLM**, qui édite les recettes courtes, est masqué dans ce parcours. Les corrections d’auteur passent par le brief et la conversation.
- Domaine : `domain/long_stories.py`. Projection des contextes : `application/long_stories.py`. Chargement des recettes : `infrastructure/long_story_recipes.py`.
- Stockage V2 : `schema_version: 2`, `narrative_engine: {"id":"story.long","version":"2.0.0"}`. L’état calculé `long_status` n’est pas une approbation enregistrée et n’est pas persisté.
- Activation API : `POST /api/stories/projects` avec `narrative_format: "long"` et `long_options`. Sans `long_options`, les clients historiques conservent le schéma 1. Les histoires courtes restent au schéma 1.
- Parcours guidé : `workflow_mode: "manual" | "automatic"`, `visual_universe` et `target_seconds` à la création. Les options `profile`, `narration` et `ending_type` acceptent `auto` dans ce parcours ; `compose` les résout sans changer une préférence explicite. Orchestration : `application/story_workflow.py` et routes `/advance`, `/pause`, `/feedback`, `/retry`. Les paramètres internes d’enchaînement ne sont pas exposés par `/write`.
- Opérations ajoutées à `/write` : `review_outline`, `repair_outline`, `revise_outline`, `review_episode`, `repair_episode`. `develop` permet également de réécrire une unité périmée. Les refus sont vérifiés côté serveur, indépendamment des boutons.
- Le paramètre de création `proposal_count` est supprimé. Chaque nouvelle demande produit une proposition ; plusieurs propositions sont refusées. Les anciennes cartes enregistrées restent consultables.

Exemple d’options :

```json
{
  "profile": "suspense",
  "delivery": "serial",
  "narration": "visual",
  "unit_count": 4,
  "ending_type": "open"
}
```

Les durées restent uniformes et le budget identique pour toutes les unités. Le récit continu utilise des séquences internes fabriquées séparément ; aucun nouveau montage final automatique n’est ajouté. La narration audio utilise les modes de paroles déjà disponibles, portés par des personnages identifiés. Les inscriptions exactes et compteurs ne constituent pas un canal fiable de narration. Le temps parole/actions est une estimation de relecture, pas une mesure de rendu.

## Vérification et qualification

Les vérifications statiques portent sur la syntaxe Python/JavaScript, les manifests et les diffs. **Les tests et les essais avec modèles réels n’ont pas été exécutés pendant l’implémentation**, conformément au `AGENTS.md` du worktree actif. Les régressions ajoutées utilisent un faux LLM et des fichiers temporaires ; le test navigateur utilise une API factice.

Depuis `D:\Code\panelforge-krea2-flux`, commandes à lancer par l’utilisateur :

```powershell
& D:\Code\panelforge\.venv\Scripts\python.exe -m unittest tests.test_long_story_response_contracts tests.test_long_stories tests.test_story_workflow tests.test_long_stories_browser tests.test_stories tests.test_stories_browser tests.test_episodes tests.test_episodes_web tests.test_episodes_browser
& D:\Code\panelforge\.venv\Scripts\python.exe -m unittest discover -s tests
```

Le navigateur de régression est ignoré si Chromium local n’est pas installé. La continuité du dépôt documente des échecs historiques de la suite générale ; aucune réussite globale n’est revendiquée ici.

Le [jeu de dix briefs](../evals/story-long-v2/briefs.json) fournit deux cas par profil, répartis en développement et réserve. Il inclut récit fourni, muet, fin ouverte, conclusion, secret, règle fantastique et budget volontairement tendu, ainsi que deux intentions minimales de conflit quotidien. Il n’a encore produit aucun résultat : l’architecture est implémentée, **le gain de qualité reste à mesurer**.

Le [retour sur Pomitto et les réglages](diagnostics/retour-pomitto-et-reglages-2026-09-20.md) complète l’audit : une intention concrète donne déjà un résultat exploitable avec le moteur court. La V2 doit préserver ce comportement, particulièrement la progression et le point d’arrêt de l’auteur. Ce document détaille tous les réglages et un premier essai comparable.

Comparer avec le même modèle, la même famille et un budget total comparable ; masquer la version aux lecteurs. Pour chaque histoire complète, noter de 0 à 2 : objectif compris, causes comprises, promesse préservée, révélations bien placées, conséquence visible, absence de répétition, faisabilité et envie de poursuivre. Localiser chaque échec dans le texte, consigner appels/corrections/clips et conserver aussi les réponses refusées. Le corpus de réserve ne sert pas à retoucher les prompts pendant la première comparaison. Modifier ensuite un événement amont sur un cas et vérifier toute la suite. Les vidéos viennent après cette évaluation textuelle, avec des références et réglages comparables.
