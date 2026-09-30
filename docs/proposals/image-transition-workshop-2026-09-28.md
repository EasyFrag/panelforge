# Atelier de transitions entre images — alignement du 28 septembre 2026

Statut : premier patch autorisé puis implémenté localement le 28 septembre. Voir [le guide de l’atelier](../design/image-transitions.md). Tests préparés, non exécutés ; aucune génération ni relance de service. Le deuxième volet reste en alignement dans [le brief transmissible](image-sequence-generation-brief-2026-09-28.md).

## Besoin compris

L’utilisateur produit une suite d’états visuels avec KREA2 Edit, Qwen ou MiniMax. Il veut placer ces images dans une frise, puis créer les vidéos intermédiaires qui rendent chaque transformation compréhensible : travaux accélérés, nettoyage, installation, déplacement dans le décor.

Une suite de N images produit normalement N−1 unités vidéo. Chaque unité conserve l’image de début, l’image de fin, l’intention de transition, les réglages et son lien vers l’usine. Les images sélectionnées sont des versions précises ; le résultat d’un essai vidéo ne remplace pas implicitement les images de la frise.

## Historique retrouvé

Données locales lues dans D:/Code/panelforge/workspace, sans modification.

Chaîne KREA2 : krea2-edit-6462a7e65b4246b8a420db170dde6530. Quatre modifications validées, puis une étape vide. Export : D:/AI/PanelForge/KREA2 Projects/attempt-88d0893feb0747d48414ac8d24f19e15-00001__f75c25f4.

| Transition | Projet H3 | Essais terminés |
| --- | --- | --- |
| Original → sol nettoyé et pavé de marbre | h3-render-888059940c1a42efa2a80d3b4ea3c9a7 | 2 |
| Sol pavé → ouverture au plafond bordée de marbre | h3-render-96f060a5c199483a9cac1339680073ba | 3 |
| Ouverture bordée → murs en marbre et colonnes grecques | h3-render-dbff2d404a7a41c3b848f9cf661e96d0 | 2 |
| Salle en marbre → décoration moderne | h3-render-9b7dfea5205b4ee78f2f40204900bebe | 2 |

Le prompt collé par l’utilisateur correspond exactement au current_prompt du deuxième projet, h3-render-96f…. Trois essais succeeded, deux à 0,2 MP puis un à 1,2 MP, durée configurée 7 s, 25 steps, même seed 12852852938604296938. Le premier projet inspecté pendant la recherche était la transition suivante, à deux essais ; l’identification finale distingue bien les deux.

- Session : prompt-64b29935e2c34964b9a74fbca832741f.
- Recette historique : minimax.h3.fl2va.direct.prompt@1.0.0.
- Intention française retrouvée : ouvrier en jean bleu, tee-shirt blanc, casquette bleue ; escabeau, agrandissement au marteau-piqueur, pose du cercle de marbre, nettoyage ; nuages animés ; effet de captation accélérée de toute l’action.
- Images H3 : asset-8ad424b34f80408fad888ea7fb878563 et asset-6ef9d6ad394f4a2aafbde63de29e017f. Leur contenu binaire est identique aux images KREA validées asset-88b50f80979c479d98c9584a53f82e9a et asset-398435799b8e4b18a90948f94f679dd3.
- Dernière vidéo : asset-3bb2b433987e4b089bdf67f843f90e00, media_type video/mp4, 3 777 189 octets. Asset sous workspace/assets/<id>/content.bin.
- Les vidéos n’ont pas été visionnées : succeeded décrit l’état enregistré, pas une qualification visuelle.

## Interface proposée

Préférence explicite de l’utilisateur : interface fonctionnelle et compacte, inspirée de l’usine à vidéo et des ateliers d’image. L’UX du mode histoire lui convient moins. La disposition ci-dessous reste une proposition à discuter.

