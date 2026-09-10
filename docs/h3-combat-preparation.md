# Préparation Combat 1.0.0 — 10 septembre 2026

Dans H3 Base ou REF2V Direct, choisir **Préparation → Combat**, puis le parcours. Classique reste le choix initial. Le changement de famille conserve le nombre d'étapes choisi ; dans H3, il conserve aussi mono/multi-plan. La famille est verrouillée dès la création de l'atelier. **Repartir de ce run** prépare une nouvelle exploration, où l'on peut choisir une autre famille sans reprendre la conversation précédente.

| Entrée | Parcours Combat | Références |
| --- | --- | --- |
| H3 mono-plan | 3, 2 ou 1 étape | Texte seul, first, last ou first + last |
| H3 multi-plan | 3, 2 ou 1 étape | Mêmes entrées, 2 à 4 plans |
| REF2V mono-plan | 3, 2 ou 1 étape | Rôles habituels des images |

Les anciens REF2V multi-plan restent dans Classique. Une préparation H3 Combat multi-plan peut être adaptée en REF2V avec l'adaptation existante, qui conserve les plans et la famille.

## Répartition des décisions

- **3 étapes** : le Brief choisit une chorégraphie cohérente avec l'intention ; le Plan fixe mécanique, espace et timing ; le Writer rédige la chorégraphie approuvée.
- **2 étapes** : le Plan interprète directement l'intention et les images, puis le Writer rédige. Aucun Brief caché.
- **1 étape** : interprétation et rédaction dans un seul appel, avec le contrat compact existant. Aucun Plan caché. La route mono garde un seul mouvement caméra principal ; la route multi permet un mouvement par plan.

Les consignes relient attaque, défense/contact, réaction, dégagement et reprise d'initiative. Elles préservent identités, armes, trajectoires et positions. La densité dépend du temps disponible ; il n'y a pas de quota rigide de coups. Les gestes nécessaires à un duel ne sont pas interdits par « Mouvements additionnels = 0 ». L'audace permet une variation tactique ou un renversement cohérent, sans exiger flash, glow, gore, ralenti ou changement de caméra. Les permissions caméra et dialogue restent distinctes.

Le mode prépare le texte. Il ne sélectionne aucun LoRA, n'ajoute aucun déclencheur comme `BUNNY`, et ne change pas la recette de rendu, les MP, le seed ou le Turbo. Les réglages enregistrés continuent à s'appliquer. La qualité visuelle et la réussite d'une chorégraphie restent à expérimenter ; aucun rendu d'évaluation n'a été lancé pour ce patch.

## Isolation et versions

### Direction suivante discutée : action et découpage indépendants

Clarification utilisateur du 10 septembre 2026, **pas encore implémentée** : deux contrôles distincts, **Quantité d'action** et **Nombre de plans**. Le second détermine mono-plan ou coupures ; il ne remplace jamais le premier. L'ancienne suggestion de remplacement concernait le contrôle « Mouvements additionnels », pas le découpage, et ne vaut pas autorisation générale de supprimer un contrôle. Audace, liberté de mouvement caméra et 1/2/3 appels de préparation restent des notions différentes.

Les exemples de référence ont été relus dans les pièces jointes originales :

- Duels épée/bouclier contre épée longue et hache contre épée : trois plans sur dix secondes. Chaque plan développe une combinaison de plusieurs attaques/réponses/dégagements, avec déplacement entre trois repères. Les coupes suivent un impact ou le passage d'une arme devant l'objectif ; la situation du combat continue après la coupe.
- Guerrière au tachi : six plans sur quinze secondes, avec variations de rythme, de cadrage et d'échelle. Ce texte constitue une référence pour le spectacle demandé ; aucune efficacité comparative de rendu n'a été mesurée par l'agent.

Le curseur d'action doit permettre une forte densité de combinaisons dans un seul plan comme dans plusieurs. Le nombre de plans doit répartir cette chorégraphie, sans ajouter mécaniquement un combat par coupe ni revenir à une pose de départ. Une option Auto pour le découpage est proposée, à côté d'un nombre explicite ; le plafond technique actuel 2–4 du parcours H3 ne doit pas être confondu avec la cible créative des exemples.

L'utilisateur fournit les adversaires, styles et progression souhaitée ; le LLM reste responsable des techniques et d'une description finale détaillée. S'inspirer des combinaisons et du montage des exemples, sans hériter automatiquement de leurs effets, magie, scène, ouverture noire ou issue finale. Calibrer les niveaux élevés sur les rendus jugés réussis par l'utilisateur ; ne pas les réduire par principe à quelques gestes espacés ni imposer un coup à intervalle fixe. Classique et la version Combat actuelle restent disponibles et inchangés.

