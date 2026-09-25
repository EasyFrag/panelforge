# Bibliothèque des histoires

Implémentation dans `D:\Code\panelforge-krea2-flux`, à la suite de la refonte des trois étapes d’écriture. Les modifications précédentes sont conservées. La génération de miniatures de vidéos reste reportée ; les blocs de bibliothèque affichent désormais les aperçus des personnages déjà disponibles.

## Utilisation

Le sélecteur ouvre une bibliothèque avec recherche insensible aux accents et filtres Toutes / Favoris / En cours / Terminées / Corbeille.

- Les suites sont regroupées par leurs liens explicites. Le titre commun se renomme depuis le groupe ; les titres d’épisode et le scénario sont préservés.
- Une étoile marque la série comme favorite. Le menu de chaque entrée permet de la rattacher à une autre série et de définir un numéro. Les suites déjà existantes conservent leur rangement quand leur parent est déplacé.
- Les numéros ne dépendent pas de la position dans la liste et ne changent pas après mise à la corbeille. Deux suites du même épisode conservent le même numéro avec l’indication Variante. Une histoire continue avec plusieurs séquences reste un épisode ; un ancien projet sériel contenant plusieurs épisodes est présenté comme une plage (Épisodes 1–4).
- La croix met le projet à la corbeille ; Annuler et Restaurer sont disponibles. Aucun fichier de scénario ou média n’est supprimé. Les ancêtres retirés restent disponibles aux suites. La corbeille ne libère pas d’espace disque.
- Les tâches d’écriture, préparation de suite, images, variantes Qwen, vidéos et DLSS connues empêchent le retrait pendant leur activité. Les anciens rendus absents sont signalés et n’empêchent pas de ranger le projet ; une activité impossible à déterminer suspend le retrait.

Depuis le complément du 24 septembre, le sélecteur **Trier par** propose Plus récentes (par défaut), Plus anciennes, Titre A–Z et Favoris d’abord. Le choix est mémorisé dans le navigateur. Les tris par date utilisent la dernière modification enregistrée du récit ou de ses fabrications ; mettre en favori ou renommer le groupe ne change pas cette date. Le tri porte sur les groupes visibles après recherche/filtre ; les épisodes restent dans leur ordre. Favoris d’abord départage les favoris par activité récente.

Même replié, un groupe affiche le nombre d’entrées visibles, les vidéos prêtes/attendues dans les langues affichées, la dernière activité et un éventuel traitement actif. Jusqu’à trois portraits nommés proviennent des références personnages sélectionnées des fabrications suivies, en commençant par les épisodes récemment utilisés. Les décors, objets et références archivées sont exclus ; les différents états d’un personnage ne créent pas plusieurs portraits. Les images sont chargées à la demande via la route média existante et son cache. Aucun fichier miniature ni appel de génération supplémentaire. Si une image manque sur disque, son nom reste accompagné d’un aperçu de remplacement.

Chaque entrée affiche Intention / Histoire / Scénario / Références / Vidéos. Les validations manuelles restent distinctes des résultats écrits ; une tâche planifiée n’est pas affichée comme un calcul en cours.

Les compteurs concernent une fabrication par unité et par langue : priorité à une fabrication correspondant au scénario courant, puis à la plus récemment créée. Les anciens essais ne s’additionnent pas. La dernière tentative vidéo hors DLSS est suivie, et seuls les résultats DLSS rattachés à cette vidéo comptent. Une nouvelle tentative en attente est indiquée planifiée. Les empreintes de scénario/références et les principaux réglages vidéo évitent de compter les rendus devenus obsolètes.

Les langues restent rattachées au même épisode et ont des compteurs distincts. Le sélecteur de langue pilote l’avancement affiché et la fabrication ouverte. Pour un projet contenant plusieurs séquences, l’accès ouvre la première fabrication de cette langue ; le sélecteur de fabrication existant permet de passer aux suivantes.

## Architecture et données

- `domain/story_library.py` : regroupement, numérotation et validation des actions de rangement.
- `application/story_library.py` : synthèse des cinq jalons, lectures des dépôts et protection de la corbeille.
- `stories/library.json` : métadonnées versionnées séparées des projets, créées lors d’une action de rangement. Écriture atomique et révision attendue pour éviter l’écrasement entre onglets.
- `GET /api/stories/library`, `PATCH /groups/{id}` et `PATCH /projects/{id}` sous le même préfixe.
- Lecture de la bibliothèque sans appel aux services qui réveillent les traitements ; aucune génération ou réconciliation déclenchée. Actualisation périodique uniquement pendant l’ouverture de la bibliothèque lorsqu’un travail actif est connu.
- La liste historique reste disponible en secours si le frontend a été chargé avant le nouveau backend. Les fichiers illisibles sont comptabilisés dans un message visible.

Les écrans Références / Scènes / Multilangue et leurs traitements sont conservés. `episodes.js` reçoit seulement un accès de navigation utilisant les sauvegardes existantes avant de changer de projet et le lecteur de fabrication existant.

## Validation et activation

Contrôles exécutés : analyse syntaxique de huit Python et compilation seule de cinq sources JavaScript, dont les deux scripts de fixture navigateur ; IDs HTML uniques et contrôles de la bibliothèque présents ; balisage de fabrication et de préparation de suite inchangé ; logique existante de `episodes.js` identique après retrait du seul accès de navigation ajouté ; `git diff --check`.

**Tests fonctionnels préparés, non exécutés**, selon AGENTS.md et la préférence utilisateur. Aucun LLM, rendu, écriture dans le runtime ou redémarrage effectué. La présentation dans le navigateur réel et les compteurs sur les données courantes restent à vérifier par l’utilisateur.

À la fin des traitements en cours, redémarrer le Lab pour charger les routes backend, puis actualiser la page. Commandes ciblées dans le worktree actif :

```powershell
D:\Code\panelforge\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_story_library.py"
D:\Code\panelforge\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_story_library_browser.py"
```

Les fixtures couvrent liens explicites/variantes, stabilité des numéros, rangement sans réécriture, favoris, corbeille/restauration, conflits de révision, contrat HTTP, avancement multilangue, rendus obsolètes/planifiés, filiation DLSS, activité des anciennes fabrications et absence d’appels aux services de génération.

Complément tris/portraits : syntaxe Python et JavaScript vérifiée sans exécution applicative ; identifiants HTML et raccordements contrôlés, balisage des suites/fabrication préservé, diff-check. Aucun test fonctionnel lancé ni ajouté pour ce complément UX ; essais des tris et portraits à la main de l’utilisateur après rechargement du backend et de la page.