Un onglet « Transitions d’images », organisé en un espace de travail :
- Une barre compacte : projet, ajouter des images, proposer les transitions, envoyer la sélection à l’usine. Conservation des conventions de sélection multiple et de retour d’état de l’usine.
- Une frise horizontale de vignettes numérotées, pour ajouter, réordonner, remplacer ou retirer une image et voir l’ensemble de la progression. Chaque image reste agrandissable.
- Sous la frise, une liste dense : sélection, paire d’images, action courte modifiable, durée, état. Une ligne par transition, avec accès direct à la correction et à la validation.
- Un panneau partagé à droite pour la transition sélectionnée : aperçu avant/après agrandissable, intention française complète, consigne personnelle et réglages particuliers. Les grandes images et le texte détaillé sont consultés ici sans multiplier les fiches ouvertes.
- Réglages communs accessibles dans un panneau repliable : effet d’accélération, durée indicative, caméra par défaut, description de l’ouvrier, ambiance sonore, musique et éléments à conserver. Ajustements possibles par transition.

Les images sont ajoutées depuis un fichier ou une version choisie dans les projets KREA/Qwen/MiniMax ; un import des seules étapes validées peut préremplir la frise. Le type de transition peut être déduit puis corrigé dans le détail plutôt qu’imposer un formulaire à chaque paire.

États proposés : à préparer, à relire, prête, envoyée. La relecture humaine avant envoi est la préférence actuelle ; validation et envoi possibles pour une sélection. Le détail Plan/Prompt/Vidéo reste dans l’usine, accessible depuis la transition.

Réordonner ou remplacer une image ne doit invalider que les transitions qui en dépendent. Une consigne déjà corrigée manuellement doit être conservée lors d’une nouvelle proposition, ou remplacée explicitement. Une transition déjà envoyée garde sa version dans l’usine ; un changement ultérieur doit être explicite.

Exemples de l’utilisateur :

| Paire | Action | Traitement proposé |
| --- | --- | --- |
| 1 → 2 | Tronçonneuse | Travaux accélérés, découpe visible et évacuation des morceaux |
| 2 → 3 | Balai | Nettoyage, disparition progressive des déchets après les passages |
| 3 → 4 | Marteau | Installation, transport/pose/fixation de l’élément concerné |
| 4 → 5 | Entrer dans l’arbre | Déplacement de caméra ; vérifier la cohérence entre extérieur et intérieur |
| 5 → 6 | Agrandir le trou supérieur | Travaux accélérés, transformation localisée et nettoyage |

## Automatisation proposée

1. L’utilisateur ordonne les images et peut renseigner quelques actions en mots simples.
2. « Proposer les transitions » analyse les images et les consignes de modification disponibles. Le LLM propose une intention française pour chaque paire, en tenant compte de la continuité globale.
3. L’utilisateur relit les propositions, corrige si nécessaire puis valide les transitions choisies. Sa consigne explicite reste prioritaire ; une proposition LLM n’est pas envoyée automatiquement. Pour une frise longue, utiliser des groupes avec contexte commun plutôt qu’un appel multimodal sans limite.
4. « Envoyer à l’usine » crée les unités sélectionnées avec leur ordre, leurs ancrages, leurs intentions et leurs paramètres. L’usine réutilise sa préparation Plan → Prompt → Vidéo, puis DLSS facultatif.

L’analyse de transition doit distinguer les différences visibles, l’opération suggérée et les incertitudes. Deux images peuvent montrer une nouvelle porte sans prouver l’outil utilisé ; la tronçonneuse peut être une proposition ou une instruction utilisateur, pas une observation certaine.

Le prompter doit décrire une causalité visuelle : matériau amené, outil en contact, modification qui suit le geste, résidus retirés. L’accélération concerne la captation globale, pas seulement un personnage qui court. Si les images frontières montrent un décor vide, prévoir l’entrée et la sortie de l’ouvrier. Les raccords entre clips restent à qualifier même avec une image frontière commune.

## Briques existantes et ajouts

Déjà présents :
- Assets d’images et historiques d’édition versionnés.
- H3 Base avec rôles first_frame / last_frame, dérivation FL2VA et compilation de l’enveloppe des références.
- Préparation LLM, plans, prompts et profils H3/Ref2V.
- Unités de l’usine avec intention, références, durée, réglages, étapes de préparation/rendu, reprises et DLSS.
- Le service VideoFactoryService.receive accepte une liste d’entrées ; l’API actuelle reçoit principalement une entrée H3/Ref2V, ou des scènes d’un épisode.

