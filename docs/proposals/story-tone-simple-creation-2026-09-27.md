# Ton autonome et création compacte — implémentation du 27 septembre 2026

## Alignement retenu

L’utilisateur a autorisé le patch après une version préalable. Son dernier retour remplace la proposition initiale de micro-échanges : aucun exemple de scénario ou de réplique n’est préchargé dans le nouveau profil. Les références vidéo servent à comprendre un registre, pas à semer la même intrigue dans toutes les histoires.

Le moteur reçoit une idée courte, une ambiance, un univers, une durée et une langue. Il invente les motivations, les événements, les échanges et l’issue. Aucun sujet, schéma de vantardise/punition, gag sexuel ou type de chute n’est obligatoire.

## Version préalable

- Commit local : `18803a8e7dba9c1ef1aa2ae5031687db33d0ddc4`.
- Branche de sauvegarde : `snapshots/pre-story-tone-2026-09-27`.
- Tag annoté : `snapshot-pre-story-tone-2026-09-27`.
- 124 fichiers de code, tests, documentation et sources de prompts/manifests ; aucun média, runtime ou trace LLM brute.
- Snapshot réalisé avec un index temporaire. Branche active, HEAD et index utilisateur conservés. Aucun push GitHub.
- Manifeste : `D:/Code/panelforge/.agent/diagnostics/pre-story-tone-2026-09-27/checkpoint.json`.

## Comportement livré

### Ambiance et rôles

`writing_direction.tone_profile` peut valoir `none` ou `black_comedy_street_v1`. Le profil versionné est stocké dans le projet. Ses quatre fichiers de consignes sont chargés par le manifeste long, intégrés au snapshot éditorial de l’appel et à son empreinte ; le package passe à la révision 8. Les anciens packages sans ton restent lisibles pour les histoires sans profil.

Le choix explicite **Comédie noire · argot cru** règle une fois le style street, le vocabulaire 3/3, le débit rapide et la narration dialoguée. Il ne change pas l’univers, le type de construction ou la fin déjà choisis. Les ajustements ultérieurs restent prioritaires et l’interface affiche « Personnalisée ». Le choix Libre remet style naturel, registre 0, débit rapide et narration automatique ; les notes personnelles restent conservées.

- Conception : situation lisible, désirs, causalité, réactions ; ni lexique ni dialogues libres préécrits.
- Rédaction : voix distinctes, argot naturel dans la langue choisie, crudité inventée lorsqu’elle sert le personnage, sans quota ni tic systématique.
- Relecture : compréhension, causalité et continuité ; ne pas traiter le ton cru comme un défaut à assagir.

Le pipeline conserve conception → rédaction → relecture, soit trois appels pour une séquence sans blocage. Aucun nouveau rôle, appel de punchlines ou seconde rédaction n’est ajouté. La limite actuelle de correction ciblée reste inchangée.

### Lexique facultatif

`writing_direction.glossary` est un texte de 2 000 caractères maximum, vide par défaut. Il décrit des mots et leur sens. Seules les requêtes de rédaction/correction des scènes le reçoivent, sous `dialogue_lexicon`. Il n’est transmis ni à la conception ni à la relecture. Aucun mot n’est obligatoire et ce texte n’est pas ajouté aux répliques protégées.

La suite d’un projet conserve profil et lexique, comme les autres directions, mais abandonne les répliques exactes du précédent épisode. Les familles muettes désactivent le profil et le lexique côté interface ; la création API neutralise aussi ces deux champs.

### Limiter l’ancrage et les consignes concurrentes

Le nouveau profil ne reçoit plus les expressions françaises d’exemple historiquement ajoutées au registre 3. Le comportement historique de ce réglage est conservé hors du profil. L’exemple de facture du profil quotidien et celui du portefeuille dans la consigne d’objets ont été retirés au profit de règles générales. Les boutons d’exemples existants restent disponibles dans Personnaliser, uniquement sur clic explicite.

Les consignes de rédaction/relecture précisent aussi que `author_exact_lines` / `protected_lines` priment pour les mots exacts. Une citation déformée dans les preuves de l’arc ne crée pas une nouvelle obligation. Les validateurs et le mécanisme d’affectation des répliques aux unités ne sont pas remaniés : cette clarification n’est pas une réparation automatique de l’ancien run.

### Interface

La création affiche idée, ambiance, univers/rendu, durée et langue. Un seul panneau **Personnaliser**, fermé par défaut, regroupe parcours, narration, nuances, lexique, paroles exactes, découpage, contexte antérieur, exemples et modèles.

Les contrôles existants sont conservés et déplacés, sans dupliquer les valeurs. Les modèles retournent dans la barre d’écriture à l’ouverture d’une histoire existante. En fabrication, le cadre de modèles d’écriture et le texte introductif redondant sont masqués. Les outils Références, Scènes et Multilangue gardent leur fonctionnement.

Nouvelle histoire : parcours suivi automatique, durée cible 80 s, plafond 8 clips de 10 s, ambiance libre. Le scénario court reste accessible dans Personnaliser. Le résumé au-dessus du bouton rappelle les choix effectifs ; les réglages d’une ancienne création ne se reportent plus accidentellement dans le nouveau formulaire. Les modèles choisis explicitement restent mémorisés.

### Compatibilité

Aucun projet existant ni média n’est modifié. L’accès aux directions sauvegardées omet les nouveaux champs lorsqu’ils n’existaient pas : les empreintes de dépendance et de relecture des anciennes histoires qualité v1 restent identiques. Le profil ne s’applique pas rétroactivement. Les requêtes déjà capturées conservent leur snapshot éditorial.

## Vérification

Contrôles statiques : syntaxe Python par AST, compilation JavaScript sans exécution, manifeste JSON et fichiers référencés, IDs Histoire uniques, imbrication du formulaire, revue du diff.

Tests préparés, **non exécutés** conformément aux instructions : profil et routage du lexique, trois appels, réglages explicites, anciennes empreintes, héritage de suite, familles muettes, validation API, empreinte/sources éditoriales et création navigateur. Aucun LLM, rendu, service ou redémarrage lancé.

Commande ciblée pour l’utilisateur, depuis le checkout actif :

```powershell
D:\Code\panelforge\.venv\Scripts\python.exe -m unittest tests.test_story_tone tests.test_story_quality_policy tests.test_story_quality_browser tests.test_stories_browser
```

## Premier essai

Après chargement du backend mis à jour et rechargement de la page, créer une nouvelle histoire. Choisir Comédie noire · argot cru, garder les modèles Qwen proposés, préciser l’univers visuel, puis une intention de quelques lignes. Laisser lexique et répliques exactes vides pour observer l’invention spontanée.

Comparer ensuite une autre idée, sans changer le ton, pour évaluer la diversité des motivations, des voix et des chutes. Le patch ne garantit ni la qualité comique ni une réduction du temps de raisonnement sans ces essais réels.
