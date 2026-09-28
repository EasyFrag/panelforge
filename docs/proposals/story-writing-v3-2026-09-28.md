# Écriture Expérimentale v3 — 28 septembre 2026

## Livraison et activation

Implémentation dans `D:/Code/panelforge-krea2-flux`, édition `experimental-2026-09-28`, politique 3, révision éditoriale 10, contrat de réponse 2.5.0. Empreinte : `babe2b1ef0fc06d50a23eaa86b26af0fc05bd9b80fe4e72ec2c55734416d8e49`.

Le nouveau lecteur charge explicitement `editions/catalog-v3.json`. Le catalogue `catalog.json` lu par les processus déjà démarrés est conservé octet pour octet : ils ne découvrent pas une politique qu’ils ne savent pas lire. La v3 devient disponible au prochain démarrage du backend avec ce code ; aucun redémarrage n’a été effectué. Elle sera le choix par défaut des nouvelles histoires et nouvelles préparations de suite. Les histoires et suites déjà épinglées conservent leur édition ; le sélecteur d’en-tête permet de choisir la v3 pour les prochains appels.

Les archives v1/v2, les scénarios achevés, médias, imports manuels et sélections d’images existants n’ont pas été modifiés. Les réglages modèles, températures, budget de sortie 80 000 et nombre d’appels du parcours restent conservés. Pas de nouvelle passe LLM ni de mécanisme d’arrêt fondé sur les répétitions du raisonnement.

## Changements

- **Récit et chat de suite** : relation utile explicite, aveu apportant une information nouvelle, explications réellement incompatibles, tromperie distincte d’une réparation et conséquence locale perceptible. Les conclusions écrites dans action/evidence ne suffisent pas sans gestes ou paroles qui les établissent. Fin ouverte, registre et choix d’auteur préservés, sans quota de clips, gag, vulgarité ou punition.
- **Répliques protégées** : seules les entrées explicites de `writing_direction.protected_lines` créent des IDs `author-line-*` liés au texte source. Le concepteur attribue chaque ID à une unité, un événement et un locuteur. Le rédacteur renvoie `line_ref` dans le dialogue ; l’application restitue les mots exacts et conserve `dialogue_id` avant validation, durée, relecture et fabrication. Référence inconnue/périmée, locuteur/événement incorrect et couverture manquante sont refusés. Aucun extracteur de citations implicites ni rapprochement approximatif.
- **Corrections locales** : `scene_edits` et `base_hash` restent les mécanismes utilisés. `episode_state=null` conserve faits, savoirs et fils ; un état complet reste possible pour une modification narrative. Une réparation classée exclusivement `dialogue_language` impose la mémoire inchangée. La correction de format existante demeure sans changement de contenu.
- **Présence et parole** : `character_ids` décrit les visibles, muets inclus. Les voix non visibles utilisent un personnage connu et un mode explicite. Une scène peut montrer seulement un décor/objet avec voix hors champ. Les références de fabrication restent liées aux visibles, indépendamment des locuteurs. Une mention n’ajoute personne ; silence et gros plan ne deviennent pas une sortie narrative. Les entrées/sorties et raccords sont décrits dans les champs existants, sans liste supplémentaire.
- **Annexe visuelle** : IDs de personnages/détenteurs typés par le casting ; objets avec identité indépendante. Les éléments invalides ou ambigus sont signalés et isolés ; les éléments valides indépendants et les remplacements antérieurs valides sont conservés. Le brouillon original reste disponible. Même traitement pour les corrections de relecture et les héritages indépendants.
- **Héritage** : l’état hérité déjà présent à la première apparition n’est plus inséré une seconde fois à la scène 1. Un ID hérité contradictoire est signalé. Une comparaison typographique dédiée tolère notamment les apostrophes droites/courbes sans modifier `appearance_key` ni les IDs persistants des images.
- **Images** : apparence identique reprise avec provenance ; pose, émotion et détenteur distincts de l’apparence. Une nouvelle apparence au début d’une suite peut prendre l’image validée de la même identité comme source du flux de variantes existant. Cela ne sélectionne ni ne génère une image automatiquement. La fiche expose cette provenance ; les imports et choix manuels gardent priorité.
- **Contexte** : décodage des enveloppes historiques JSON connues et références vers les gros contenus exactement identiques, sans résumé LLM ni perte de scènes/dialogues/faits/savoirs. Les portées projet/unité restent conservées. Les résidus anglais dans les faits et fils internes deviennent un diagnostic indicatif, jamais un blocage automatique lexical.

