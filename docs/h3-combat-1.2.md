# Combat 1.2 — Orientations et parcours visibles

## Correction des parcours

Combat 1.1.1 disposait des recettes en un, deux et trois appels. Le filtre `recipeTier` reconnaissait uniquement les versions se terminant par `.0` de Combat 1.0/1.1 et classait 1.1.1 dans les recettes historiques. La règle conservant toujours visible le choix actif ne laissait apparaître que le parcours sélectionné, généralement « Exploration guidée · 3 étapes ».

La classification reconnaît maintenant les recettes Combat installées indépendamment de leur numéro de version. Le sélecteur Version Combat continue de filtrer la version exacte. Les trois parcours sont visibles en **H3 et REF2V, notamment en 1.1.1 et 1.2.0**, sans cocher les archives. Les filtres des recettes Classique restent inchangés.

## Orientation choisie au départ

Combat **1.2.0** est proposé lors du choix Combat pour une nouvelle exploration. Trois orientations :

- **Libre / mixte**, défaut : styles et pouvoirs demandés, mouvements et réactions liés, effets rattachés aux attaques.
- **Corps à corps** : appuis, distances, contacts, contrôles et déséquilibres ; aucune tenue ni paire de gants imposée.
- **Armes** : portée, prise, trajectoire héritée, récupération, techniques et cadrages adaptés aux armes effectivement demandées.

Une consigne conditionnelle commune traite **un contre plusieurs** lorsque l'intention le demande : trajet du protagoniste, pression relayée, accès limités par le décor, réactions et reprises persistantes. Aucun sélecteur supplémentaire, plafond rigide d'assaillants ou classificateur LLM. Les genres fantastiques peuvent garder leurs effets de zone explicites.

L'intention reste prioritaire. Quantité d'action, nombre de plans, caméra et un/deux/trois appels sont indépendants de cette orientation. Le choix est conservé pendant les échanges, révisions après rendu, forks, conversions, réouvertures et continuations. Comme les autres réglages de préparation, il est verrouillé dans l'atelier créé ; une nouvelle exploration permet un nouveau choix. Le rédacteur préserve les mécanismes décidés dans le plan.

Un conseil de LoRA apparaît sous l'orientation : Weapon Combat pour Armes, Combat V2 pour les autres. **Conseil uniquement** : aucun changement de LoRA, forces, seed, MP, BUNNY ou workflow. L'orientation est aussi rappelée dans l'atelier de rendu.

## Contrats et compatibilité

Six nouvelles recettes et deux profils 1.2.0 adoptent les blocs de chorégraphie 1.1.0, d'identité/rédaction 1.1.1 et les contrats neutres à versions exactes. Les blocs compacts d'orientation sont dans `application/combat_orientation.py`, explicitement propres à 1.2.0. Ils sont injectés dans les appels existants via les réglages enregistrés ; les trois manuels complets ne sont pas transmis.

`CombatSettings.orientation` vaut `mixed`, `hand_to_hand` ou `weapons` en 1.2.0. Le champ reste absent des anciennes versions et n'est pas accepté dans leurs réglages. Les sessions passent au schéma **12**, lisible depuis 1–11 ; les projets H3/REF2V au schéma **9**, lisible depuis 1–8. Aucune migration automatique du workspace. Les anciens ateliers et leurs versions 1.0.0, 1.1.0 et 1.1.1 restent utilisables.

Les protections d'identité et de caméra de 1.1.1 restent actives dans 1.2.0, ainsi que son contrat de révision après rendu. Aucun format à six sections, quota de coups ou découpage temporel des documents externes n'est imposé. Caches des cinq JS modifiés : **20260910.5**.

## Vérification et utilisation

Tests **préparés, non exécutés par l'agent** : visibilité des trois parcours H3/REF2V par version sans option historique, choix/affichage/payload et restauration de l'orientation, six parcours × trois orientations en synchrone et streaming avec nombre d'appels inchangé, révisions, stockage et anciens schémas, fork, conversion et continuation, isolement des anciennes versions. Fixtures d'empreintes couvrant les **574 fichiers de prompts/profils antérieurs**.

```powershell
python -m unittest tests.test_combat_orientation tests.test_combat_identity tests.test_combat_sequence tests.test_combat_preparation tests.test_combat_controls_browser tests.test_recipe_picker_browser tests.test_h3_multishot_browser tests.test_run_lab_build tests.test_prompt_lab
```

Vérifications statiques du patch : AST Python, syntaxe JavaScript sans invocation, liens des manifests, empreintes des anciens prompts/profils et diff. Aucun test, appel LLM, génération ni redémarrage de service effectué. Tags de restauration conservés.

Après les traitements en cours, charger le patch en redémarrant le Lab et recharger la page. Choisir Combat 1.2, l'orientation puis l'un des trois parcours. Combat 1.1.1 reste disponible pour comparer avec la même intention, les mêmes références et les mêmes réglages de rendu.