À ajouter pour cet atelier :
- Projet de frise et import/sélection multiaatelier des versions d’images.
- Analyse des différences et intentions de transition, éditables et conservées.
- Relation durable entre une transition/version et ses unités/essais de l’usine ; envoi groupé dédupliqué et retours de statut.
- Contrat de réglages « travaux accélérés », sans refaire le moteur de rendu.
- Aucun montage final automatique requis. La génération itérative de nouvelles images fait désormais l’objet d’un deuxième volet en cours d’alignement, documenté séparément ; elle ne remplace pas ce premier patch.

## FL2VA et référence d’ouvrier

La documentation officielle distingue H3-Base-FL2VA (zéro, une ou deux images) et H3-Base-Ref2VA (jusqu’à neuf images).
Source consultée : https://github.com/MiniMax-AI/MiniMax-H3#model-variants-and-input-specifications

Le code actuel de l’usine confirme la séparation :
- En mode h3, seules les deux images frontières sont admises.
- En mode ref2v, les images, y compris celles étiquetées first/last, passent dans la liste des références ; elles n’occupent pas les entrées first/last du rendu FL2VA.

Décision d’alignement : une description/tenue cohérente de l’ouvrier suffit au départ ; FL2VA reste la base proposée pour les transitions entre états. Une option Ref2VA permettrait départ + arrivée + portrait d’ouvrier, avec qualification visuelle des états frontières et de l’identité. Ne pas promettre le même conditionnement first/last après un simple changement de mode. Une référence seulement montrée au LLM aiderait la description sans garantir l’identité au rendu.

## Décisions et limites du périmètre actuel

- Description textuelle commune de l’ouvrier suffisante au départ ; aucun portrait requis pour cette première version.
- Préférence actuelle pour une relecture humaine des propositions avant envoi à l’usine.
- Images déjà disponibles, choisies et ordonnées par l’utilisateur ; N images donnent N−1 transitions.
- Actions proposées par LLM et corrigeables ; durée, type et indications manuelles ajustables par paire.
- UX compacte inspirée de l’usine et des ateliers d’image ; la disposition frise/liste/panneau reste à discuter.
- L’utilisateur a ensuite autorisé le premier patch ; l’atelier de transitions est implémenté localement. La création autonome d’images reste séparée.

## Deuxième volet désormais en cours d’alignement : faire évoluer les images et le scénario

L’utilisateur souhaite pouvoir partir d’une seule image et laisser un LLM construire progressivement une suite de transformations et un scénario. Le modèle doit analyser l’image effectivement produite, proposer l’étape suivante, piloter son édition/génération, puis observer le résultat pour décider de la suite.

Boucle envisagée : image retenue + direction générale → proposition d’une transformation → image candidate → examen du résultat et des éléments à conserver → retenir, corriger ou réessayer → étape suivante. Le scénario évolue avec les résultats observés. Le système doit pouvoir reconnaître une étape non accomplie et éviter de la considérer comme acquise dans la suite.

Précision utilisateur ultérieure : partir d’une image, d’une intention facultative et d’un nombre d’étapes, puis laisser le LLM proposer et itérer seul. MiniMax est le moteur d’édition demandé ; les LLM sont paramétrables par rôle. La proposition précédente de validation humaine à chaque image n’est donc pas le parcours retenu pour cette nouvelle ébauche. Le [brief séparé](image-sequence-generation-brief-2026-09-28.md) propose une boucle minimale, deux rôles LLM et un formulaire compact. Aucune implémentation demandée à ce stade.

Préparation minimale utile dès le premier atelier : conserver les versions précises des images, leur origine et les intentions de transformation ; lier chaque transition à ses deux images retenues. Une future image générée pourra alors rejoindre la même frise. Les intentions vidéo se préparent à partir des images retenues, en tenant compte de ce qui a réellement changé.

Cette ambition réutilise l’idée d’un scénario construit progressivement, avec une interface centrée sur les images et leurs transitions. Elle n’impose pas de reprendre l’organisation de l’interface du mode histoire.
