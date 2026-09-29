# Histoires : états visuels réutilisables et consignes par rôle

Implémenté le 27 septembre 2026 dans D:/Code/panelforge-krea2-flux. Non déployé/redémarré par l'agent. Aucune génération ni exécution de tests fonctionnels.

## Comportement

Les nouvelles histoires longues portent visual_state_policy=2 et utilisent le contrat LLM 2.4.0. Les anciens projets gardent leur politique, leurs contrats et leurs références. Aucun nettoyage ou rejeu automatique du test Fraisette déjà lancé.

Pour Fraisette fine à la scène 1, enceinte aux scènes 2 et 3, avec Pomito inchangé et un décor : deux images d'identité, un décor, une variante enceinte réutilisée deux fois. Les douze ancres redondantes du cas observé sont couvertes par une régression dédiée ; cette attente n'a pas été vérifiée par exécution dans cette intervention.

- Une image correspond à une apparence résolue d'un personnage/objet, pas à un début ou une fin de scène. La chronologie d'auteur est conservée ; sa projection en tâches est parcimonieuse.
- Égalité prudente : même identité, corps et tenue identiques après normalisation de la casse, des espaces et Unicode. Pas de fusion sémantique de paraphrases, pas de fusion entre personnages ou objets différents.
- Le détenteur d'un objet reste suivi mais ne provoque pas une nouvelle image de l'objet.
- L'état de première apparition est fourni au prompt d'identité avec priorité sur une évolution future de la biographie. Une variante ne recopie plus toute cette biographie ; Qwen reçoit seulement l'apparence demandée et les consignes de conservation.
- Les états persistent. Une apparence déjà rencontrée réutilise sa référence ; un retour à l'apparence initiale utilise la base. Les ID de références dépendent de l'apparence, pas du nom d'un jalon.
- Un état final sans utilisation à l'ouverture d'une scène reste dans la mémoire pour la suite sans image demandée immédiatement. Le routage des transformations pendant un clip conserve le comportement existant ; aucun ajout de deux images avant/après au moteur vidéo dans ce patch.
- Les images et choix historiques sont conservés. Une référence devenue inutile est archivée, pas supprimée. Une modification initiale invalide la base ; les variantes attendent sa revalidation et ne partent pas depuis une base obsolète.
- L'héritage des nouveaux projets compare les apparences des images validées, y compris une ancienne variante. Il ne reprend pas une ancienne silhouette sur le seul nom. En l'absence de correspondance explicite, l'image reste à préparer.

## Ellipse et transformation

Dans le contrat 2.4, un visual_transition non null comporte timing : within_scene ou between_scenes.

- within_scene : avant, déclencheur, changement et après sont effectivement montrés dans ce clip.
- between_scenes : le changement a eu lieu avant l'ouverture ; le prompt demande l'état déjà acquis et interdit de rejouer sa transformation.
- Pas de changement utile : visual_transition=null.

Le relecteur voit désormais ce champ, les états résolus start/end et les états couverts par les identités. Il ne voit toujours pas la bible secrète, les descriptions privilégiées ni les conclusions narratives du scénariste. Un visuel de continuité n'est pas une preuve narrative.

## Consignes

Sources lean-common/compose/edit/write/review/discuss.txt dans prompt_sources/story.long/2.0.0, snapshot éditorial révision 6. Les recettes anciennes restent disponibles pour les anciens contrats.

Les nouveaux appels reçoivent les consignes de leur rôle, les règles conditionnelles pertinentes et un schéma JSON faisant autorité. Les gros exemples de réponse ont été retirés des appels structurés ; le parcours idées historique conserve son contrat lorsqu'il n'a pas de schéma. Le nommage fruité et sa vérification à l'édition restent actifs. Les règles de questions sans réécriture, de correction des seuls blocages et de suivi des relectures restent en place.

Prompt de base de la relecture : 3 019 caractères sans contexte conditionnel, contre 12 620 dans le run audité. Mesure statique des textes, pas mesure de vitesse du modèle. Aucun gain de temps ou de thinking n'est encore mesuré. Quatre étapes, modèles choisis, températures et budget de 80 000 conservés. Aucun appel supplémentaire, détecteur de répétition ou arrêt automatique ajouté.

## Vérification et essai utilisateur

Contrôles effectués : syntaxe Python par AST sans importer les services, manifeste JSON et présence des nouvelles sources, git diff --check ciblé, relecture du diff par rapport à l'instantané avant intervention. Les modifications préexistantes du checkout ont été préservées.

JavaScript : changements limités à la reconnaissance de la politique 2, au texte d'aide et aux versions de cache. Node absent de l'environnement ; pas de contrôle syntaxique automatisé JS ni test navigateur effectué.

Tests écrits/mis à jour, non exécutés conformément à AGENTS.md :

```powershell
python -m unittest tests.test_story_sparse_states tests.test_required_visual_states tests.test_required_state_images tests.test_long_stories tests.test_story_workflow
```

Les nouvelles régressions couvrent la duplication 12→1, le routage de deux scènes vers une image, le retour à la base, les changements textuels mineurs, la conservation des médias après édition, les objets transmis, les scènes non visibles, les états finaux inutilisés, l'héritage, une seule mise en file Qwen, la revalidation de la source, la confidentialité de la projection lecteur et le contrat des ellipses. Le faux LLM du workflow crée ses réponses localement au lieu de recopier un exemple retiré des prompts.

Après le redémarrage habituel du Lab et rechargement de l'interface, créer une NOUVELLE histoire avec l'intention Fraisette précédente et les mêmes modèles/réglages. Vérifier les quatre références, accepter les bases puis l'unique variante, contrôler la même référence enceinte aux scènes 2/3. Comparer ensuite la durée et le volume de raisonnement de la relecture aux traces de l'audit. Ne pas présenter le résultat attendu comme un test déjà passé.

Diagnostic initial : D:/Code/panelforge/.agent/diagnostics/story-visual-variants-2026-09-27.md.
Contrôles statiques : D:/Code/panelforge/.agent/diagnostics/story-revamp-checks-2026-09-27.json.
