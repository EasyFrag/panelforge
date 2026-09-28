# Audit — gestes des Petits hommes expérimentaux (27 septembre 2026)

Demande : vérifier si les multiples gestes sont représentés dans les générations.
Audit des sept fiches expérimentales existantes, sans modification applicative
ni relance. La discussion des langues est validée par l'utilisateur ; voir
l'addendum au rapport des langues.

## Périmètre et méthode

- Sept Plans JSON, sept Prompts usine et les sept essais H3 correspondants.
- Les prompts d'essai sont identiques aux prompts usine ; les effective_prompt
  sont identiques après retrait des espaces de bord (retour final).
- Sept vidéos H3 brutes, 10,13 s environ, 736 × 1280, 24 fps.
- Extraction CPU avec le ffmpeg déjà installé : 20 captures par vidéo, à 2 images/s,
  soit 140 captures examinées. Les repères 0 à 9,5 s sont ceux de l'échantillonnage.
- Observation par captures successives, pas lecture continue ni écoute audio.
  Les versions DLSS livrées n'ont pas été inspectées séparément.
- Pas de test applicatif, appel LLM, rendu, génération ou redémarrage.
  Seules des copies diagnostiques et la documentation ont été écrites.

Instantané, index des vidéos, captures, planches et contrôles de prompts :
D:/Code/panelforge/.agent/diagnostics/little-men-gestures-2026-09-27/

## Constat par génération

Les numéros correspondent à media-index.json et aux dossiers des planches.

| N° / fin d'ID | Scène | Plan et prompt effectif | Observation des captures H3 |
| --- | --- | --- | --- |
| 1 / 9fe0bd1b | Lieu de culte, clocher penché | Refermer/redresser la flèche à l'aiguille ; enrouler puis nouer le fil à sa base | Deux temps lisibles : clocher redressé vers 4–5 s, puis main abaissée et fil doré entourant le clocher vers 5,5–7,5 s. La main saisit directement la flèche pendant son redressement. Résultat et bande dorée persistent après son retrait. |
| 2 / cc6d32d2 | Pont | Poser un brin formant le passage ; fixer aux deux rives et remonter les fils pendants | Passage formé vers 3–4,5 s, travail de finition vers 5–7 s. Plusieurs gestes sont visibles mais restent proches d'une seule opération de couture. Les fils pendants disparaissent vers l'eau ; leur remontée sur le pont n'est pas clairement établie. |
| 3 / 5bcf987a | Lieu de culte, arche blanche | Reconstituer l'arche ; coudre sa jonction supérieure | Arche remontée, puis crochet travaillant au sommet ; deuxième effet plus subtil. Deux mains visibles dès environ 2 s alors qu'une seule est demandée. La colonne avant droite reste tronquée : le plan ciblait seulement l'arche. |
| 4 / af3de81a | Lieu de culte dans le désert | Relever le pan effondré ; nouer à la base et rassembler les fils | Pan relevé vers 4–5 s, geste plus bas/horizontal vers 5,5–7 s, façade fermée ensuite. Deux temps présents ; le nouage/nettoyage exact n'est pas entièrement confirmé. Une longue aiguille et une boucle de fil restent au premier plan. |
| 5 / a00e3278 | Pont | Rapprocher les deux moitiés ; serrer un nœud à la jonction | Pont rejoint vers 4–5 s, puis aiguille manipulée à la jonction jusqu'à 7 s. Le second résultat, un petit nœud, est peu distinct sur les captures ; impression de couture continue. |
| 6 / dc91e8f7 | Pierre sur la route, baguette | Installer un levier sur un caillou ; appuyer pour faire rouler le rocher hors du chemin | Outil approché/placé, puis main agrippant directement le rocher vers 5–7 s. Chemin dégagé, mais mécanisme de levier non fidèlement représenté. Dès le plan, mise en place + utilisation correspondent à une aide principale plutôt qu'à deux effets autonomes. |
| 7 / b4fc2c29 | Pierre sur la route, cuillère | Libérer le rocher avec le creux de la cuillère ; le guider sur le côté avec le manche | Rocher mis en mouvement vers 3,5–4,5 s, puis poussé sur le côté vers 5–7 s. Enchaînement lisible ; la cuillère reste utilisée du côté de son creux, pas clairement avec le manche comme demandé. |

## Interprétation

Les gestes successifs sont réellement présents. L'assemblage ne les a pas
supprimés : les actions restent dans les prompts effectifs du rendu.
Six Plans prévoient une réparation puis une finition/déplacement complémentaire ;
le septième décrit surtout la préparation et l'utilisation d'un seul levier.

La lisibilité varie : le clocher redressé puis entouré de fil et le rocher déplacé
puis guidé sur le côté offrent les deux exemples les plus nets dans cet échantillon.
Les ponts produisent plutôt une couture prolongée. Les cinq scènes de pont/bâtiment
choisissent toutes aiguille ou crochet, en cohérence avec les décors de laine mais
avec peu de variété d'intervention.

Les écarts observés concernent la mise en scène et le suivi des gestes :
deux mains pour l'arche, prise directe du rocher au lieu du levier, détails
de fixation/nettoyage peu distincts. Ces sept essais ne permettent pas d'attribuer
ces écarts au sampling, au modèle ou à la seule durée.

## Proposition à discuter

Conserver deux gestes utiles lorsque le problème le justifie, et juger leur
distinction par les effets visibles :
1. Premier geste avec résultat intermédiaire compréhensible.
2. Second geste répondant à un besoin restant, avec un changement visible propre.
3. Résultat final, retrait et remerciement.

Exemples possibles sans en faire une recette répétitive : libérer le rocher puis
le caler hors du chemin ; remettre la passerelle puis ajouter un appui visible.
Entrée/sortie de la main, prise d'outil et remerciement ne comptent pas comme
une aide supplémentaire. Un unique geste peut toujours suffire ; pas de
remplissage. Pour le preset, privilégier un effet secondaire assez visible
plutôt qu'un minuscule nœud présenté comme preuve suffisante de deux aides.

Aucun correctif implémenté : poursuivre l'alignement demandé.