Un ancien arc avec des répliques protégées doit recevoir leur attribution explicite avant une écriture v3. Cette attribution peut être corrigée par `outline/author_line_assignments` dans le parcours d’édition existant ; l’application ne devine ni locuteur ni événement. Un changement de source reste consultable et diagnostiqué, sans réinterpréter les brouillons reçus sous une autre édition.

## Prompts et cohérence

Les nouvelles consignes remplacent les consignes v2 correspondantes. Retirées : obligation de recopier les répliques dans evidence, répétition des textes protégés dans le contexte rédacteur, renvoi obligatoire de toute la mémoire pour une retouche locale, nombre fixe de moments dans le chat de suite. Schémas, exemples de réparation et adaptateurs suivent le contrat 2.5.

Mesure statique des blocs archivés actifs, avec qualité et ton activés :

| Rôle | v2, caractères | v3, caractères | Variation |
| --- | ---: | ---: | ---: |
| Conception | 5 302 | 3 895 | −26,5 % |
| Écriture | 7 878 | 6 523 | −17,2 % |
| Relecture | 6 544 | 5 450 | −16,7 % |
| Discussion de suite | 1 836 | 1 676 | −8,7 % |

Ces chiffres excluent contexte, schéma et ajouts dynamiques : ils ne mesurent ni la taille complète réellement envoyée, ni les tokens, ni la latence. Un cas de régression prépare la comparaison des requêtes complètes v2/v3 sur une suite synthétique avec historique dupliqué ; il n’a pas été exécuté. Le gain réel et la qualité des générations restent à observer lors des prochains essais.

## Vérifications

- Syntaxe Python de tous les fichiers concernés : AST valide.
- JavaScript modifié : compilation V8 seule réussie, sans exécution de l’application.
- Archives et catalogue : JSON, empreintes SHA-256, empreinte du paquet v3 et conservation exacte des archives/catalogue historiques vérifiés.
- Diff isolé : pas d’erreur d’espacement relevée ; sauvegardes des fichiers concernés conservées.
- 22 cas nouveaux préparés dans `tests/test_story_writing_v3.py` : chaîne synthétique, source exacte, attribution, mémoire locale, fabrication des présents silencieux et voix hors champ, entrée tardive de Sacha, typo, annexe partielle, carton transformé, imports, contexte, provenance et anciens lecteurs. Fixtures v2 des suites existantes explicitement conservées.

**Tests fonctionnels non exécutés**, selon `AGENTS.md` du checkout actif : « Tests are run by the user unless explicitly requested otherwise. » Aucun appel LLM, image/vidéo, redémarrage, commit ou push.

Commande ciblée à exécuter depuis le checkout actif avec son environnement Python :

```powershell
$env:PYTHONPATH = 'D:\Code\panelforge-krea2-flux\src'
& 'D:\Code\panelforge\.venv\Scripts\python.exe' -m unittest tests.test_story_writing_v3 tests.test_story_editions tests.test_story_quality_policy tests.test_story_workflow
```

Suite complète du dépôt : `python -m unittest discover -s tests`.

## Traces

Plan accepté : `D:/Code/panelforge/docs/proposals/story-recent-runs-corrective-plan-2026-09-28.md`.
Sauvegardes, diff et contrôle statique : `D:/Code/panelforge/.agent/diagnostics/story-writing-v3-2026-09-28/` (`before/`, `implementation.diff`, `static-report.json`, `immutable-before.json`).

Les constats des audits Colis/carton, Coupe, copine et Moula ont servi au patch. Aucun nouvel examen audiovisuel ni réécriture de ces runs n’a été effectué. Pour Sacha, le cas observé reste une entrée écrite scène 4 ; le correctif ne la rajoute pas rétroactivement aux scènes précédentes.
