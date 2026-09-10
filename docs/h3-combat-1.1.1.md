# Combat 1.1.1 — Identités et caméra

Le prompt du duel feu/glace avait remplacé les associations explicites aux photos par des descriptions physiques génériques. Le nom anglais « fire fighter » pouvait aussi induire une tenue de pompier, visible dans le résultat signalé. Un autre candidat avait été rejeté pour une phrase de mouvement caméra dans la description, favorisée par une consigne ambiguë. Ces observations motivent une correction ciblée ; elles ne prouvent pas que la longueur du prompt ou le LoRA sont responsables de toute la dérive des visages.

## Comportement

- Nouvelle version **Combat 1.1.1**, proposée à la sélection de Combat dans un nouvel atelier H3 ou REF2V. Les six parcours en un, deux et trois appels sont disponibles. **1.1.0 et 1.0.0 restent sélectionnables** ; les ateliers existants conservent leur version, y compris leurs révisions, réouvertures, conversions et continuations. Pour comparer, créer une nouvelle exploration avec la nouvelle version.
- Chaque combattant référencé est associé à son véritable `<Picture N>` et à son rôle lors de son introduction. Les noms restent cohérents dans les plans et les échanges suivants. Visage, cheveux et morphologie restent distincts des changements autorisés de costume, pouvoirs ou équipement. Les noms de rôle doivent éviter une interprétation indésirable, comme « fire fighter » pour un mage du feu.
- Le numéro suit la référence fournie, pas l'ordre des combattants. Une image peut contenir plusieurs personnages ; décor/style et First/Last Frames conservent leurs rôles. Aucun numéro Picture inventé en text-to-video.
- Le mouvement appartient uniquement à `camera_motion`. `opening_composition` décrit le cadrage initial et les positions ; `description` ou les échanges du plan décrivent les sujets et le décor sans reformuler un mouvement de caméra. Le schéma JSON porte ces précisions directement sur les champs. Le rédacteur du parcours planifié reçoit aussi cette règle sur chaque entrée de `shots`.
- Les mentions Picture dans la prose sont autorisées en **1.1.1 uniquement**, en vérifiant leurs numéros contre les références compilées. Les en-têtes, caméras et coupures restent protégés. Le contrôle strict des mouvements libres reste actif ; aucune suppression silencieuse et aucun appel supplémentaire de réparation.

Les révisions après rendu conservent leur contrat propre : tokens caméra et champ `camera_directives`, avec les mêmes associations d'identité. On ne leur demande pas un objet Sequence à la place de leur réponse conversationnelle.

## Isolation et contrats

Les nouveaux manifests adoptent explicitement la chorégraphie **1.1.0**, les contrats neutres existants et la politique vocale **1.0.0**, puis leurs nouveaux blocs d'identité et de rédaction. Aucun héritage de « latest », aucune modification des blocs Classique, Combat 1.0.0 ou 1.1.0. Le contrat Sequence et son stockage restent compatibles ; les descriptions du schéma et l'autorisation des mentions Picture sont conditionnées par la version exacte. L'énumération de révision accueille 1.1.1 sans migration des projets.

Quantité d'action, nombre de plans, liberté caméra et nombre d'appels restent indépendants. Seed, MP, modèles, LoRA, BUNNY et files de rendu ne sont pas modifiés. Aucun réglage de ressemblance supplémentaire dans l'interface. Caches des quatre scripts concernés : **20260910.4**.

## Vérification

Tests **préparés pour l'utilisateur, non exécutés pendant le patch** : mentions d'identité en mono/multiplan, refus des références inconnues et en-têtes répétés, caméra libre toujours refusée, règles locales du schéma, six parcours synchrones et streamés sans appel caché, révision directe et après rendu, First/Last/text-to-video, stockage, conversion, fork et continuation avec version exacte. Les fixtures d'empreintes couvrent les 561 fichiers de prompts/profils précédents.

Depuis le checkout actif, avec l'environnement Python habituel :

```powershell
python -m unittest tests.test_combat_identity tests.test_combat_sequence tests.test_combat_preparation tests.test_combat_controls_browser tests.test_h3_multishot_browser tests.test_recipe_picker_browser tests.test_run_lab_build
```

Vérifications effectuées à l'implémentation : analyses statiques Python/JavaScript, liens des manifests, empreintes des assets précédents et diff. Aucun test, appel LLM, génération ni redémarrage de service. Les tags de restauration existants sont conservés. La fidélité réelle des visages reste à comparer sur des rendus avec les mêmes références, seed et réglages.