Neuf cookbooks `minimax.h3.{fl2va|ref2v}.combat[.multishot].{guided|planned|prompt}@1.0.0` épinglent trois profils Combat 1.0.0. Les manifestes comportent `preparation: {family: "combat", version: "1.0.0"}`. Il n'existe pas d'héritage de Classique ni de dépendance `latest`.

- `_blocks/h3-combat/1.0.0` : chorégraphie et responsabilités propres à chaque étape, Brief et ajustement après rendu.
- `_blocks/h3-output-contracts/1.0.0` : contrats de sortie et enveloppes techniques extraits après lecture. Les fichiers utilisateurs identiques sont partagés entre parcours.
- Blocs communs déjà utilisés par Classique : `video-preparation/1.0.0` pour références et responsabilité 2/3 étapes ; `vocal-preparation/1.0.0` pour les schémas compacts avec dialogues. Les enrichissements classiques de travaux/transformations ne sont pas hérités.
- `application/combat_preparation.py` : permissions et audace Combat 1.0.0, distinctes des politiques Classique. Transport, compilation et validateurs techniques existants restent communs.

Les textes assemblés des neuf cookbooks Classique actuels et de leurs trois profils restent identiques à l'état avant ce patch. Le snapshot SHA-256 est dans `tests/fixtures/h3_classic_prompt_baseline.json` ; les tests comparent les catalogues réellement assemblés et une mutation isolée d'un bloc Combat. Cela vérifie les consignes, pas l'équivalence de vidéos stochastiques.

Pour évoluer : publier de nouvelles versions propres à la famille. Pour une amélioration générale, publier un nouveau bloc commun et examiner son adoption par **les deux familles dans le même patch**. Documenter tout écart si une famille ne peut pas encore l'adopter. Ne pas réécrire un bloc déjà publié. Les corrections de file, stockage, interface et transport restent dans l'application commune.

## Continuité

La famille/version est conservée dans le profil, la session et le projet de rendu, et exposée dans l'API. Une combinaison profil/cookbook/session de familles différentes est refusée. L'ajustement après rendu utilise la révision **Combat 1.0.0** et ses propres consignes ; les versions Classique n'y sont pas proposées. Une version Combat absente n'est pas remplacée silencieusement par Classique.

L'adaptation H3 → REF2V conserve la famille/version, les références, les réglages, les paroles et les plans. « Repartir de la dernière frame » conserve la recette H3 exacte ; depuis REF2V Combat, il propose H3 Combat de la même version et avec le même nombre d'étapes. Si cette version manque, le brouillon courant est conservé et une erreur explicite est affichée.

Stockage : sessions **schéma 10**, compatible 1–9 ; projets H3 **schéma 7**, compatible 1–6. Les anciens projets deviennent Classique à la lecture et ne sont pas réécrits en masse. Catalogues : profils schéma 6 et cookbooks schéma 10, avec compatibilité des anciens manifestes.

## Vérification réservée à l'utilisateur

Tests préparés, **non exécutés** : neuf routes et nombre d'appels simulés, transmission aux rendus H3/REF2V, rejet des mélanges de familles, réouverture et anciens schémas, comparaison Classique, ajustement après rendu, conversion, sélecteurs et continuation. Les fixtures utilisent des réponses fixes et des services simulés ; aucun besoin de LLM ni de génération.

Depuis le checkout actif, par exemple :

```powershell
$env:PYTHONPATH = 'D:\Code\localQ\.panelpatch\src'
& D:\Code\panelforge\.venv\Scripts\python.exe -m unittest tests.test_combat_preparation tests.test_h3_multishot_browser tests.test_recipe_picker_browser tests.test_h3_ref2v_conversion
```

Les fixtures de migration de `tests/test_prompt_lab.py` et les assertions de cache de `tests/test_lab_web.py` sont également actualisées. Les tests navigateur utilisent Chromium local sans serveur et sont ignorés s'il manque.

Contrôles statiques effectués : syntaxe AST des Python modifiés/ajoutés, compilation JavaScript sans invocation (quatre scripts et trois fixtures navigateur), résolution des neuf manifestes Combat et trois profils, douze empreintes Classique inchangées, `git diff --check` sans erreur. Aucun import applicatif de vérification ni test exécuté.

Caches de l'interface : `lab-core.js`, `i2v-direct.js`, `ref2v-direct.js`, `h3-render-lab.js` **20260910.1**. Le patch nécessite le prochain redémarrage habituel du Lab par l'utilisateur, puis le rechargement de la page. Aucun service redémarré, aucune donnée de travail modifiée, aucun appel LLM ni génération. Les tags stables existants, dont `stable-avant-masque-2026-09-06`, sont conservés ; pas de commit ou push dans ce tour.
